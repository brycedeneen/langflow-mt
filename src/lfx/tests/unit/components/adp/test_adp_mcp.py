"""Tests for ADPMCPComponent."""

from unittest.mock import AsyncMock, patch

import pytest
from lfx.components.adp.adp_mcp import ADPMCPComponent


def _make_component(connection, **overrides):
    defaults = {
        "connection": connection,
        "mcp_url": "",
        "tool_filter": "",
    }
    defaults.update(overrides)
    return ADPMCPComponent(**defaults)


@pytest.mark.asyncio
async def test_mcp_component_uses_connection_base_url_by_default(adp_connection):
    c = _make_component(adp_connection)
    fake_tools = [{"name": "list_workers"}, {"name": "get_worker"}]

    async def fake_list(url, headers):
        assert url == adp_connection.mcp_base_url
        assert headers["Authorization"] == f"Bearer {adp_connection.access_token}"
        return fake_tools

    with patch.object(c, "_list_tools", new=AsyncMock(side_effect=fake_list)):
        tools = await c.build_tools()

    assert [t["name"] for t in tools] == ["list_workers", "get_worker"]


@pytest.mark.asyncio
async def test_mcp_component_override_url(adp_connection):
    c = _make_component(adp_connection, mcp_url="https://custom.adp.example/mcp")
    captured: dict = {}

    async def fake_list(url, _headers):
        captured["url"] = url
        return []

    with patch.object(c, "_list_tools", new=AsyncMock(side_effect=fake_list)):
        await c.build_tools()
    assert captured["url"] == "https://custom.adp.example/mcp"


@pytest.mark.asyncio
async def test_mcp_component_tool_filter(adp_connection):
    c = _make_component(adp_connection, tool_filter="list_workers, get_worker")
    fake_tools = [
        {"name": "list_workers"},
        {"name": "get_worker"},
        {"name": "list_pay_statements"},
    ]
    with patch.object(c, "_list_tools", new=AsyncMock(return_value=fake_tools)):
        tools = await c.build_tools()
    assert [t["name"] for t in tools] == ["list_workers", "get_worker"]


@pytest.mark.asyncio
async def test_mcp_component_401_triggers_force_refresh(adp_connection):
    c = _make_component(adp_connection)

    call_count = {"n": 0}

    async def fake_list(url, _headers):
        call_count["n"] += 1
        if call_count["n"] == 1:
            from httpx import HTTPStatusError, Request, Response

            req = Request("GET", url)
            resp = Response(401, request=req)
            msg = "unauthorized"
            raise HTTPStatusError(msg, request=req, response=resp)
        return [{"name": "list_workers"}]

    async def fake_force(conn, *, force=False):
        assert force is True
        conn.access_token = "refreshed"  # noqa: S105

    with patch.object(c, "_list_tools", new=AsyncMock(side_effect=fake_list)), patch(
        "lfx.components.adp.adp_mcp.fetch_token", new=AsyncMock(side_effect=fake_force)
    ):
        tools = await c.build_tools()

    assert call_count["n"] == 2
    assert tools[0]["name"] == "list_workers"
