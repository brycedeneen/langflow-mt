"""MCP server exposing the component catalog tools.

This creates a standalone MCP ``Server`` instance that wraps the four
read-only catalog functions so they can be consumed by any MCP client.
"""

from __future__ import annotations

import json

from mcp import types
from mcp.server import Server

from langflow.services.assistant.tools.catalog import (
    get_component_schema,
    list_categories,
    list_compatible_outputs,
    search_components,
)
from langflow.services.assistant.tools.template_metadata import (
    get_template_instructions,
)

server = Server("langflow-components-catalog")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Advertise the four catalog tools to MCP clients."""
    return [
        types.Tool(
            name="list_categories",
            description=(
                "List all Langflow component categories with their component counts. "
                "Call this first to understand what kinds of components are available."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        types.Tool(
            name="search_components",
            description=(
                "Search for Langflow components by name or description, optionally "
                "filtered by category. Returns summary info: name, display_name, type, description, "
                "and (when admin-authored) agent_summary."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Substring to match against component name, display_name, or description.",
                    },
                    "component_type": {
                        "type": "string",
                        "description": "Category filter, e.g. 'llms', 'vectorstores'.",
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="get_component_schema",
            description=(
                "Get the full schema for a specific component including all inputs, "
                "outputs, type information, and (when admin-authored) agent_usage_notes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "Exact internal component name, e.g. 'OpenAIModel'.",
                    },
                },
                "required": ["component_name"],
            },
        ),
        types.Tool(
            name="get_template_instructions",
            description=(
                "Fetch the admin-authored usage notes for a template, "
                "keyed by template_id. Returns {template_id, template_name, agent_usage_notes}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "template_id": {
                        "type": "string",
                        "description": "UUID of the template.",
                    },
                },
                "required": ["template_id"],
            },
        ),
        types.Tool(
            name="list_compatible_outputs",
            description=(
                "Find components whose outputs include a given type. Useful for "
                "determining what can connect to a particular input."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "input_type": {
                        "type": "string",
                        "description": "The input type to match, e.g. 'Message', 'Document'.",
                    },
                },
                "required": ["input_type"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """Dispatch an MCP tool call to the matching catalog function."""
    arguments = arguments or {}

    if name == "list_categories":
        result = await list_categories()
    elif name == "search_components":
        result = await search_components(
            query=arguments.get("query"),
            component_type=arguments.get("component_type"),
        )
    elif name == "get_component_schema":
        component_name = arguments.get("component_name")
        if not component_name:
            return [types.TextContent(type="text", text=json.dumps({"error": "component_name is required"}))]
        result = await get_component_schema(component_name=component_name)
        if result is None:
            result = {"error": f"Component '{component_name}' not found"}
    elif name == "list_compatible_outputs":
        input_type = arguments.get("input_type")
        if not input_type:
            return [types.TextContent(type="text", text=json.dumps({"error": "input_type is required"}))]
        result = await list_compatible_outputs(input_type=input_type)
    elif name == "get_template_instructions":
        template_id = arguments.get("template_id")
        if not template_id:
            return [types.TextContent(type="text", text=json.dumps({"error": "template_id is required"}))]
        result = await get_template_instructions(template_id=template_id)
        if result is None:
            result = {"error": f"Template '{template_id}' not found"}
    else:
        result = {"error": f"Unknown tool: {name}"}

    return [types.TextContent(type="text", text=json.dumps(result, default=str))]
