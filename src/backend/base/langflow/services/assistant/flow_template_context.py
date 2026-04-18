"""Per-message helper that injects the flow's source-template notes into the system prompt."""

from __future__ import annotations

from uuid import UUID

from langflow.services.assistant.tools.metadata_lookup import fetch_template_usage_notes


async def build_flow_template_context(
    based_on_template_flow_id: UUID | None,
) -> str:
    """Return a markdown block describing the flow's source template, or an empty string.

    The block is inserted between `{canvas_summary}` and `{available_templates}`
    in SYSTEM_PROMPT_TEMPLATE. It gives the LLM the template's admin-authored
    agent_usage_notes so it can customize the flow with the user intelligently.

    Returns "" when:
      - based_on_template_flow_id is None (ordinary user flow), or
      - the pointer is set but no TemplateMetadata row / notes exist for it, or
      - the pointer references a flow that no longer exists (stale pointer).
    """
    if based_on_template_flow_id is None:
        return ""
    notes = await fetch_template_usage_notes(str(based_on_template_flow_id))
    if notes is None or notes.get("agent_usage_notes") is None:
        return ""
    return (
        "## Current Flow Template\n\n"
        f'This flow was created from the "{notes["flow_name"]}" template.\n'
        f"{notes['agent_usage_notes']}\n\n"
    )
