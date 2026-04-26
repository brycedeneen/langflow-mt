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
    {
        "name": "get_template_instructions",
        "description": (
            "Fetch the full admin-authored usage notes for a template, "
            "keyed by template_id. Call this after matching a template "
            "from the Available Templates list in the system prompt, before "
            "mutating the flow. Returns {template_id, template_name, agent_usage_notes}."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "template_id": {
                    "type": "string",
                    "description": "UUID of the template.",
                },
            },
            "required": ["template_id"],
        },
    },
    {
        "name": "apply_template",
        "description": (
            "Load a template's nodes and edges into the current flow atomically. "
            "Use this after matching a template from the Available Templates list "
            "in the system prompt — pass the target flow's id and the template's "
            "template_id. Sets the current flow's template pointer so later "
            "messages carry the template's instructions. Returns the applied patch "
            "(added_nodes and added_edges) and the template's name. Refuses when "
            "the target is non-empty or the template is archived/deleted."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target_flow_id": {
                    "type": "string",
                    "description": "UUID of the flow to apply the template to (typically the current flow).",
                },
                "template_id": {
                    "type": "string",
                    "description": "UUID of the template (from the Available Templates list).",
                },
            },
            "required": ["target_flow_id", "template_id"],
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
        "name": "create_secret_variable",
        "description": (
            "Create a user-scoped secret variable in the variable store and "
            "return its name. Use BEFORE set_field_value when the target "
            "field is a secret/password (e.g. SFTP password, an API token). "
            "After this call, pass the returned variable_name to "
            "set_field_value — the runtime substitutes the real value at "
            "execution time. Choose a descriptive name like "
            "'sftp_password_<flow_short>' so the user can recognize it later."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The variable name (will appear in the variable store).",
                },
                "value": {
                    "type": "string",
                    "description": "The secret value (will be encrypted at rest).",
                },
            },
            "required": ["name", "value"],
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

INSPECTION_TOOLS = [
    {
        "name": "get_node_field_value",
        "description": (
            "Read the current value of one field on one node in the active flow. "
            "Use for surfacing values like an endpoint URL a component computed. "
            "For webhook API keys use get_webhook_credentials instead — those "
            "live in the secret store, not the node template. Returns the value "
            "as a string, or an error string starting with 'node not found:' or "
            "'field not found on node:'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "The node's id from the canvas summary."},
                "field_name": {
                    "type": "string",
                    "description": "Template field name (backtick-style, e.g. 'endpoint'). Not the display name.",
                },
            },
            "required": ["node_id", "field_name"],
        },
    },
    {
        "name": "get_webhook_credentials",
        "description": (
            "Return the webhook URL and API key for the active flow as "
            "{endpoint, api_key}. Use after adding a webhook-like component "
            "(ADP Trigger or Webhook) and confirming persistence. Returns "
            "{error: ...} if no key has been provisioned yet."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_user_variables",
        "description": (
            "Return the names of secret variables already stored for the "
            "current user. Call this BEFORE asking the user for credentials "
            "(API keys, passwords, certificates) — they may have already "
            "configured them in a previous conversation. If a relevant name "
            "exists (e.g. 'adp_client_id'), reference it directly via "
            "set_field_value(node_id, '<field>', '<variable_name>') instead "
            "of re-asking. Returns {variable_names: [...]} with names only "
            "(never values)."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "suggest_professional_services",
        "description": (
            "Surface a Professional Services suggestion card to the user. Use when the "
            "user explicitly asks for human help, says they're stuck, or hits the same "
            "error twice. Provide a one-sentence reason. Calling this tool returns the "
            "suggestion to the user — do NOT keep iterating on the problem afterward."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "One-sentence reason for surfacing the suggestion (under 240 chars).",
                    "maxLength": 240,
                },
            },
            "required": ["reason"],
        },
    },
]


def is_inspection_tool(name: str) -> bool:
    return any(t["name"] == name for t in INSPECTION_TOOLS)


ALL_TOOLS = CATALOG_TOOLS + MUTATION_TOOLS + INSPECTION_TOOLS


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
