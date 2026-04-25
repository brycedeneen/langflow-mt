"""Tests for adp_worker_compensation_tools — build_worker_compensation_tools builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_worker_compensation_tools import (
    PATH_ADD_ADDITIONAL,
    PATH_CHANGE_ADDITIONAL,
    PATH_CHANGE_BASE,
    PATH_REMOVE_ADDITIONAL,
    build_add_additional_remuneration_event,
    build_change_additional_remuneration_event,
    build_change_base_pay_event,
    build_remove_additional_remuneration_event,
    build_worker_compensation_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


# ------------- envelope builders -------------


def test_build_change_base_pay_event_minimum():
    body = build_change_base_pay_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        new_annual_amount=125000.0,
    )
    event = body["events"][0]
    assert event["data"]["eventContext"]["worker"] == {
        "associateOID": "G3ABC",
        "workAssignment": {"itemID": "WA-1"},
    }
    wa = event["data"]["transform"]["workAssignment"]
    assert wa["baseRemuneration"]["annualRateAmount"] == {
        "amountValue": 125000.0,
        "currencyCode": "USD",
    }
    assert "effectiveDate" not in wa["baseRemuneration"]
    assert "effectiveDateTime" not in event["data"]["transform"]
    assert "eventReasonCode" not in event["data"]["transform"]


def test_build_change_base_pay_event_with_date_and_reason():
    body = build_change_base_pay_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        new_annual_amount=100000.0,
        currency_code="EUR",
        effective_date="2026-05-01",
        reason_code="Annual Review",
    )
    transform = body["events"][0]["data"]["transform"]
    assert transform["workAssignment"]["baseRemuneration"]["annualRateAmount"]["currencyCode"] == "EUR"
    assert transform["workAssignment"]["baseRemuneration"]["effectiveDate"] == "2026-05-01"
    assert transform["effectiveDateTime"] == "2026-05-01"
    assert transform["eventReasonCode"] == {"codeValue": "Annual Review"}


def test_build_add_additional_remuneration_event():
    body = build_add_additional_remuneration_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        name_code="Bonus",
        rate_amount=5000.0,
        effective_date="2026-06-01",
    )
    additional = body["events"][0]["data"]["transform"]["workAssignment"]["additionalRemunerations"][0]
    assert additional["nameCode"] == {"codeValue": "Bonus"}
    assert additional["rate"]["rateAmount"] == {"amountValue": 5000.0, "currencyCode": "USD"}
    assert additional["effectiveDate"] == "2026-06-01"


def test_build_change_additional_remuneration_event_amount_only():
    body = build_change_additional_remuneration_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        additional_remuneration_item_id="AR-7",
        rate_amount=7500.0,
    )
    additional = body["events"][0]["data"]["transform"]["workAssignment"]["additionalRemunerations"][0]
    assert additional["itemID"] == "AR-7"
    assert additional["rate"]["rateAmount"]["amountValue"] == 7500.0


def test_build_change_additional_remuneration_event_date_only():
    body = build_change_additional_remuneration_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        additional_remuneration_item_id="AR-7",
        effective_date="2026-07-01",
    )
    additional = body["events"][0]["data"]["transform"]["workAssignment"]["additionalRemunerations"][0]
    assert additional["itemID"] == "AR-7"
    assert "rate" not in additional
    assert additional["effectiveDate"] == "2026-07-01"


def test_build_remove_additional_remuneration_event():
    body = build_remove_additional_remuneration_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        additional_remuneration_item_id="AR-7",
    )
    additional = body["events"][0]["data"]["transform"]["workAssignment"]["additionalRemunerations"][0]
    assert additional == {"itemID": "AR-7"}


# ------------- builder tests -------------


@pytest.mark.asyncio
async def test_build_tools_returns_four_tools():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_compensation_tools(conn, cache)
    assert len(tools) == 4
    assert {t.name for t in tools} == {
        "change_employee_base_pay",
        "add_employee_additional_remuneration",
        "change_employee_additional_remuneration",
        "remove_employee_additional_remuneration",
    }


@pytest.mark.asyncio
async def test_tool_invocation_builds_envelope_and_posts():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_compensation_tools(conn, cache)
    tool = next(t for t in tools if t.name == "change_employee_base_pay")

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {"confirmMessage": {"requestID": "REQ-9"}}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_compensation_tools.build_mtls_httpx_client", fake_client):
        result = await tool.ainvoke({
            "associate_oid": "G3ABC",
            "work_assignment_item_id": "WA-1",
            "new_annual_amount": 120000.0,
            "effective_date": "2026-05-01",
        })

    assert result == {"confirmMessage": {"requestID": "REQ-9"}}
    call = client.request.call_args
    posted_url = call.kwargs.get("url") or call.args[1]
    assert PATH_CHANGE_BASE in posted_url


@pytest.mark.asyncio
async def test_post_event_401_retries_with_fresh_token():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_compensation_tools(conn, cache)
    tool = next(t for t in tools if t.name == "change_employee_base_pay")

    unauthorized = MagicMock(spec=httpx.Response)
    unauthorized.status_code = 401
    unauthorized.json.return_value = {"error": "expired"}

    success = MagicMock(spec=httpx.Response)
    success.status_code = 200
    success.json.return_value = {"confirmMessage": {"requestID": "REQ-2"}}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.side_effect = [unauthorized, success]

    async def fake_refresh(conn_arg, *, force=False):
        assert force is True
        conn_arg.access_token = "new-token"  # noqa: S105

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_worker_compensation_tools.build_mtls_httpx_client", fake_client), \
         patch("lfx.components.adp.adp_worker_compensation_tools.fetch_token", AsyncMock(side_effect=fake_refresh)):
        await tool.ainvoke({
            "associate_oid": "G3ABC",
            "work_assignment_item_id": "WA-1",
            "new_annual_amount": 120000.0,
        })

    assert client.request.await_count == 2


def test_expected_paths_constants():
    assert PATH_CHANGE_BASE == "/events/hr/v1/worker.work-assignment.base-remuneration.change"
    assert PATH_ADD_ADDITIONAL == "/events/hr/v1/worker.work-assignment.additional-remuneration.add"
    assert PATH_CHANGE_ADDITIONAL == "/events/hr/v1/worker.work-assignment.additional-remuneration.change"
    assert PATH_REMOVE_ADDITIONAL == "/events/hr/v1/worker.work-assignment.additional-remuneration.remove"
