"""Tests for ADPTeamTimeCardsToolsComponent."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lfx.components.adp.adp_team_time_cards_tools import (
    ADPTeamTimeCardsToolsComponent,
    PATH_GET,
)


def _make_component(connection) -> ADPTeamTimeCardsToolsComponent:
    return ADPTeamTimeCardsToolsComponent(connection=connection)


@pytest.mark.asyncio
async def test_get_basic_path_no_params(adp_connection):
    c = _make_component(adp_connection)
    mock_call = AsyncMock(return_value={})

    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        tool = tools[0]
        await tool.ainvoke({"associate_oid": "G3ABC"})

    assert mock_call.call_args.kwargs["path"] == PATH_GET.format(aoid="G3ABC")
    assert mock_call.call_args.kwargs["params"] is None


@pytest.mark.asyncio
async def test_get_with_odata_params(adp_connection):
    c = _make_component(adp_connection)
    mock_call = AsyncMock(return_value={})

    with patch.object(c, "_call", new=mock_call):
        tools = await c.build_tools()
        tool = tools[0]
        await tool.ainvoke(
            {
                "associate_oid": "G3ABC",
                "$filter": "startDate ge '2026-01-01'",
                "$top": 50,
                "$skip": 0,
                "$select": "timeCards",
                "$expand": "worker",
                "indirectReportees": True,
                "customFilter": "MyHyperfind",
                "visibilityCode": "public",
            },
        )

    params = mock_call.call_args.kwargs["params"]
    assert params == {
        "$filter": "startDate ge '2026-01-01'",
        "$top": 50,
        "$skip": 0,
        "$select": "timeCards",
        "$expand": "worker",
        "indirectReportees": True,
        "customFilter": "MyHyperfind",
        "visibilityCode": "public",
    }


@pytest.mark.asyncio
async def test_build_tools_single_read_tool(adp_connection):
    c = _make_component(adp_connection)
    tools = await c.build_tools()
    assert len(tools) == 1
    assert tools[0].name == "get_team_time_cards"


@pytest.mark.asyncio
async def test_call_401_retries(adp_connection):
    c = _make_component(adp_connection)
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
        "lfx.components.adp.adp_team_time_cards_tools.build_mtls_httpx_client",
        new=fake_build_client,
    ), patch.object(c, "_execute_request", new=mock_exec), patch(
        "lfx.components.adp.adp_team_time_cards_tools.fetch_token",
        new=AsyncMock(side_effect=fake_force_refresh),
    ):
        await c._call(adp_connection, path=PATH_GET.format(aoid="G3ABC"))

    assert mock_exec.call_count == 2


def test_expected_path_constant():
    assert PATH_GET == "/time/v2/workers/{aoid}/team-time-cards"
