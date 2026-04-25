"""Tests for adp_pay_data_input_tools module-level builders."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_pay_data_input_tools import (
    PATH_MODIFY,
    build_pay_data_input_event,
    build_pay_data_input_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


# ------------- envelope builder -------------


def test_build_event_minimal_regular_hours():
    body = build_pay_data_input_event(
        associate_oid="G3ABC",
        payroll_group_code="94N",
        payroll_file_number="1001",
        earning_inputs=[{"earning_code": "R", "number_of_hours": 80}],
    )
    event = body["events"][0]
    ctx = event["data"]["eventContext"]
    assert ctx == {"payrollGroupCode": {"codeValue": "94N"}}
    payee = event["data"]["transform"]["payDataInput"]["payeePayInputs"][0]
    assert payee["associateOID"] == "G3ABC"
    assert payee["payNumber"] == "1"
    pay_input = payee["payrollProfilePayInputs"][0]["payInputs"][0]
    assert pay_input["earningInputs"][0] == {
        "earningCode": {"codeValue": "R"},
        "numberOfHours": 80,
    }
    assert pay_input["deductionInputs"] == []
    assert pay_input["memoInputs"] == []
    assert pay_input["reportableEarningAndBenefitInputs"] == []
    assert pay_input["taxInputs"] == []
    assert pay_input["_modificationTypeCode"] == "Add"


def test_build_event_append_with_processing_job_id():
    body = build_pay_data_input_event(
        associate_oid="G3ABC",
        payroll_group_code="94N",
        payroll_file_number="1001",
        payroll_processing_job_id="Regular, OT",
        modification_type="Append",
        earning_inputs=[
            {"earning_code": "R", "number_of_hours": 80},
            {"earning_code": "O", "number_of_hours": 10},
        ],
    )
    ctx = body["events"][0]["data"]["eventContext"]
    assert ctx["payrollProcessingJobID"] == "Regular, OT"
    payee = body["events"][0]["data"]["transform"]["payDataInput"]["payeePayInputs"][0]
    pay_input = payee["payrollProfilePayInputs"][0]["payInputs"][0]
    assert pay_input["_modificationTypeCode"] == "Append"
    assert len(pay_input["earningInputs"]) == 2
    assert pay_input["earningInputs"][1]["earningCode"]["codeValue"] == "O"


def test_build_event_deduction():
    body = build_pay_data_input_event(
        associate_oid="G3ABC",
        payroll_group_code="94N",
        payroll_file_number="1001",
        deduction_inputs=[{"deduction_code": "1", "rate_value": 25}],
    )
    pay_input = (
        body["events"][0]["data"]["transform"]["payDataInput"]
        ["payeePayInputs"][0]["payrollProfilePayInputs"][0]["payInputs"][0]
    )
    assert pay_input["deductionInputs"][0] == {
        "deductionCode": {"codeValue": "1"},
        "deductionRate": {"rateValue": 25, "currencyCode": "USD"},
    }


def test_build_event_memo_with_cancel_auto_pay():
    body = build_pay_data_input_event(
        associate_oid="G3ABC",
        payroll_group_code="94N",
        payroll_file_number="1001",
        cancel_automatic_pay_indicator=True,
        memo_inputs=[{"memo_code": "GTL", "amount_value": 200}],
    )
    pay_input = (
        body["events"][0]["data"]["transform"]["payDataInput"]
        ["payeePayInputs"][0]["payrollProfilePayInputs"][0]["payInputs"][0]
    )
    assert pay_input["cancelAutomaticPayIndicator"] == "true"
    assert pay_input["memoInputs"][0] == {
        "memoCode": {"codeValue": "GTL"},
        "memoAmount": {"amountValue": 200, "currencyCode": "USD"},
    }


def test_build_event_tips_with_rate_and_reportable():
    body = build_pay_data_input_event(
        associate_oid="G3ABC",
        payroll_group_code="94N",
        payroll_file_number="1001",
        earning_inputs=[{"earning_code": "T", "rate_value": 150}],
        reportable_earning_benefit_inputs=[{"code": "T", "amount_value": 350}],
    )
    pay_input = (
        body["events"][0]["data"]["transform"]["payDataInput"]
        ["payeePayInputs"][0]["payrollProfilePayInputs"][0]["payInputs"][0]
    )
    # HAR sample 13 shows earning rate with no currencyCode — mirror exactly.
    assert pay_input["earningInputs"][0]["rate"] == {"rateValue": 150}
    assert pay_input["reportableEarningAndBenefitInputs"][0] == {
        "reportableEarningAndBenefitCode": {"codeValue": "T"},
        "reportableEarningAndBenefitAmount": {"amountValue": 350, "currencyCode": "USD"},
    }


def test_build_event_shift_code_maps_to_configuration_tags():
    body = build_pay_data_input_event(
        associate_oid="G3ABC",
        payroll_group_code="94N",
        payroll_file_number="1001",
        earning_inputs=[{"earning_code": "R", "number_of_hours": 20, "shift_code": "2"}],
    )
    earning = (
        body["events"][0]["data"]["transform"]["payDataInput"]
        ["payeePayInputs"][0]["payrollProfilePayInputs"][0]["payInputs"][0]["earningInputs"][0]
    )
    assert earning["configurationTags"] == [{"tagCode": "Shift Code", "tagValues": ["2"]}]


def test_build_event_flsa_week_number():
    body = build_pay_data_input_event(
        associate_oid="G3ABC",
        payroll_group_code="94N",
        payroll_file_number="1001",
        earning_inputs=[
            {"earning_code": "R", "number_of_hours": 40, "earned_pay_period_week_number": 1},
            {"earning_code": "R", "number_of_hours": 40, "earned_pay_period_week_number": 2},
        ],
    )
    earnings = (
        body["events"][0]["data"]["transform"]["payDataInput"]
        ["payeePayInputs"][0]["payrollProfilePayInputs"][0]["payInputs"][0]["earningInputs"]
    )
    assert earnings[0]["earnedPayPeriodWeekNumber"] == 1
    assert earnings[1]["earnedPayPeriodWeekNumber"] == 2


def test_build_event_tax_cycle():
    body = build_pay_data_input_event(
        associate_oid="G3ABC",
        payroll_group_code="94N",
        payroll_file_number="1001",
        earning_inputs=[{"earning_code": "B", "earnings_amount": 5000}],
        tax_inputs=[{"tax_cycle_code": "B"}],
    )
    pay_input = (
        body["events"][0]["data"]["transform"]["payDataInput"]
        ["payeePayInputs"][0]["payrollProfilePayInputs"][0]["payInputs"][0]
    )
    assert pay_input["earningInputs"][0]["earningsAmount"] == {
        "amountValue": 5000,
        "currencyCode": "USD",
    }
    assert pay_input["taxInputs"][0] == {"taxCycleCode": {"codeValue": "B"}}


def test_build_event_additional_fields_escape():
    body = build_pay_data_input_event(
        associate_oid="G3ABC",
        payroll_group_code="94N",
        payroll_file_number="1001",
        additional_fields={"someRareField": "X"},
    )
    pay_input = (
        body["events"][0]["data"]["transform"]["payDataInput"]
        ["payeePayInputs"][0]["payrollProfilePayInputs"][0]["payInputs"][0]
    )
    assert pay_input["someRareField"] == "X"


def test_build_event_pay_number_override():
    body = build_pay_data_input_event(
        associate_oid="G3ABC",
        payroll_group_code="94N",
        payroll_file_number="1001",
        pay_number="2",
        earning_inputs=[{"earning_code": "R", "number_of_hours": 40}],
    )
    payee = body["events"][0]["data"]["transform"]["payDataInput"]["payeePayInputs"][0]
    assert payee["payNumber"] == "2"


# ------------- POST helper -------------


@pytest.mark.asyncio
async def test_post_event_happy_path():
    conn = _make_connection()
    fake_response = httpx.Response(200, json={"confirmMessage": {"requestID": "REQ-1"}})
    client = MagicMock()
    client.request = AsyncMock(return_value=fake_response)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_pay_data_input_tools.build_mtls_httpx_client", fake_client):
        from lfx.components.adp.adp_pay_data_input_tools import _post_event
        result = await _post_event(conn, path=PATH_MODIFY, body={"events": []})

    assert result == {"confirmMessage": {"requestID": "REQ-1"}}


@pytest.mark.asyncio
async def test_post_event_401_retries_with_fresh_token():
    conn = _make_connection()
    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(200, json={"confirmMessage": {"requestID": "REQ-2"}}),
    ]
    client = MagicMock()
    client.request = AsyncMock(side_effect=responses)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    async def fake_force_refresh(c, *, force=False):
        assert force is True
        c.access_token = "new-token"  # noqa: S105

    with patch(
        "lfx.components.adp.adp_pay_data_input_tools.build_mtls_httpx_client", fake_client,
    ), patch(
        "lfx.components.adp.adp_pay_data_input_tools.fetch_token",
        new=AsyncMock(side_effect=fake_force_refresh),
    ):
        from lfx.components.adp.adp_pay_data_input_tools import _post_event
        await _post_event(conn, path=PATH_MODIFY, body={"events": []})

    assert client.request.call_count == 2
    second_headers = client.request.call_args_list[1].kwargs["headers"]
    assert second_headers["Authorization"] == "Bearer new-token"


@pytest.mark.asyncio
async def test_post_event_http_error_returns_error_dict():
    conn = _make_connection()
    fake_response = httpx.Response(400, json={"errorCode": "INVALID"})
    client = MagicMock()
    client.request = AsyncMock(return_value=fake_response)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_pay_data_input_tools.build_mtls_httpx_client", fake_client):
        from lfx.components.adp.adp_pay_data_input_tools import _post_event
        result = await _post_event(conn, path=PATH_MODIFY, body={"events": []})

    assert result == {"error": {"errorCode": "INVALID"}, "status_code": 400}


# ------------- gating + tool registration -------------


@pytest.mark.asyncio
async def test_build_tools_disabled_returns_empty():
    tools = build_pay_data_input_tools(_make_connection(), RequestCache(ttl_seconds=30, max_entries=8))
    assert tools == []


@pytest.mark.asyncio
async def test_build_tools_enabled_returns_one_tool():
    tools = build_pay_data_input_tools(
        _make_connection(), RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
    )
    assert len(tools) == 1
    tool = tools[0]
    assert tool.name == "submit_pay_data_input"
    assert tool.description
    assert tool.args_schema is not None


@pytest.mark.asyncio
async def test_tool_invocation_builds_envelope_and_posts():
    conn = _make_connection()
    mock_post = AsyncMock(return_value={"confirmMessage": {"requestID": "REQ-9"}})

    with patch(
        "lfx.components.adp.adp_pay_data_input_tools._post_event", new=mock_post,
    ):
        tools = build_pay_data_input_tools(
            conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
        )
        tool = tools[0]
        result = await tool.ainvoke(
            {
                "associate_oid": "G3ABC",
                "payroll_group_code": "94N",
                "payroll_file_number": "1001",
                "payroll_processing_job_id": "Regular, OT",
                "earning_inputs": [
                    {"earning_code": "R", "number_of_hours": 80},
                    {"earning_code": "O", "number_of_hours": 10},
                ],
            },
        )

    assert result == {"confirmMessage": {"requestID": "REQ-9"}}
    call = mock_post.call_args
    assert call.kwargs["path"] == PATH_MODIFY
    body = call.kwargs["body"]
    payee = body["events"][0]["data"]["transform"]["payDataInput"]["payeePayInputs"][0]
    assert payee["associateOID"] == "G3ABC"
    earnings = payee["payrollProfilePayInputs"][0]["payInputs"][0]["earningInputs"]
    assert len(earnings) == 2
    assert earnings[0]["earningCode"]["codeValue"] == "R"
    assert earnings[1]["numberOfHours"] == 10


def test_expected_path_constant():
    assert PATH_MODIFY == "/events/payroll/v1/pay-data-input.modify"
