"""Tests for adp_team_time_cards_tools module-level builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_team_time_cards_tools import (
    PATH_GET,
    build_team_time_cards_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


@pytest.mark.asyncio
async def test_get_basic_path_no_params():
    client = MagicMock()
    client.request = AsyncMock(return_value=httpx.Response(200, json={}))

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_team_time_cards_tools.build_mtls_httpx_client", fake_client):
        tools = build_team_time_cards_tools(_make_connection(), RequestCache(ttl_seconds=30, max_entries=8))
        await tools[0].ainvoke({"associate_oid": "G3ABC"})

    called_url = client.request.call_args[1]["url"]
    assert called_url.endswith(PATH_GET.format(aoid="G3ABC"))
    # no extra OData params
    called_params = client.request.call_args[1].get("params", {})
    assert not called_params


@pytest.mark.asyncio
async def test_get_with_odata_params():
    client = MagicMock()
    client.request = AsyncMock(return_value=httpx.Response(200, json={}))

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    with patch("lfx.components.adp.adp_team_time_cards_tools.build_mtls_httpx_client", fake_client):
        tools = build_team_time_cards_tools(_make_connection(), RequestCache(ttl_seconds=30, max_entries=8))
        await tools[0].ainvoke(
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

    called_params = client.request.call_args[1].get("params", {})
    assert called_params["$filter"] == "startDate ge '2026-01-01'"
    assert called_params["$top"] == 50
    assert called_params["indirectReportees"] is True
    assert called_params["customFilter"] == "MyHyperfind"
    assert called_params["visibilityCode"] == "public"


def test_build_tools_single_read_tool():
    tools = build_team_time_cards_tools(_make_connection(), RequestCache(ttl_seconds=30, max_entries=8))
    assert len(tools) == 1
    assert tools[0].name == "get_team_time_cards"


@pytest.mark.asyncio
async def test_call_401_retries():
    client = MagicMock()
    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(200, json={"ok": True}),
    ]
    client.request = AsyncMock(side_effect=responses)

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    async def fake_force_refresh(conn, *, force=False):
        assert force is True
        conn.access_token = "refreshed"  # noqa: S105

    with patch(
        "lfx.components.adp.adp_team_time_cards_tools.build_mtls_httpx_client",
        new=fake_client,
    ), patch(
        "lfx.components.adp.adp_team_time_cards_tools.fetch_token",
        new=AsyncMock(side_effect=fake_force_refresh),
    ):
        conn = _make_connection()
        tools = build_team_time_cards_tools(conn, RequestCache(ttl_seconds=30, max_entries=8))
        await tools[0].ainvoke({"associate_oid": "G3ABC"})

    assert client.request.call_count == 2


def test_expected_path_constant():
    assert PATH_GET == "/time/v2/workers/{aoid}/team-time-cards"
