"""Shared metadata lookup helpers for assistant tools and system prompt injection."""

from __future__ import annotations

from uuid import UUID

from sqlmodel import select

from langflow.agentic.utils.component_search import build_component_name_resolver
from langflow.services.database.models import ComponentMetadata
from langflow.services.database.models.template.model import Template
from langflow.services.deps import session_scope


async def fetch_component_summaries(names: list[str]) -> dict[str, str | None]:
    """Return {input_name: agent_summary} for the given names (absent → None).

    Inputs may be any alias (registry key, display name, or class name); they
    are resolved to the canonical registry key before the DB query. The result
    is keyed by the *input* name so callers can correlate without re-resolving.
    """
    if not names:
        return {}
    aliases = await build_component_name_resolver()
    canonical_by_input: dict[str, str] = {}
    for name in names:
        canonical = aliases.get(name)
        if canonical is not None:
            canonical_by_input[name] = canonical
    if not canonical_by_input:
        return {name: None for name in names}
    async with session_scope() as session:
        rows = (
            await session.exec(
                select(ComponentMetadata).where(
                    ComponentMetadata.component_name.in_(set(canonical_by_input.values()))
                )
            )
        ).all()
    summary_by_canonical = {r.component_name: r.agent_summary for r in rows}
    return {
        name: summary_by_canonical.get(canonical_by_input[name]) if name in canonical_by_input else None
        for name in names
    }


async def fetch_component_usage_notes(component_name: str) -> str | None:
    """Return agent_usage_notes for a single component, or None when absent.

    The input may be any alias (registry key, display name, or class name).
    """
    aliases = await build_component_name_resolver()
    canonical = aliases.get(component_name)
    if canonical is None:
        return None
    async with session_scope() as session:
        row = (
            await session.exec(
                select(ComponentMetadata).where(
                    ComponentMetadata.component_name == canonical
                )
            )
        ).one_or_none()
    return row.agent_usage_notes if row else None


async def fetch_template_summaries() -> list[dict]:
    """Return rows with (template_id, template_name, agent_summary) for prompt injection.

    Only includes templates whose ``agent_summary`` is non-null and that are
    neither archived nor soft-deleted. Sorted by template name.
    """
    async with session_scope() as session:
        rows = (
            await session.exec(
                select(Template)
                .where(Template.agent_summary.is_not(None))
                .where(Template.deleted_at.is_(None))
                .where(Template.archived_at.is_(None))
            )
        ).all()
    out = [
        {
            "template_id": str(t.id),
            "template_name": t.name,
            "agent_summary": t.agent_summary,
        }
        for t in rows
    ]
    out.sort(key=lambda r: r["template_name"])
    return out


async def fetch_template_usage_notes(template_id: str) -> dict | None:
    """Return {template_id, template_name, agent_usage_notes} for a single template.

    Returns None when ``template_id`` is malformed or the template doesn't exist.
    Returns ``agent_usage_notes=None`` when the template exists but has no notes.
    """
    try:
        parsed = UUID(template_id)
    except ValueError:
        return None
    async with session_scope() as session:
        t = (
            await session.exec(select(Template).where(Template.id == parsed))
        ).one_or_none()
    if t is None:
        return None
    return {
        "template_id": str(t.id),
        "template_name": t.name,
        "agent_usage_notes": t.agent_usage_notes,
    }
