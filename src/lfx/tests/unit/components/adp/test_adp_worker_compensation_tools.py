"""Tests for ADPWorkerCompensationToolsComponent."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lfx.components.adp.adp_worker_compensation_tools import (
    ADPWorkerCompensationToolsComponent,
    PATH_ADD_ADDITIONAL,
    PATH_CHANGE_ADDITIONAL,
    PATH_CHANGE_BASE,
    PATH_REMOVE_ADDITIONAL,
    build_add_additional_remuneration_event,
    build_change_additional_remuneration_event,
    build_change_base_pay_event,
    build_remove_additional_remuneration_event,
)


def _make_component(connection, *, enable_mutations: bool = False) -> ADPWorkerCompensationToolsComponent:
    return ADPWorkerCompensationToolsComponent(connection=connection, enable_mutations=enable_mutations)


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


# ------------- POST helper -------------


@pytest.mark.asyncio
async def test_post_event_happy_path(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    fake_response = httpx.Response(200, json={"confirmMessage": {"requestID": "REQ-1"}})
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):
        yield mock_client

    with patch(
        "lfx.components.adp.adp_worker_compensation_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=AsyncMock(return_value=fake_response)):
        result = await c._post_event(adp_connection, path=PATH_CHANGE_BASE, body={"events": []})

    assert result == {"confirmMessage": {"requestID": "REQ-1"}}


@pytest.mark.asyncio
async def test_post_event_401_retries_with_fresh_token(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(200, json={"confirmMessage": {"requestID": "REQ-2"}}),
    ]
    mock_exec = AsyncMock(side_effect=responses)
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):
        yield mock_client

    async def fake_force_refresh(conn, *, force=False):
        assert force is True
        conn.access_token = "new-token"  # noqa: S105

    with patch(
        "lfx.components.adp.adp_worker_compensation_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=mock_exec), patch(
        "lfx.components.adp.adp_worker_compensation_tools.fetch_token",
        new=AsyncMock(side_effect=fake_force_refresh),
    ):
        await c._post_event(adp_connection, path=PATH_CHANGE_BASE, body={"events": []})

    assert mock_exec.call_count == 2
    second_headers = mock_exec.call_args_list[1].kwargs["headers"]
    assert second_headers["Authorization"] == "Bearer new-token"


@pytest.mark.asyncio
async def test_post_event_http_error_returns_error_dict(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    fake_response = httpx.Response(400, json={"errorCode": "WA-NOT-FOUND"})
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):
        yield mock_client

    with patch(
        "lfx.components.adp.adp_worker_compensation_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=AsyncMock(return_value=fake_response)):
        result = await c._post_event(adp_connection, path=PATH_CHANGE_BASE, body={"events": []})

    assert result == {"error": {"errorCode": "WA-NOT-FOUND"}, "status_code": 400}


# ------------- gating + tool registration -------------


@pytest.mark.asyncio
async def test_build_tools_disabled_returns_empty(adp_connection):
    c = _make_component(adp_connection, enable_mutations=False)
    tools = await c.build_tools()
    assert tools == []


@pytest.mark.asyncio
async def test_build_tools_enabled_returns_four_tools(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    tools = await c.build_tools()

    assert len(tools) == 4
    assert {t.name for t in tools} == {
        "change_employee_base_pay",
        "add_employee_additional_remuneration",
        "change_employee_additional_remuneration",
        "remove_employee_additional_remuneration",
    }
    for tool in tools:
        assert tool.description
        assert tool.args_schema is not None


@pytest.mark.asyncio
async def test_tool_invocation_builds_envelope_and_calls_helper(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"confirmMessage": {"requestID": "REQ-9"}})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        tool = next(t for t in tools if t.name == "change_employee_base_pay")
        result = await tool.ainvoke(
            {
                "associate_oid": "G3ABC",
                "work_assignment_item_id": "WA-1",
                "new_annual_amount": 120000.0,
                "effective_date": "2026-05-01",
            },
        )

    assert result == {"confirmMessage": {"requestID": "REQ-9"}}
    call = mock_post.call_args
    assert call.kwargs["path"] == PATH_CHANGE_BASE
    body = call.kwargs["body"]
    wa = body["events"][0]["data"]["transform"]["workAssignment"]
    assert wa["baseRemuneration"]["annualRateAmount"]["amountValue"] == 120000.0


def test_expected_paths_constants():
    # Defensive: confirm we haven't accidentally renamed ADP event paths.
    assert PATH_CHANGE_BASE == "/events/hr/v1/worker.work-assignment.base-remuneration.change"
    assert PATH_ADD_ADDITIONAL == "/events/hr/v1/worker.work-assignment.additional-remuneration.add"
    assert PATH_CHANGE_ADDITIONAL == "/events/hr/v1/worker.work-assignment.additional-remuneration.change"
    assert PATH_REMOVE_ADDITIONAL == "/events/hr/v1/worker.work-assignment.additional-remuneration.remove"
