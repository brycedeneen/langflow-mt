"""Tests for ADPTimeOffToolsComponent."""

from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_time_off_tools import (
    ADPTimeOffToolsComponent,
    PATH_BALANCES_MODIFY,
    _V2_PATHS,
    _V3_SUMMARY_PATHS,
    build_balances_modify_event,
)


def _make(connection, *, enable_mutations=False):
    return ADPTimeOffToolsComponent(connection=connection, enable_mutations=enable_mutations)


def test_build_balances_modify_event():
    body = build_balances_modify_event(
        associate_oid="G3ABC",
        fields={"adjustments": [{"amount": 4.0}]},
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {"associateOID": "G3ABC"}
    assert event["data"]["transform"]["timeOffBalances"]["adjustments"][0]["amount"] == 4.0


@pytest.mark.asyncio
async def test_v2_view_routes_correct_paths(adp_connection):
    c = _make(adp_connection)
    mock_call = AsyncMock(return_value={})

    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        read_tool = next(t for t in tools if t.name == "get_worker_time_off_details")
        for view in ["balances", "configurations", "requests"]:
            await read_tool.ainvoke({"associate_oid": "G3ABC", "view": view})
            expected = _V2_PATHS[view].format(aoid="G3ABC")
            assert mock_call.call_args.kwargs["path"] == expected


@pytest.mark.asyncio
async def test_v3_scope_routes_correct_paths(adp_connection):
    c = _make(adp_connection)
    mock_call = AsyncMock(return_value={})

    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        summary_tool = next(t for t in tools if t.name == "get_time_off_request_summaries")
        for scope in ["self", "team"]:
            await summary_tool.ainvoke({"associate_oid": "G3ABC", "scope": scope})
            assert mock_call.call_args.kwargs["path"] == _V3_SUMMARY_PATHS[scope].format(aoid="G3ABC")


@pytest.mark.asyncio
async def test_modify_gated(adp_connection):
    c = _make(adp_connection, enable_mutations=False)
    tools = await c.build_tools()
    assert "modify_time_off_balances" not in {t.name for t in tools}

    c = _make(adp_connection, enable_mutations=True)
    tools = await c.build_tools()
    assert "modify_time_off_balances" in {t.name for t in tools}


@pytest.mark.asyncio
async def test_modify_routes_to_balances_modify(adp_connection):
    c = _make(adp_connection, enable_mutations=True)
    mock_post = AsyncMock(return_value={})

    with patch.object(c, "_post_event", new=mock_post):
        tools = await c.build_tools()
        mod_tool = next(t for t in tools if t.name == "modify_time_off_balances")
        await mod_tool.ainvoke({"associate_oid": "G3ABC", "fields": {}})

    assert mock_post.call_args.kwargs["path"] == PATH_BALANCES_MODIFY
