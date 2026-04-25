"""ADPMCPComponent — exposes ADP MCP server tools to a Langflow Agent."""

from __future__ import annotations

from typing import Any

import httpx
from langchain_core.tools import StructuredTool

from lfx.components.adp._shared import ADPConnection, fetch_token, validate_adp_url
from lfx.custom.custom_component.component import Component
from lfx.field_typing import Tool
from lfx.io import HandleInput, MessageTextInput, Output


class ADPMCPComponent(Component):
    display_name = "ADP MCP"
    description = "Connect to ADP's MCP server and expose its tools to an Agent component."
    icon = "Plug"
    name = "ADPMCP"

    inputs = [
        HandleInput(
            name="connection",
            display_name="ADP Connection",
            input_types=["ADPConnection"],
            required=True,
        ),
        MessageTextInput(
            name="mcp_url",
            display_name="MCP URL",
            info="Override the default ADP MCP URL on the connection.",
            advanced=True,
        ),
        MessageTextInput(
            name="tool_filter",
            display_name="Tool Filter",
            info="Comma-separated list of tool names to expose (leave blank for all).",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Tools", name="tools", method="build_tools"),
    ]

    async def build_tools(self) -> list[Tool]:
        """Fetch tools from the ADP MCP server, applying auth and optional filtering."""
        conn: ADPConnection = self.connection
        url = (self.mcp_url or "").strip() or conn.mcp_base_url
        validate_adp_url(url, field_name="mcp_url")
        headers = {"Authorization": f"Bearer {conn.access_token}"}

        _http_unauthorized = 401
        try:
            raw_tools, client = await self._list_tools(url, headers)
        except httpx.HTTPStatusError as e:
            if e.response.status_code != _http_unauthorized:
                raise
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            raw_tools, client = await self._list_tools(url, headers)

        filter_value = (self.tool_filter or "").strip()
        if filter_value:
            wanted = {t.strip() for t in filter_value.split(",") if t.strip()}
            raw_tools = [t for t in raw_tools if self._tool_name(t) in wanted]

        return self._convert_to_structured_tools(raw_tools, client)

    @staticmethod
    def _tool_name(tool: Any) -> str:
        """Extract the tool name from a dict or object."""
        if isinstance(tool, dict):
            return tool.get("name", "")
        return getattr(tool, "name", "")

    @staticmethod
    def _convert_to_structured_tools(raw_tools: list[Any], client: Any) -> list[StructuredTool]:
        """Convert raw MCP tool objects to langchain StructuredTool instances.

        Builds schema + coroutine inline to avoid importing lfx.base.mcp.util
        at the module level (which pulls in the ``mcp`` SDK).
        """
        from lfx.schema.json_schema import create_input_schema_from_json_schema

        tools: list[StructuredTool] = []
        for tool in raw_tools:
            if not tool or not hasattr(tool, "name"):
                continue
            args_schema = create_input_schema_from_json_schema(tool.inputSchema)
            if not args_schema:
                continue

            tool_name = tool.name

            def _make_coroutine(name, schema, c):
                async def _coroutine(**kwargs):
                    validated = schema.model_validate(kwargs)
                    return await c.run_tool(name, arguments=validated.model_dump())
                return _coroutine

            tools.append(
                StructuredTool.from_function(
                    name=tool_name,
                    description=tool.description or "",
                    args_schema=args_schema,
                    coroutine=_make_coroutine(tool_name, args_schema, client),
                )
            )
        return tools

    async def _list_tools(self, url: str, headers: dict[str, str]) -> tuple[list[Any], Any]:
        """Connect to the ADP MCP server and return (raw_tools, client).

        Returns the client alongside the tools so callers can pass it to
        ``_convert_to_structured_tools`` for building tool executors.
        """
        from lfx.base.mcp.util import MCPStreamableHttpClient

        client = MCPStreamableHttpClient()
        raw_tools = await client._connect_to_server(url=url, headers=headers)  # noqa: SLF001
        return raw_tools, client
