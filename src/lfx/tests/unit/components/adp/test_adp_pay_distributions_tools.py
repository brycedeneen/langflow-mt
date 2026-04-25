"""Tests for adp_pay_distributions_tools module-level builders."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_pay_distributions_tools import (
    PATH_CHANGE,
    PATH_DETAIL,
    PATH_LIST,
    build_change_pay_distribution_event,
    build_pay_distributions_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


# ------------- envelope builder -------------


def test_build_add_dd_percentage_net():
    body = build_change_pay_distribution_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        effective_date="2024-05-31",
        distribution_instructions=[
            {
                "distribution_percentage": 50,
                "account_number": "123456778",
                "account_type_code": "x",
                "routing_transit_id": "823456789",
            },
        ],
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {
        "worker": {"associateOID": "G3ABC"},
        "payDistribution": {"itemID": "WA-1"},
    }
    transform = event["data"]["transform"]
    assert transform["effectiveDateTime"] == "2024-05-31"
    instruction = transform["payDistribution"]["distributionInstructions"][0]
    assert instruction["distributionPercentage"] == "50"
    assert instruction["depositAccount"] == {
        "financialAccount": {"accountNumber": "123456778", "typeCode": {"codeValue": "x"}},
        "financialParty": {"routingTransitID": {"idValue": "823456789"}},
    }
    assert "itemID" not in instruction


def test_build_update_dd_partial_net_with_item_id():
    body = build_change_pay_distribution_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        effective_date="2024-05-31",
        distribution_instructions=[
            {
                "item_id": "9201158803848_1",
                "distribution_amount": 700,
                "account_number": "123456778",
                "account_type_code": "W",
                "routing_transit_id": "823456789",
            },
        ],
    )
    instruction = body["events"][0]["data"]["transform"]["payDistribution"]["distributionInstructions"][0]
    assert instruction["itemID"] == "9201158803848_1"
    assert instruction["distributionAmount"] == {"amountValue": "700"}


def test_build_update_dd_remaining_balance():
    body = build_change_pay_distribution_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        effective_date="2024-05-31",
        distribution_instructions=[
            {
                "item_id": "9201158803848_1",
                "remaining_balance_indicator": True,
                "account_number": "4172678660111",
                "account_type_code": "Z",
                "routing_transit_id": "031207607",
            },
        ],
    )
    instruction = body["events"][0]["data"]["transform"]["payDistribution"]["distributionInstructions"][0]
    assert instruction["remainingBalanceIndicator"] is True


def test_build_inactivate_instruction():
    body = build_change_pay_distribution_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        effective_date="2024-05-31",
        distribution_instructions=[
            {
                "instruction_status_code": "I",
                "instruction_status_short_name": "Inactive",
                "remaining_balance_indicator": True,
                "account_number": "123456778",
                "account_type_code": "w",
                "account_type_short_name": "w",
                "routing_transit_id": "823456789",
            },
        ],
    )
    instruction = body["events"][0]["data"]["transform"]["payDistribution"]["distributionInstructions"][0]
    assert instruction["instructionStatusCode"] == {"codeValue": "I", "shortName": "Inactive"}
    assert instruction["depositAccount"]["financialAccount"]["typeCode"] == {
        "codeValue": "w",
        "shortName": "w",
    }


def test_build_remove_all_empty_list():
    body = build_change_pay_distribution_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        effective_date="2024-05-31",
        distribution_instructions=[],
    )
    transform = body["events"][0]["data"]["transform"]
    assert transform["payDistribution"] == {"distributionInstructions": []}


def test_build_canadian_financial_party():
    body = build_change_pay_distribution_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        effective_date="2024-05-31",
        distribution_instructions=[
            {
                "distribution_amount": 300,
                "account_number": "11118167",
                "account_type_code": "DP1",
                "account_type_short_name": "DEPOSIT ACCT1",
                "financial_party_scheme_code": "260",
                "branch_name_code": "58956",
            },
        ],
    )
    instruction = body["events"][0]["data"]["transform"]["payDistribution"]["distributionInstructions"][0]
    fp = instruction["depositAccount"]["financialParty"]
    assert fp == {
        "financialPartyID": {"schemeCode": {"codeValue": "260"}},
        "branchNameCode": {"codeValue": "58956"},
    }
    assert instruction["depositAccount"]["financialAccount"]["typeCode"] == {
        "codeValue": "DP1",
        "shortName": "DEPOSIT ACCT1",
    }


def test_build_multiple_instructions_in_one_call():
    body = build_change_pay_distribution_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        effective_date="2024-05-31",
        distribution_instructions=[
            {
                "item_id": "9201158803848_1",
                "distribution_amount": 300,
                "account_number": "123456778",
                "account_type_code": "Z",
                "routing_transit_id": "823456789",
            },
            {
                "item_id": "9201158803848_1",
                "distribution_amount": 500,
                "account_number": "123456778",
                "account_type_code": "Y",
                "routing_transit_id": "823456789",
            },
        ],
    )
    instructions = body["events"][0]["data"]["transform"]["payDistribution"]["distributionInstructions"]
    assert len(instructions) == 2
    assert instructions[0]["distributionAmount"]["amountValue"] == "300"
    assert instructions[1]["distributionAmount"]["amountValue"] == "500"


def test_build_additional_fields_merged_into_pay_distribution():
    body = build_change_pay_distribution_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        distribution_instructions=[],
        additional_fields={"someRareKey": "val"},
    )
    pd = body["events"][0]["data"]["transform"]["payDistribution"]
    assert pd["someRareKey"] == "val"


def test_build_omits_effective_date_when_missing():
    body = build_change_pay_distribution_event(
        associate_oid="G3ABC",
        work_assignment_item_id="WA-1",
        distribution_instructions=[],
    )
    transform = body["events"][0]["data"]["transform"]
    assert "effectiveDateTime" not in transform


# ------------- _fetch_pay_distributions helper -------------


@pytest.mark.asyncio
async def test_fetch_pay_distributions_happy_path():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    fake_response = httpx.Response(200, json={"payDistributions": []})
    client = MagicMock()
    client.request = AsyncMock(return_value=fake_response)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_pay_distributions_tools.build_mtls_httpx_client", fake_client):
        from lfx.components.adp.adp_pay_distributions_tools import _fetch_pay_distributions
        result = await _fetch_pay_distributions(
            conn, path=PATH_LIST.format(aoid="G3ABC"), request_cache=cache,
        )

    assert result == {"payDistributions": []}


@pytest.mark.asyncio
async def test_fetch_pay_distributions_401_retries():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    client = MagicMock()

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    async def fake_force_refresh(c, *, force=False):
        assert force is True
        c.access_token = "refreshed"  # noqa: S105

    with patch(
        "lfx.components.adp.adp_pay_distributions_tools.build_mtls_httpx_client", fake_client,
    ), patch(
        "lfx.components.adp.adp_pay_distributions_tools.cached_get_json",
        new=AsyncMock(side_effect=[
            {"status_code": 401, "error": "expired"},
            {"payDistributions": []},
        ]),
    ), patch(
        "lfx.components.adp.adp_pay_distributions_tools.fetch_token",
        new=AsyncMock(side_effect=fake_force_refresh),
    ):
        from lfx.components.adp.adp_pay_distributions_tools import _fetch_pay_distributions
        result = await _fetch_pay_distributions(
            conn, path=PATH_LIST.format(aoid="G3ABC"), request_cache=cache,
        )

    assert result == {"payDistributions": []}


@pytest.mark.asyncio
async def test_fetch_pay_distributions_http_error_returns_dict():
    conn = _make_connection()
    cache = RequestCache(ttl_seconds=30, max_entries=8)
    client = MagicMock()

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch(
        "lfx.components.adp.adp_pay_distributions_tools.build_mtls_httpx_client", fake_client,
    ), patch(
        "lfx.components.adp.adp_pay_distributions_tools.cached_get_json",
        new=AsyncMock(return_value={"error": {"errorCode": "NOT_FOUND"}, "status_code": 404}),
    ):
        from lfx.components.adp.adp_pay_distributions_tools import _fetch_pay_distributions
        result = await _fetch_pay_distributions(
            conn, path="/payroll/v2/workers/missing/pay-distributions", request_cache=cache,
        )

    assert result == {"error": {"errorCode": "NOT_FOUND"}, "status_code": 404}


# ------------- tool registration + invocation -------------


@pytest.mark.asyncio
async def test_build_tools_disabled_returns_only_read():
    tools = build_pay_distributions_tools(_make_connection(), RequestCache(ttl_seconds=30, max_entries=8))
    assert len(tools) == 1
    assert tools[0].name == "get_worker_pay_distributions"


@pytest.mark.asyncio
async def test_build_tools_enabled_returns_both():
    tools = build_pay_distributions_tools(
        _make_connection(), RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
    )
    assert {t.name for t in tools} == {
        "get_worker_pay_distributions",
        "change_worker_pay_distributions",
    }
    for tool in tools:
        assert tool.description
        assert tool.args_schema is not None


@pytest.mark.asyncio
async def test_read_tool_list_routes_to_list_path():
    conn = _make_connection()
    mock_fetch = AsyncMock(return_value={"payDistributions": []})

    with patch(
        "lfx.components.adp.adp_pay_distributions_tools._fetch_pay_distributions", new=mock_fetch,
    ):
        tools = build_pay_distributions_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        read_tool = next(t for t in tools if t.name == "get_worker_pay_distributions")
        await read_tool.ainvoke({"associate_oid": "G3ABC"})

    assert mock_fetch.call_args.kwargs["path"] == "/payroll/v2/workers/G3ABC/pay-distributions"


@pytest.mark.asyncio
async def test_read_tool_detail_routes_to_detail_path():
    conn = _make_connection()
    mock_fetch = AsyncMock(return_value={})

    with patch(
        "lfx.components.adp.adp_pay_distributions_tools._fetch_pay_distributions", new=mock_fetch,
    ):
        tools = build_pay_distributions_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        read_tool = next(t for t in tools if t.name == "get_worker_pay_distributions")
        await read_tool.ainvoke({"associate_oid": "G3ABC", "pay_distribution_id": "PD-9"})

    assert mock_fetch.call_args.kwargs["path"] == "/payroll/v2/workers/G3ABC/pay-distributions/PD-9"


@pytest.mark.asyncio
async def test_change_tool_builds_envelope_and_posts():
    conn = _make_connection()
    mock_post = AsyncMock(return_value={"confirmMessage": {"requestID": "REQ-9"}})

    with patch("lfx.components.adp.adp_pay_distributions_tools._post_event", new=mock_post):
        tools = build_pay_distributions_tools(
            conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
        )
        change_tool = next(t for t in tools if t.name == "change_worker_pay_distributions")
        result = await change_tool.ainvoke(
            {
                "associate_oid": "G3ABC",
                "work_assignment_item_id": "WA-1",
                "effective_date": "2024-05-31",
                "distribution_instructions": [
                    {
                        "distribution_percentage": 50,
                        "account_number": "123456778",
                        "account_type_code": "x",
                        "routing_transit_id": "823456789",
                    },
                ],
            },
        )

    assert result == {"confirmMessage": {"requestID": "REQ-9"}}
    call = mock_post.call_args
    assert call.kwargs["path"] == PATH_CHANGE
    body = call.kwargs["body"]
    instruction = body["events"][0]["data"]["transform"]["payDistribution"]["distributionInstructions"][0]
    assert instruction["distributionPercentage"] == "50"


def test_expected_path_constants():
    assert PATH_LIST == "/payroll/v2/workers/{aoid}/pay-distributions"
    assert PATH_DETAIL == "/payroll/v2/workers/{aoid}/pay-distributions/{pay_distribution_id}"
    assert PATH_CHANGE == "/events/payroll/v1/worker.pay-distribution.change"
