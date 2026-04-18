"""Shared metadata lookup helpers for assistant tools and system prompt injection."""

from __future__ import annotations

from uuid import UUID

from sqlmodel import select

from langflow.services.database.models import ComponentMetadata, Flow, TemplateMetadata
from langflow.services.deps import session_scope


async def fetch_component_summaries(names: list[str]) -> dict[str, str | None]:
    """Return {component_name: agent_summary} for the given names (absent → None)."""
    if not names:
        return {}
    async with session_scope() as session:
        rows = (
            await session.exec(
                select(ComponentMetadata).where(ComponentMetadata.component_name.in_(names))
            )
        ).all()
    return {r.component_name: r.agent_summary for r in rows}


async def fetch_component_usage_notes(component_name: str) -> str | None:
    """Return agent_usage_notes for a single component, or None when absent."""
    async with session_scope() as session:
        row = (
            await session.exec(
                select(ComponentMetadata).where(
                    ComponentMetadata.component_name == component_name
                )
            )
        ).one_or_none()
    return row.agent_usage_notes if row else None


async def fetch_template_summaries() -> list[dict]:
    """Return rows with (flow_id, flow_name, agent_summary) for prompt injection.

    Only includes templates whose agent_summary is non-null. Sorted by flow name.
    Used by Task 11 (system prompt injection); parked here since the lookup is
    metadata-shaped.
    """
    async with session_scope() as session:
        metas = (
            await session.exec(
                select(TemplateMetadata).where(TemplateMetadata.agent_summary.is_not(None))
            )
        ).all()
        if not metas:
            return []
        flow_ids = [m.flow_id for m in metas]
        flows = (await session.exec(select(Flow).where(Flow.id.in_(flow_ids)))).all()
    flow_by_id = {f.id: f for f in flows}
    out = []
    for m in metas:
        flow = flow_by_id.get(m.flow_id)
        if flow is None:
            continue
        out.append(
            {
                "flow_id": str(flow.id),
                "flow_name": flow.name,
                "agent_summary": m.agent_summary,
            }
        )
    out.sort(key=lambda r: r["flow_name"])
    return out


async def fetch_template_usage_notes(flow_id: str) -> dict | None:
    """Return {flow_id, flow_name, agent_usage_notes} for a single template.

    Returns None when flow_id is malformed or the flow doesn't exist. Returns
    agent_usage_notes=None when the flow exists but has no metadata row.
    """
    try:
        parsed = UUID(flow_id)
    except ValueError:
        return None
    async with session_scope() as session:
        flow = (await session.exec(select(Flow).where(Flow.id == parsed))).one_or_none()
        if flow is None:
            return None
        meta = (
            await session.exec(
                select(TemplateMetadata).where(TemplateMetadata.flow_id == parsed)
            )
        ).one_or_none()
    return {
        "flow_id": flow_id,
        "flow_name": flow.name,
        "agent_usage_notes": meta.agent_usage_notes if meta else None,
    }
