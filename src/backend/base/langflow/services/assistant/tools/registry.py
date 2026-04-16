from __future__ import annotations

from typing import Any

CATALOG_TOOLS = [
    {
        "name": "list_categories",
        "description": "List all Langflow component categories with counts. Call this first to understand what kinds of components are available.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_components",
        "description": "Search for Langflow components by name/description or filter by category. Returns name, display_name, type, description.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
                "component_type": {"type": "string", "description": "Category filter (e.g. 'llms', 'vectorstores')"},
            },
            "required": [],
        },
    },
    {
        "name": "get_component_schema",
        "description": "Get the full schema for a specific component including all inputs/outputs and types.",
        "parameters": {
            "type": "object",
            "properties": {
                "component_name": {"type": "string", "description": "Exact component name"},
            },
            "required": ["component_name"],
        },
    },
    {
        "name": "list_compatible_outputs",
        "description": "Find components whose outputs include a given type. Useful for figuring out what can connect to a given input.",
        "parameters": {
            "type": "object",
            "properties": {
                "input_type": {"type": "string", "description": "The input type (e.g. 'Message', 'Document')"},
            },
            "required": ["input_type"],
        },
    },
]

MUTATION_TOOLS = [
    {
        "name": "add_component",
        "description": "Add a new component node to the flow canvas. Use get_component_schema first to find the exact component_type name.",
        "parameters": {
            "type": "object",
            "properties": {
                "component_type": {"type": "string", "description": "Component type name (e.g. 'OpenAIModel')"},
                "position": {
                    "description": "'auto' to auto-position, or {x, y} coordinates",
                    "oneOf": [
                        {"type": "string", "enum": ["auto"]},
                        {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]},
                    ],
                },
                "initial_fields": {
                    "type": "object",
                    "description": "Field values to pre-populate (field_name → value)",
                    "additionalProperties": True,
                },
            },
            "required": ["component_type"],
        },
    },
    {
        "name": "connect_edge",
        "description": "Connect an output of one node to an input of another node.",
        "parameters": {
            "type": "object",
            "properties": {
                "source_node_id": {"type": "string"},
                "source_output": {"type": "string", "description": "Output name on the source node"},
                "target_node_id": {"type": "string"},
                "target_input": {"type": "string", "description": "Input field name on the target node"},
            },
            "required": ["source_node_id", "source_output", "target_node_id", "target_input"],
        },
    },
    {
        "name": "set_field_value",
        "description": "Set a field value on an existing node in the flow. The field_name must match a template field name exactly (e.g. 'url_input' not 'url'). Check the node's template keys from the flow data if unsure.",
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "field_name": {"type": "string"},
                "value": {"description": "The value to set"},
            },
            "required": ["node_id", "field_name", "value"],
        },
    },
    {
        "name": "remove_component",
        "description": "Remove a node and all its connected edges from the flow.",
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
            },
            "required": ["node_id"],
        },
    },
    {
        "name": "add_sticky_note",
        "description": "Add a sticky note to the flow canvas.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Note text (supports markdown)"},
                "position": {
                    "description": "'auto' or {x, y}",
                    "oneOf": [
                        {"type": "string", "enum": ["auto"]},
                        {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]},
                    ],
                },
            },
            "required": ["content"],
        },
    },
]

ALL_TOOLS = CATALOG_TOOLS + MUTATION_TOOLS


def get_tools_for_openai() -> list[dict[str, Any]]:
    """Return tools in OpenAI function-calling format."""
    return [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
        for t in ALL_TOOLS
    ]


def get_tools_for_anthropic() -> list[dict[str, Any]]:
    """Return tools in Anthropic tool_use format."""
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
        for t in ALL_TOOLS
    ]


def is_catalog_tool(name: str) -> bool:
    return any(t["name"] == name for t in CATALOG_TOOLS)


def is_mutation_tool(name: str) -> bool:
    return any(t["name"] == name for t in MUTATION_TOOLS)
