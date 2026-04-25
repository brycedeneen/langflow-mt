"""Tests for ADPMCPComponent."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools import StructuredTool
from lfx.components.adp.adp_mcp import ADPMCPComponent


def _make_component(connection, **overrides):
    defaults = {
        "connection": connection,
        "mcp_url": "",
        "tool_filter": "",
    }
    defaults.update(overrides)
    return ADPMCPComponent(**defaults)


def _make_raw_mcp_tool(name: str) -> SimpleNamespace:
    """Create a fake raw MCP tool object matching the MCP SDK shape."""
    return SimpleNamespace(
        name=name,
        description=f"Tool: {name}",
        inputSchema={"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
    )


_FAKE_CLIENT = MagicMock()


@pytest.mark.asyncio
async def test_mcp_component_uses_connection_base_url_by_default(adp_connection):
    c = _make_component(adp_connection)
    raw_tools = [_make_raw_mcp_tool("list_workers"), _make_raw_mcp_tool("get_worker")]

    async def fake_list(url, headers):
        assert url == adp_connection.mcp_base_url
        assert headers["Authorization"] == f"Bearer {adp_connection.access_token}"
        return raw_tools, _FAKE_CLIENT

    with patch.object(c, "_list_tools", new=AsyncMock(side_effect=fake_list)):
        tools = await c.build_tools()

    assert len(tools) == 2
    assert all(isinstance(t, StructuredTool) for t in tools)
    assert [t.name for t in tools] == ["list_workers", "get_worker"]


@pytest.mark.asyncio
async def test_mcp_component_override_url(adp_connection):
    c = _make_component(adp_connection, mcp_url="https://staging-mcp.adp.com/mcp")
    captured: dict = {}

    async def fake_list(url, _headers):
        captured["url"] = url
        return [], _FAKE_CLIENT

    with patch.object(c, "_list_tools", new=AsyncMock(side_effect=fake_list)):
        await c.build_tools()
    assert captured["url"] == "https://staging-mcp.adp.com/mcp"


@pytest.mark.asyncio
async def test_mcp_component_rejects_off_allowlist_mcp_url(adp_connection):
    c = _make_component(adp_connection, mcp_url="https://attacker.example.com/mcp")
    list_mock = AsyncMock()
    with patch.object(c, "_list_tools", new=list_mock), pytest.raises(ValueError, match="mcp_url"):
        await c.build_tools()
    list_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_mcp_component_tool_filter(adp_connection):
    c = _make_component(adp_connection, tool_filter="list_workers, get_worker")
    raw_tools = [
        _make_raw_mcp_tool("list_workers"),
        _make_raw_mcp_tool("get_worker"),
        _make_raw_mcp_tool("list_pay_statements"),
    ]
    with patch.object(c, "_list_tools", new=AsyncMock(return_value=(raw_tools, _FAKE_CLIENT))):
        tools = await c.build_tools()
    assert [t.name for t in tools] == ["list_workers", "get_worker"]


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
        return [_make_raw_mcp_tool("list_workers")], _FAKE_CLIENT

    async def fake_force(conn, *, force=False):
        assert force is True
        conn.access_token = "refreshed"  # noqa: S105

    with patch.object(c, "_list_tools", new=AsyncMock(side_effect=fake_list)), patch(
        "lfx.components.adp.adp_mcp.fetch_token", new=AsyncMock(side_effect=fake_force)
    ):
        tools = await c.build_tools()

    assert call_count["n"] == 2
    assert tools[0].name == "list_workers"
