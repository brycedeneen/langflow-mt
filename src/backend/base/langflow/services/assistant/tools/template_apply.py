"""Tool: apply_template — atomically load a template's nodes+edges into a flow."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlmodel import select

from langflow.services.assistant.tools._id_regen import regenerate_flow_ids
from langflow.services.database.models import Flow
from langflow.services.database.models.flow.starter import (
    is_flow_a_starter_project_async,
)
from langflow.services.deps import session_scope


async def apply_template(
    target_flow_id: str,
    template_flow_id: str,
) -> dict[str, Any]:
    """Replace a blank flow's data with a template's data. Sets the target's
    based_on_template_flow_id so subsequent assistant messages carry the
    template's agent_usage_notes in the system prompt.

    Returns: {"applied_patch": {"added_nodes": [...], "added_edges": [...],
              "updated_nodes": [], "removed_ids": []}, "template_name": str}
    Errors:  {"error": "..."} when target is non-empty, template isn't a
    starter project, or either flow can't be loaded.
    """
    try:
        target_uuid = UUID(target_flow_id)
        template_uuid = UUID(template_flow_id)
    except ValueError:
        return {"error": "Invalid flow id format."}

    async with session_scope() as session:
        target = (await session.exec(select(Flow).where(Flow.id == target_uuid))).one_or_none()
        if target is None:
            return {"error": "Target flow not found."}
        template = (await session.exec(select(Flow).where(Flow.id == template_uuid))).one_or_none()
        if template is None:
            return {"error": "Template flow not found."}

        if not await is_flow_a_starter_project_async(template, session):
            return {"error": "Source flow is not a template."}

        current_nodes = (target.data or {}).get("nodes") or []
        if current_nodes:
            return {
                "error": (
                    "Target flow is not empty. Start from a blank flow to apply a template."
                )
            }

        template_data = template.data or {"nodes": [], "edges": []}
        new_data = regenerate_flow_ids(template_data)

        target.data = new_data
        target.based_on_template_flow_id = template_uuid
        session.add(target)
        await session.commit()
        await session.refresh(target)

        return {
            "applied_patch": {
                "added_nodes": new_data.get("nodes") or [],
                "added_edges": new_data.get("edges") or [],
                "updated_nodes": [],
                "removed_ids": [],
            },
            "template_name": template.name,
        }
