"""Tool: get_template_instructions — on-demand fetch of a template's usage notes."""

from __future__ import annotations

from typing import Any

from langflow.services.assistant.tools.metadata_lookup import fetch_template_usage_notes


async def get_template_instructions(flow_id: str) -> dict[str, Any] | None:
    """Return the admin-authored usage notes for a starter-project template.

    Returns None when the flow doesn't exist or the id is malformed.
    Otherwise returns {flow_id, flow_name, agent_usage_notes}. The
    agent_usage_notes field is None when the flow exists but no metadata
    row has been authored yet.
    """
    return await fetch_template_usage_notes(flow_id)
