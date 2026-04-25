"""Tests for adp_worker_assignment_tools — build_worker_assignment_tools builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_worker_assignment_tools import (
    PATH_ORG_UNITS_MODIFY,
    PATH_REPORTS_TO_MODIFY,
    PATH_WORK_ASSIGNMENT_MODIFY,
    PATH_WORK_ASSIGNMENT_TERMINATE,
    build_change_org_units_event,
    build_change_reports_to_event,
    build_modify_work_assignment_event,
    build_terminate_work_assignment_event,
    build_worker_assignment_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


def test_build_change_reports_to_event():
    body = build_change_reports_to_event(
        associate_oid="G3EMP", work_assignment_item_id="WA-1",
        new_manager_associate_oid="G3MGR",
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {"associateOID": "G3EMP", "workAssignmentID": "WA-1"}
    assert event["data"]["transform"]["workAssignment"]["reportsTo"] == [{"associateOID": "G3MGR"}]


def test_build_change_org_units_event():
    body = build_change_org_units_event(
        associate_oid="G3EMP", work_assignment_item_id="WA-1",
        organizational_units=[{"type_code": "Department", "name_code": "Engineering"}],
    )
    units = body["events"][0]["data"]["transform"]["worker"]["workAssignment"]["assignedOrganizationalUnits"]
    assert units[0]["typeCode"] == {"codeValue": "Department"}
    assert units[0]["nameCode"] == {"codeValue": "Engineering"}


def test_build_modify_work_assignment_event_accepts_arbitrary_fields():
    body = build_modify_work_assignment_event(
        associate_oid="G3EMP", work_assignment_item_id="WA-1",
        work_assignment_fields={"jobTitle": "Senior Engineer"},
    )
    wa = body["events"][0]["data"]["transform"]["worker"]["workAssignment"]
    assert wa == {"jobTitle": "Senior Engineer"}


def test_build_terminate_work_assignment_event():
    body = build_terminate_work_assignment_event(
        associate_oid="G3EMP", work_assignment_item_id="WA-1",
        termination_date="2026-06-01", comment="Position eliminated",
        reason_code="Position Eliminated",
    )
    event = body["events"][0]
    assert event["data"]["eventContext"]["worker"]["workAssignment"] == {"itemID": "WA-1"}
    assert event["data"]["transform"]["worker"]["workAssignment"] == {"terminationDate": "2026-06-01"}
    assert event["data"]["transform"]["comment"] == {"text": "Position eliminated"}
    assert event["data"]["transform"]["eventReasonCode"] == {"codeValue": "Position Eliminated"}


@pytest.mark.asyncio
async def test_build_tools_returns_four_tools():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_assignment_tools(conn, cache)
    assert {t.name for t in tools} == {
        "change_employee_manager",
        "change_employee_organizational_units",
        "modify_employee_work_assignment",
        "terminate_employee_work_assignment",
    }


@pytest.mark.asyncio
async def test_tools_route_to_correct_paths():
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

    tools = {t.name: t for t in build_worker_assignment_tools(conn, cache)}

    with patch("lfx.components.adp.adp_worker_assignment_tools.build_mtls_httpx_client", fake_client):
        await tools["change_employee_manager"].ainvoke(
            {"associate_oid": "A", "work_assignment_item_id": "W", "new_manager_associate_oid": "M"},
        )
        await tools["change_employee_organizational_units"].ainvoke(
            {"associate_oid": "A", "work_assignment_item_id": "W", "organizational_units": []},
        )
        await tools["modify_employee_work_assignment"].ainvoke(
            {"associate_oid": "A", "work_assignment_item_id": "W", "work_assignment_fields": {}},
        )
        await tools["terminate_employee_work_assignment"].ainvoke(
            {"associate_oid": "A", "work_assignment_item_id": "W"},
        )

    posted_urls = [c.kwargs.get("url") or c.args[1] for c in client.request.call_args_list]
    assert any(PATH_REPORTS_TO_MODIFY in u for u in posted_urls)
    assert any(PATH_ORG_UNITS_MODIFY in u for u in posted_urls)
    assert any(PATH_WORK_ASSIGNMENT_MODIFY in u for u in posted_urls)
    assert any(PATH_WORK_ASSIGNMENT_TERMINATE in u for u in posted_urls)


@pytest.mark.asyncio
async def test_unauthorized_triggers_refresh_and_retry():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_assignment_tools(conn, cache)
    tool = next(t for t in tools if t.name == "change_employee_manager")

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

    with patch("lfx.components.adp.adp_worker_assignment_tools.build_mtls_httpx_client", fake_client), \
         patch("lfx.components.adp.adp_worker_assignment_tools.fetch_token", AsyncMock()) as fetch_mock:
        await tool.ainvoke(
            {"associate_oid": "A", "work_assignment_item_id": "W", "new_manager_associate_oid": "M"},
        )

    fetch_mock.assert_awaited_once()
    assert client.request.await_count == 2
