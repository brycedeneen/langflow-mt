"""Per-message helper that injects the source-template notes into the system prompt."""

from __future__ import annotations

from uuid import UUID

from langflow.services.assistant.tools.metadata_lookup import fetch_template_usage_notes


async def build_flow_template_context(
    based_on_template_id: UUID | None,
) -> str:
    """Return a markdown block describing the flow's source template, or "".

    The block is inserted between ``{canvas_summary}`` and ``{available_templates}``
    in SYSTEM_PROMPT_TEMPLATE. It gives the LLM the template's admin-authored
    ``agent_usage_notes`` so it can customize the flow with the user intelligently.

    Returns "" when:
      - based_on_template_id is None (ordinary user flow), or
      - the pointer references a template that no longer exists, or
      - the template has no agent_usage_notes set.
    """
    if based_on_template_id is None:
        return ""
    notes = await fetch_template_usage_notes(str(based_on_template_id))
    if notes is None or notes.get("agent_usage_notes") is None:
        return ""
    return (
        "## Current Flow Template\n\n"
        f'This flow was created from the "{notes["template_name"]}" template.\n'
        f"{notes['agent_usage_notes']}\n\n"
    )
