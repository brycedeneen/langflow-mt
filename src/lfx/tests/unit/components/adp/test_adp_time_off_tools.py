"""Tests for adp_time_off_tools module-level builder."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from lfx.components.adp._shared import RequestCache
from lfx.components.adp.adp_time_off_tools import (
    _V2_PATHS,
    _V3_SUMMARY_PATHS,
    PATH_BALANCES_MODIFY,
    build_balances_modify_event,
    build_time_off_tools,
)


def _make_connection(*, access_token="fake-token", api_base_url="https://api.adp.com"):  # noqa: S107
    conn = MagicMock()
    conn.access_token = access_token
    conn.api_base_url = api_base_url
    return conn


def test_build_balances_modify_event():
    body = build_balances_modify_event(
        associate_oid="G3ABC",
        fields={"adjustments": [{"amount": 4.0}]},
    )
    event = body["events"][0]
    assert event["data"]["eventContext"] == {"associateOID": "G3ABC"}
    assert event["data"]["transform"]["timeOffBalances"]["adjustments"][0]["amount"] == 4.0


@pytest.mark.asyncio
async def test_v2_view_routes_correct_paths():
    client = MagicMock()
    client.request = AsyncMock(return_value=httpx.Response(200, json={}))

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    conn = _make_connection()
    with patch("lfx.components.adp.adp_time_off_tools.build_mtls_httpx_client", fake_client):
        for view in ["balances", "configurations", "requests"]:
            # Fresh cache per call by resetting client
            client.request = AsyncMock(return_value=httpx.Response(200, json={}))
            cache = RequestCache(ttl_seconds=30, max_entries=8)
            tools2 = build_time_off_tools(conn, cache)
            read_tool2 = next(t for t in tools2 if t.name == "get_worker_time_off_details")
            await read_tool2.ainvoke({"associate_oid": "G3ABC", "view": view})
            expected = _V2_PATHS[view].format(aoid="G3ABC")
            called_url = client.request.call_args[1]["url"]
            assert called_url.endswith(expected), f"view={view}: expected URL ending {expected}, got {called_url}"


@pytest.mark.asyncio
async def test_v3_scope_routes_correct_paths():
    client = MagicMock()

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    conn = _make_connection()
    with patch("lfx.components.adp.adp_time_off_tools.build_mtls_httpx_client", fake_client):
        for scope in ["self", "team"]:
            client.request = AsyncMock(return_value=httpx.Response(200, json={}))
            cache = RequestCache(ttl_seconds=30, max_entries=8)
            tools = build_time_off_tools(conn, cache)
            summary_tool = next(t for t in tools if t.name == "get_time_off_request_summaries")
            await summary_tool.ainvoke({"associate_oid": "G3ABC", "scope": scope})
            expected = _V3_SUMMARY_PATHS[scope].format(aoid="G3ABC")
            called_url = client.request.call_args[1]["url"]
            assert called_url.endswith(expected), f"scope={scope}: expected URL ending {expected}, got {called_url}"


def test_modify_gated():
    conn = _make_connection()
    tools = build_time_off_tools(conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=False)
    assert "modify_time_off_balances" not in {t.name for t in tools}

    tools = build_time_off_tools(conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True)
    assert "modify_time_off_balances" in {t.name for t in tools}


@pytest.mark.asyncio
async def test_modify_routes_to_balances_modify():
    client = MagicMock()
    client.request = AsyncMock(return_value=httpx.Response(200, json={"ok": True}))

    @asynccontextmanager
    async def fake_client(*_args, **_kwargs):
        yield client

    conn = _make_connection()
    with patch("lfx.components.adp.adp_time_off_tools.build_mtls_httpx_client", fake_client):
        tools = build_time_off_tools(
            conn, RequestCache(ttl_seconds=30, max_entries=8), enable_mutations=True,
        )
        mod_tool = next(t for t in tools if t.name == "modify_time_off_balances")
        await mod_tool.ainvoke({"associate_oid": "G3ABC", "fields": {}})

    called_url = client.request.call_args[1]["url"]
    assert called_url.endswith(PATH_BALANCES_MODIFY)
