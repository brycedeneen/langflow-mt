"""Tests for adp_worker_deployment_tools — build_worker_deployment_tools builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_worker_deployment_tools import (
    PATH_CHANGE_STANDARD_HOURS,
    PATH_CHANGE_WORKER_TYPE,
    build_change_standard_hours_event,
    build_change_worker_type_event,
    build_worker_deployment_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


def test_build_change_standard_hours_event():
    body = build_change_standard_hours_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        hours_quantity=32.0,
        effective_date="2026-05-01",
        reason_code="Schedule Change",
    )
    event = body["events"][0]
    assert event["data"]["eventContext"]["worker"] == {
        "associateOID": "G3ABC",
        "workAssignment": {"itemID": "WA-1"},
    }
    sh = event["data"]["transform"]["workAssignment"]["standardHours"]
    assert sh["hoursQuantity"] == 32.0
    assert sh["unitCode"] == {"codeValue": "Hour"}
    assert sh["unitTimeCode"] == {"codeValue": "Weekly"}
    assert event["data"]["transform"]["effectiveDateTime"] == "2026-05-01"
    assert event["data"]["transform"]["eventReasonCode"] == {"codeValue": "Schedule Change"}


def test_build_change_worker_type_event():
    body = build_change_worker_type_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        worker_type_code="Contractor",
    )
    wa = body["events"][0]["data"]["transform"]["workAssignment"]
    assert wa["workerTypeCode"] == {"codeValue": "Contractor"}


@pytest.mark.asyncio
async def test_build_tools_returns_two_tools():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_deployment_tools(conn, cache)
    assert {t.name for t in tools} == {
        "change_employee_standard_hours",
        "change_employee_worker_type",
    }


@pytest.mark.asyncio
async def test_tool_routes_to_correct_paths():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {"confirmMessage": {"requestID": "R-1"}}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = {t.name: t for t in build_worker_deployment_tools(conn, cache)}

    with patch("lfx.components.adp.adp_worker_deployment_tools.build_mtls_httpx_client", fake_client):
        await tools["change_employee_standard_hours"].ainvoke({
            "associate_oid": "G3ABC", "work_assignment_item_id": "WA-1", "hours_quantity": 40.0,
        })
        await tools["change_employee_worker_type"].ainvoke({
            "associate_oid": "G3ABC", "work_assignment_item_id": "WA-1", "worker_type_code": "Regular",
        })

    posted_urls = [c.kwargs.get("url") or c.args[1] for c in client.request.call_args_list]
    assert any(PATH_CHANGE_STANDARD_HOURS in u for u in posted_urls)
    assert any(PATH_CHANGE_WORKER_TYPE in u for u in posted_urls)


@pytest.mark.asyncio
async def test_unauthorized_triggers_refresh_and_retry():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_deployment_tools(conn, cache)
    tool = next(t for t in tools if t.name == "change_employee_worker_type")

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

    with patch("lfx.components.adp.adp_worker_deployment_tools.build_mtls_httpx_client", fake_client), \
         patch("lfx.components.adp.adp_worker_deployment_tools.fetch_token", AsyncMock()) as fetch_mock:
        await tool.ainvoke({
            "associate_oid": "G3ABC", "work_assignment_item_id": "WA-1", "worker_type_code": "Regular",
        })

    fetch_mock.assert_awaited_once()
    assert client.request.await_count == 2
