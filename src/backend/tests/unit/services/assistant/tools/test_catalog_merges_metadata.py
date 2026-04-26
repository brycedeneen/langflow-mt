"""search_components and get_component_schema must merge metadata rows."""

from __future__ import annotations

import pytest

from langflow.services.assistant.tools.catalog import (
    get_component_schema,
    search_components,
)
from langflow.services.database.models import ComponentMetadata
from langflow.services.deps import session_scope


async def _replace_webhook_metadata(*, agent_summary=None, agent_usage_notes=None, updated_by) -> None:
    """Delete any existing Webhook row (which the seeder writes on startup) and
    insert a fresh one keyed by the canonical registry key ``Webhook``."""
    from sqlmodel import select

    async with session_scope() as session:
        existing = (
            await session.exec(
                select(ComponentMetadata).where(ComponentMetadata.component_name == "Webhook")
            )
        ).one_or_none()
        if existing:
            await session.delete(existing)
            await session.commit()
        session.add(
            ComponentMetadata(
                component_name="Webhook",
                agent_summary=agent_summary,
                agent_usage_notes=agent_usage_notes,
                updated_by=updated_by,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_search_components_includes_agent_summary_when_metadata_exists(
    active_super_user,
):
    await _replace_webhook_metadata(
        agent_summary="Inbound HTTP entry.", updated_by=active_super_user.id
    )

    try:
        results = await search_components(query="webhook")
        hit = next((r for r in results if r["name"] == "Webhook"), None)
        assert hit is not None
        assert hit["agent_summary"] == "Inbound HTTP entry."
    finally:
        async with session_scope() as session:
            from sqlmodel import select

            row = (
                await session.exec(
                    select(ComponentMetadata).where(ComponentMetadata.component_name == "Webhook")
                )
            ).one_or_none()
            if row:
                await session.delete(row)
            await session.commit()


@pytest.mark.asyncio
async def test_search_components_returns_null_agent_summary_when_no_metadata():
    results = await search_components(query="webhook")
    hit = next((r for r in results if r["name"] == "Webhook"), None)
    assert hit is not None
    assert hit.get("agent_summary") is None


@pytest.mark.asyncio
async def test_get_component_schema_merges_agent_usage_notes(active_super_user):
    await _replace_webhook_metadata(
        agent_usage_notes="Configure event types before wiring downstream.",
        updated_by=active_super_user.id,
    )

    try:
        schema = await get_component_schema("Webhook")
        assert schema is not None
        assert schema["agent_usage_notes"] == "Configure event types before wiring downstream."
    finally:
        async with session_scope() as session:
            from sqlmodel import select

            row = (
                await session.exec(
                    select(ComponentMetadata).where(ComponentMetadata.component_name == "Webhook")
                )
            ).one_or_none()
            if row:
                await session.delete(row)
            await session.commit()


@pytest.mark.asyncio
async def test_get_component_schema_returns_null_usage_notes_when_absent():
    schema = await get_component_schema("Webhook")
    assert schema is not None
    assert schema.get("agent_usage_notes") is None
