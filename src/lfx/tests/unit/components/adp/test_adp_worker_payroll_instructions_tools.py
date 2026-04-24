"""Tests for ADPWorkerPayrollInstructionsToolsComponent."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lfx.components.adp.adp_worker_payroll_instructions_tools import (
    ADPWorkerPayrollInstructionsToolsComponent,
    PATH_CHANGE,
    PATH_DETAIL,
    PATH_LIST,
    PATH_START,
    PATH_STOP,
    build_general_deduction_event,
)


def _make_component(connection, *, enable_mutations: bool = False) -> ADPWorkerPayrollInstructionsToolsComponent:
    return ADPWorkerPayrollInstructionsToolsComponent(connection=connection, enable_mutations=enable_mutations)


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
    # The change transform should NOT repeat deductionCode — it's pinned in context.
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
    # Per HAR sample, stop omits payrollGroupCode.
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


# ------------- read path routing -------------


@pytest.mark.asyncio
async def test_read_tool_list_path(adp_connection):
    c = _make_component(adp_connection)
    mock_call = AsyncMock(return_value={"workerPayrollInstructions": []})

    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        read_tool = next(t for t in tools if t.name == "get_worker_payroll_instructions")
        await read_tool.ainvoke({"associate_oid": "G3ABC"})

    assert mock_call.call_args.kwargs["path"] == "/payroll/v1/workers/G3ABC/payroll-instructions"


@pytest.mark.asyncio
async def test_read_tool_detail_path(adp_connection):
    c = _make_component(adp_connection)
    mock_call = AsyncMock(return_value={})

    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        read_tool = next(t for t in tools if t.name == "get_worker_payroll_instructions")
        await read_tool.ainvoke({"associate_oid": "G3ABC", "payroll_instruction_id": "PI-9"})

    assert mock_call.call_args.kwargs["path"] == "/payroll/v1/workers/G3ABC/payroll-instructions/PI-9"


# ------------- POST helper -------------


@pytest.mark.asyncio
async def test_call_401_retries(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(200, json={"ok": True}),
    ]
    mock_exec = AsyncMock(side_effect=responses)
    mock_client = MagicMock()

    @asynccontextmanager
    async def fake_build_client(_conn, *, timeout=30):
        yield mock_client

    async def fake_force_refresh(conn, *, force=False):
        assert force is True
        conn.access_token = "refreshed"  # noqa: S105

    with patch(
        "lfx.components.adp.adp_worker_payroll_instructions_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=mock_exec), patch(
        "lfx.components.adp.adp_worker_payroll_instructions_tools.fetch_token",
        new=AsyncMock(side_effect=fake_force_refresh),
    ):
        await c._call(adp_connection, method="POST", path=PATH_START, body={"events": []})

    assert mock_exec.call_count == 2
    assert mock_exec.call_args_list[1].kwargs["headers"]["Authorization"] == "Bearer refreshed"


# ------------- tool registration + routing -------------


@pytest.mark.asyncio
async def test_build_tools_disabled_returns_only_read(adp_connection):
    c = _make_component(adp_connection, enable_mutations=False)
    tools = await c.build_tools()
    assert len(tools) == 1
    assert tools[0].name == "get_worker_payroll_instructions"


@pytest.mark.asyncio
async def test_build_tools_enabled_returns_both(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    tools = await c.build_tools()

    assert {t.name for t in tools} == {
        "get_worker_payroll_instructions",
        "manage_worker_general_deduction",
    }


@pytest.mark.asyncio
async def test_manage_tool_start_routes_to_start_path(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"confirmMessage": {"requestID": "REQ-1"}})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        tool = next(t for t in tools if t.name == "manage_worker_general_deduction")
        await tool.ainvoke(
            {
                "action": "start",
                "associate_oid": "G3ABC",
                "payroll_file_number": "1001",
                "payroll_agreement_id": "AGR-1",
                "effective_date": "2020-01-01",
                "payroll_group_code": "938",
                "deduction_code": "H",
                "deduction_rate_value": 200,
                "deduction_rate_currency": "USD",
            },
        )

    assert mock_post.call_args.kwargs["path"] == PATH_START


@pytest.mark.asyncio
async def test_manage_tool_change_routes_to_change_path(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"confirmMessage": {"requestID": "REQ-2"}})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        tool = next(t for t in tools if t.name == "manage_worker_general_deduction")
        await tool.ainvoke(
            {
                "action": "change",
                "associate_oid": "G3ABC",
                "payroll_file_number": "1001",
                "payroll_agreement_id": "AGR-1",
                "effective_date": "2020-05-08",
                "payroll_group_code": "94N",
                "item_id": "ITEM-1",
                "deduction_code": "M",
                "deduction_rate_value": 20,
            },
        )

    assert mock_post.call_args.kwargs["path"] == PATH_CHANGE


@pytest.mark.asyncio
async def test_manage_tool_stop_routes_to_stop_path(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={"confirmMessage": {"requestID": "REQ-3"}})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        tool = next(t for t in tools if t.name == "manage_worker_general_deduction")
        await tool.ainvoke(
            {
                "action": "stop",
                "associate_oid": "G3ABC",
                "payroll_file_number": "1001",
                "payroll_agreement_id": "AGR-1",
                "effective_date": "2019-04-18",
                "item_id": "ITEM-1",
            },
        )

    assert mock_post.call_args.kwargs["path"] == PATH_STOP


@pytest.mark.asyncio
async def test_manage_tool_change_without_item_id_returns_validation_error(adp_connection):
    c = _make_component(adp_connection, enable_mutations=True)
    mock_post = AsyncMock()

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        tool = next(t for t in tools if t.name == "manage_worker_general_deduction")
        result = await tool.ainvoke(
            {
                "action": "change",
                "associate_oid": "G3ABC",
                "payroll_file_number": "1001",
                "payroll_agreement_id": "AGR-1",
                "effective_date": "2020-05-08",
                "payroll_group_code": "94N",
                "deduction_code": "M",
            },
        )

    assert result["status_code"] == 422
    assert "item_id" in result["error"]
    mock_post.assert_not_called()


def test_expected_path_constants():
    assert PATH_LIST == "/payroll/v1/workers/{aoid}/payroll-instructions"
    assert PATH_DETAIL == "/payroll/v1/workers/{aoid}/payroll-instructions/{payroll_instruction_id}"
    assert PATH_START == "/events/payroll/v2/worker-general-deduction-instruction.start"
    assert PATH_CHANGE == "/events/payroll/v2/worker-general-deduction-instruction.change"
    assert PATH_STOP == "/events/payroll/v2/worker-general-deduction-instruction.stop"
