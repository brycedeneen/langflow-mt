"""System-prompt block listing available templates."""

from __future__ import annotations

from langflow.services.assistant.tools.metadata_lookup import fetch_template_summaries

_HEADER = (
    "## Available Templates\n\n"
    "The following templates are available. Use "
    "`get_template_instructions(template_id)` if the user's request matches one.\n"
)


async def build_available_templates_block() -> str:
    """Return a ready-to-inject prompt block, or empty string when nothing to show."""
    rows = await fetch_template_summaries()
    if not rows:
        return ""
    lines = [_HEADER]
    for row in rows:
        lines.append(
            f'- [template_id: {row["template_id"]}] "{row["template_name"]}" — {row["agent_summary"]}'
        )
    return "\n".join(lines) + "\n"
