"""ADPMCPComponent — exposes ADP MCP server tools to a Langflow Agent."""

from __future__ import annotations

from typing import Any

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import HandleInput, MessageTextInput, Output

from ._shared import ADPConnection, fetch_token, validate_adp_url


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

    async def build_tools(self) -> list[Any]:
        """Fetch tools from the ADP MCP server, applying auth and optional filtering."""
        conn: ADPConnection = self.connection
        url = (self.mcp_url or "").strip() or conn.mcp_base_url
        validate_adp_url(url, field_name="mcp_url")
        headers = {"Authorization": f"Bearer {conn.access_token}"}

        _http_unauthorized = 401
        try:
            tools = await self._list_tools(url, headers)
        except httpx.HTTPStatusError as e:
            if e.response.status_code != _http_unauthorized:
                raise
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            tools = await self._list_tools(url, headers)

        filter_value = (self.tool_filter or "").strip()
        if filter_value:
            wanted = {t.strip() for t in filter_value.split(",") if t.strip()}
            tools = [t for t in tools if self._tool_name(t) in wanted]

        return tools

    @staticmethod
    def _tool_name(tool: Any) -> str:
        """Extract the tool name from a dict or object."""
        if isinstance(tool, dict):
            return tool.get("name", "")
        return getattr(tool, "name", "")

    async def _list_tools(self, url: str, headers: dict[str, str]) -> list[Any]:
        """Connect to the ADP MCP server and return its tool list.

        This is a thin wrapper around ``MCPStreamableHttpClient._connect_to_server``
        so that tests can patch it cleanly. The public signature
        ``(url, headers) -> list[Any]`` is the stable contract; internals may change.

        Real wiring notes:
        - ``MCPStreamableHttpClient._connect_to_server(url, headers, ...)`` accepts a
          ``headers`` dict directly, which is how we pass the Bearer token.
        - mTLS is NOT currently plumbed through ``MCPStreamableHttpClient``: the base
          client does not accept a custom ``httpx.AsyncClient`` or SSL context. For v1
          the Bearer token alone is sent over HTTPS — this is acceptable per ADP bundle
          design. A follow-up task should extend ``MCPStreamableHttpClient`` to accept
          an ``ssl_context`` or ``httpx_client`` parameter so that full mTLS can be
          wired through ``build_mtls_httpx_client(conn)``.
        """
        from lfx.base.mcp.util import MCPStreamableHttpClient

        client = MCPStreamableHttpClient()
        # _connect_to_server manages its own session; no explicit aclose needed for
        # the one-shot list-tools call (sessions are cached in MCPSessionManager).
        return await client._connect_to_server(url=url, headers=headers)  # noqa: SLF001
