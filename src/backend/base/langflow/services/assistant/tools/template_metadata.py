"""Tool: get_template_instructions — on-demand fetch of a template's usage notes."""

from __future__ import annotations

from typing import Any

from langflow.services.assistant.tools.metadata_lookup import fetch_template_usage_notes


async def get_template_instructions(template_id: str) -> dict[str, Any] | None:
    """Return the admin-authored usage notes for a template.

    Returns None when the template doesn't exist or the id is malformed.
    Otherwise returns ``{template_id, template_name, agent_usage_notes}``.
    The ``agent_usage_notes`` field is None when no notes have been authored.
    """
    return await fetch_template_usage_notes(template_id)
