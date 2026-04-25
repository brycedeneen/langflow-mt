"""Tests for adp_worker_lifecycle_tools — build_worker_lifecycle_tools builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_worker_lifecycle_tools import (
    PATH_REHIRE,
    build_rehire_event,
    build_worker_lifecycle_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


def test_build_rehire_event_minimum():
    body = build_rehire_event(
        associate_oid="G3ABC", work_assignment_item_id="WA-1", rehire_date="2026-05-01",
    )
    event = body["events"][0]
    assert event["data"]["eventContext"]["associateOID"] == "G3ABC"
    assert event["data"]["eventContext"]["workAssignment"] == {"itemID": "WA-1"}
    worker = event["data"]["transform"]["worker"]
    assert worker["associateOID"] == "G3ABC"
    assert worker["workerDates"] == {"rehireDate": "2026-05-01"}
    assert worker["workAssignment"]["hireDate"] == "2026-05-01"
    assert event["data"]["transform"]["effectiveDateTime"] == "2026-05-01"


def test_build_rehire_event_with_rich_fields():
    body = build_rehire_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        rehire_date="2026-05-01",
        job_code="SWE-2",
        job_title="Senior Engineer",
        worker_type_code="Regular",
        work_location_name="Remote",
        department_name="Engineering",
        reports_to_associate_oid="G3MGR",
        annual_base_pay=150000.0,
        reason_code="Rehire",
    )
    wa = body["events"][0]["data"]["transform"]["worker"]["workAssignment"]
    assert wa["jobCode"] == {"codeValue": "SWE-2"}
    assert wa["jobTitle"] == "Senior Engineer"
    assert wa["workerTypeCode"] == {"codeValue": "Regular"}
    assert wa["homeWorkLocation"] == {"nameCode": {"codeValue": "Remote"}}
    assert wa["homeOrganizationalUnits"][0]["nameCode"] == {"codeValue": "Engineering"}
    assert wa["reportsTo"] == [{"associateOID": "G3MGR"}]
    assert wa["baseRemuneration"]["annualRateAmount"]["amountValue"] == 150000.0
    assert body["events"][0]["data"]["transform"]["eventReasonCode"] == {"codeValue": "Rehire"}


def test_build_rehire_event_additional_fields_deep_merge():
    body = build_rehire_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        rehire_date="2026-05-01",
        department_name="Engineering",
        additional_worker_fields={
            "person": {"legalName": {"givenName": "Jane", "familyName1": "Doe"}},
        },
    )
    worker = body["events"][0]["data"]["transform"]["worker"]
    assert worker["person"]["legalName"] == {"givenName": "Jane", "familyName1": "Doe"}
    assert worker["workAssignment"]["homeOrganizationalUnits"][0]["nameCode"] == {"codeValue": "Engineering"}


@pytest.mark.asyncio
async def test_build_tools_returns_one_tool():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_lifecycle_tools(conn, cache)
    assert len(tools) == 1
    assert tools[0].name == "rehire_employee"


@pytest.mark.asyncio
async def test_rehire_tool_routes_to_path():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {"ok": True}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = build_worker_lifecycle_tools(conn, cache)

    with patch("lfx.components.adp.adp_worker_lifecycle_tools.build_mtls_httpx_client", fake_client):
        await tools[0].ainvoke({
            "associate_oid": "G3ABC",
            "work_assignment_item_id": "WA-1",
            "rehire_date": "2026-05-01",
        })

    posted_url = client.request.call_args.kwargs.get("url") or client.request.call_args.args[1]
    assert PATH_REHIRE in posted_url


@pytest.mark.asyncio
async def test_unauthorized_triggers_refresh_and_retry():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_lifecycle_tools(conn, cache)
    tool = tools[0]

    unauthorized = MagicMock(spec=httpx.Response)
    unauthorized.status_code = 401
    unauthorized.json.return_value = {"message": "unauthorized"}

    success = MagicMock(spec=httpx.Response)
    success.status_code = 200
    success.json.return_value = {"ok": True}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.side_effect = [unauthorized, success]

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_lifecycle_tools.build_mtls_httpx_client", fake_client), \
         patch("lfx.components.adp.adp_worker_lifecycle_tools.fetch_token", AsyncMock()) as fetch_mock:
        await tool.ainvoke({
            "associate_oid": "G3ABC",
            "work_assignment_item_id": "WA-1",
            "rehire_date": "2026-05-01",
        })

    fetch_mock.assert_awaited_once()
    assert client.request.await_count == 2
