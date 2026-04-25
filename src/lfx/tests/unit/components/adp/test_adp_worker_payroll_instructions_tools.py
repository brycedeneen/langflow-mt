"""Tests for adp_worker_payroll_instructions_tools — build_worker_payroll_instructions_tools builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_worker_payroll_instructions_tools import (
    PATH_CHANGE,
    PATH_DETAIL,
    PATH_LIST,
    PATH_START,
    PATH_STOP,
    build_general_deduction_event,
    build_worker_payroll_instructions_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


# ------------- envelope builder: start -------------


def test_build_start_event_with_goal():
    body = build_general_deduction_event(
        action="start",
        associate_oid="G3ZNHFD4527JV1P3",
        payroll_file_number="9656",
        payroll_agreement_id="26849471_194737",
        effective_date="2019-05-15",
        payroll_group_code="938",
        payroll_group_short_name="938",
        deduction_code="D",
        deduction_rate_value=20,
        deduction_rate_currency="USD",
        deduction_goal={"goal_limit_amount": 500, "goal_id": "2", "goal_balance_amount": 300},
    )
    event = body["events"][0]
    ctx_pi = event["data"]["eventContext"]["payrollInstruction"]
    assert ctx_pi["payrollFileNumber"] == "9656"
    assert ctx_pi["payrollAgreementID"] == "26849471_194737"
    assert ctx_pi["payrollGroupCode"] == {"codeValue": "938", "shortName": "938"}
    assert "itemID" not in ctx_pi
    assert "generalDeductionInstruction" not in ctx_pi

    transform = event["data"]["transform"]
    assert transform["effectiveDateTime"] == "2019-05-15"
    gdi = transform["payrollInstruction"]["generalDeductionInstruction"]
    assert gdi["deductionCode"] == {"codeValue": "D"}
    assert gdi["deductionRate"] == {"rateValue": 20, "currencyCode": "USD"}
    assert gdi["deductionGoal"] == {
        "goalLimitAmount": {"amountValue": 500},
        "goalID": "2",
        "goalBalanceAmount": {"amountValue": 300},
    }


def test_build_start_event_no_goal_no_inactive():
    body = build_general_deduction_event(
        action="start",
        associate_oid="G3ABC",
        payroll_file_number="12345",
        payroll_agreement_id="39297793_1317",
        effective_date="2019-04-18",
        payroll_group_code="94N",
        deduction_code="L",
        deduction_rate_value=111,
        deduction_rate_currency="USD",
    )
    gdi = body["events"][0]["data"]["transform"]["payrollInstruction"]["generalDeductionInstruction"]
    assert "deductionGoal" not in gdi
    assert "inactiveIndicator" not in gdi


def test_build_start_event_with_inactive_indicator():
    body = build_general_deduction_event(
        action="start",
        associate_oid="G3ABC",
        payroll_file_number="1001",
        payroll_agreement_id="AGR-1",
        effective_date="2020-06-15",
        payroll_group_code="938",
        deduction_code="H",
        deduction_rate_value="",
        deduction_rate_currency="USD",
        deduction_goal={"goal_limit_amount": "500", "goal_id": "6", "goal_balance_amount": "50"},
        inactive_indicator=True,
    )
    gdi = body["events"][0]["data"]["transform"]["payrollInstruction"]["generalDeductionInstruction"]
    assert gdi["inactiveIndicator"] is True
    assert gdi["deductionRate"] == {"rateValue": "", "currencyCode": "USD"}


# ------------- envelope builder: change -------------


def test_build_change_event_pins_context_deduction_code():
    body = build_general_deduction_event(
        action="change",
        associate_oid="G3ABC",
        payroll_file_number="1001",
        payroll_agreement_id="AGR-1",
        effective_date="2020-05-08",
        payroll_group_code="94N",
        payroll_group_short_name="94N",
        item_id="169749147863_1",
        deduction_code="M",
        deduction_rate_value="20",
        inactive_indicator=True,
    )
    event = body["events"][0]
    ctx_pi = event["data"]["eventContext"]["payrollInstruction"]
    assert ctx_pi["itemID"] == "169749147863_1"
    assert ctx_pi["generalDeductionInstruction"] == {"deductionCode": {"codeValue": "M"}}

    gdi = event["data"]["transform"]["payrollInstruction"]["generalDeductionInstruction"]
    assert "deductionCode" not in gdi
    assert gdi["inactiveIndicator"] is True
    assert gdi["deductionRate"] == {"rateValue": "20"}


def test_build_change_event_requires_item_id():
    with pytest.raises(ValueError, match="requires item_id"):
        build_general_deduction_event(
            action="change",
            associate_oid="G3ABC",
            payroll_file_number="1001",
            payroll_agreement_id="AGR-1",
            effective_date="2020-05-08",
            payroll_group_code="94N",
            deduction_code="M",
            deduction_rate_value=20,
        )


def test_build_change_event_requires_deduction_code():
    with pytest.raises(ValueError, match="requires deduction_code"):
        build_general_deduction_event(
            action="change",
            associate_oid="G3ABC",
            payroll_file_number="1001",
            payroll_agreement_id="AGR-1",
            effective_date="2020-05-08",
            payroll_group_code="94N",
            item_id="ITEM-1",
            deduction_rate_value=20,
        )


# ------------- envelope builder: stop -------------


def test_build_stop_event_minimal():
    body = build_general_deduction_event(
        action="stop",
        associate_oid="G3ABC",
        payroll_file_number="1001",
        payroll_agreement_id="AGR-1",
        effective_date="2019-04-18",
        item_id="169734365871_1",
    )
    event = body["events"][0]
    ctx_pi = event["data"]["eventContext"]["payrollInstruction"]
    assert ctx_pi["itemID"] == "169734365871_1"
    assert ctx_pi["generalDeductionInstruction"] == {}
    assert "payrollGroupCode" not in ctx_pi

    transform = event["data"]["transform"]
    assert transform == {"effectiveDateTime": "2019-04-18"}


def test_build_stop_event_requires_item_id():
    with pytest.raises(ValueError, match="requires item_id"):
        build_general_deduction_event(
            action="stop",
            associate_oid="G3ABC",
            payroll_file_number="1001",
            payroll_agreement_id="AGR-1",
            effective_date="2019-04-18",
        )


# ------------- builder tests -------------


@pytest.mark.asyncio
async def test_build_tools_returns_two_tools():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    tools = build_worker_payroll_instructions_tools(conn, cache)
    assert {t.name for t in tools} == {
        "get_worker_payroll_instructions",
        "manage_worker_general_deduction",
    }


@pytest.mark.asyncio
async def test_read_tool_list_path():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {"workerPayrollInstructions": []}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = {t.name: t for t in build_worker_payroll_instructions_tools(conn, cache)}

    with patch("lfx.components.adp.adp_worker_payroll_instructions_tools.build_mtls_httpx_client", fake_client):
        await tools["get_worker_payroll_instructions"].ainvoke({"associate_oid": "G3ABC"})

    called_url = client.request.call_args.kwargs.get("url") or client.request.call_args.args[1]
    assert called_url.endswith("/payroll/v1/workers/G3ABC/payroll-instructions")


@pytest.mark.asyncio
async def test_read_tool_detail_path():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = {t.name: t for t in build_worker_payroll_instructions_tools(conn, cache)}

    with patch("lfx.components.adp.adp_worker_payroll_instructions_tools.build_mtls_httpx_client", fake_client):
        await tools["get_worker_payroll_instructions"].ainvoke({
            "associate_oid": "G3ABC", "payroll_instruction_id": "PI-9",
        })

    called_url = client.request.call_args.kwargs.get("url") or client.request.call_args.args[1]
    assert called_url.endswith("/payroll/v1/workers/G3ABC/payroll-instructions/PI-9")


@pytest.mark.asyncio
async def test_manage_tool_start_routes_to_start_path():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {"confirmMessage": {"requestID": "REQ-1"}}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.return_value = response

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = {t.name: t for t in build_worker_payroll_instructions_tools(conn, cache)}

    with patch("lfx.components.adp.adp_worker_payroll_instructions_tools.build_mtls_httpx_client", fake_client):
        await tools["manage_worker_general_deduction"].ainvoke({
            "action": "start",
            "associate_oid": "G3ABC",
            "payroll_file_number": "1001",
            "payroll_agreement_id": "AGR-1",
            "effective_date": "2020-01-01",
            "payroll_group_code": "938",
            "deduction_code": "H",
            "deduction_rate_value": 200,
            "deduction_rate_currency": "USD",
        })

    posted_url = client.request.call_args.kwargs.get("url") or client.request.call_args.args[1]
    assert PATH_START in posted_url


@pytest.mark.asyncio
async def test_manage_tool_change_without_item_id_returns_validation_error():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    client = AsyncMock(spec=httpx.AsyncClient)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = {t.name: t for t in build_worker_payroll_instructions_tools(conn, cache)}

    with patch("lfx.components.adp.adp_worker_payroll_instructions_tools.build_mtls_httpx_client", fake_client):
        result = await tools["manage_worker_general_deduction"].ainvoke({
            "action": "change",
            "associate_oid": "G3ABC",
            "payroll_file_number": "1001",
            "payroll_agreement_id": "AGR-1",
            "effective_date": "2020-05-08",
            "payroll_group_code": "94N",
            "deduction_code": "M",
        })

    assert result["status_code"] == 422
    assert "item_id" in result["error"]
    client.request.assert_not_called()


@pytest.mark.asyncio
async def test_call_401_retries():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)

    unauthorized = MagicMock(spec=httpx.Response)
    unauthorized.status_code = 401
    unauthorized.json.return_value = {"error": "expired"}

    success = MagicMock(spec=httpx.Response)
    success.status_code = 200
    success.json.return_value = {"ok": True}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.request.side_effect = [unauthorized, success]

    async def fake_refresh(conn_arg, *, force=False):
        assert force is True
        conn_arg.access_token = "refreshed"  # noqa: S105

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    tools = {t.name: t for t in build_worker_payroll_instructions_tools(conn, cache)}

    with patch("lfx.components.adp.adp_worker_payroll_instructions_tools.build_mtls_httpx_client", fake_client), \
         patch("lfx.components.adp.adp_worker_payroll_instructions_tools.fetch_token",
               AsyncMock(side_effect=fake_refresh)):
        await tools["get_worker_payroll_instructions"].ainvoke({"associate_oid": "G3ABC"})

    assert client.request.await_count == 2
    assert client.request.call_args_list[1].kwargs["headers"]["Authorization"] == "Bearer refreshed"


def test_expected_path_constants():
    assert PATH_LIST == "/payroll/v1/workers/{aoid}/payroll-instructions"
    assert PATH_DETAIL == "/payroll/v1/workers/{aoid}/payroll-instructions/{payroll_instruction_id}"
    assert PATH_START == "/events/payroll/v2/worker-general-deduction-instruction.start"
    assert PATH_CHANGE == "/events/payroll/v2/worker-general-deduction-instruction.change"
    assert PATH_STOP == "/events/payroll/v2/worker-general-deduction-instruction.stop"
