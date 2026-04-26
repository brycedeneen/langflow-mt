"""Unit tests for the metadata_lookup template + component helpers.

Tests cover:
- fetch_template_summaries: excludes null-summary rows, archived, deleted
- fetch_template_usage_notes: returns notes dict, handles unknown/malformed IDs
- fetch_component_summaries / fetch_component_usage_notes: resolve aliases
  (class names, display names) to the canonical registry key before DB lookup.
"""

from __future__ import annotations

import pytest

from langflow.services.assistant.tools.metadata_lookup import (
    fetch_component_summaries,
    fetch_component_usage_notes,
    fetch_template_summaries,
    fetch_template_usage_notes,
)
from langflow.services.deps import session_scope


@pytest.mark.asyncio
async def test_fetch_template_summaries_excludes_null_summary(active_super_user):  # noqa: ARG001
    from langflow.services.database.models.template.model import Template

    a = Template(name="SummaryA", nodes=[], edges=[], scope="platform", agent_summary="alpha summary")
    b = Template(name="SummaryB", nodes=[], edges=[], scope="platform", agent_summary=None)

    async with session_scope() as session:
        session.add_all([a, b])
        await session.commit()
        await session.refresh(a)
        await session.refresh(b)

    try:
        rows = await fetch_template_summaries()
        keyed = {r["template_name"]: r for r in rows}
        assert "SummaryA" in keyed
        assert "SummaryB" not in keyed
        assert keyed["SummaryA"]["agent_summary"] == "alpha summary"
        assert keyed["SummaryA"]["template_id"] == str(a.id)
    finally:
        async with session_scope() as session:
            from sqlmodel import select

            for name in ["SummaryA", "SummaryB"]:
                row = (
                    await session.exec(select(Template).where(Template.name == name))
                ).one_or_none()
                if row:
                    await session.delete(row)
            await session.commit()


@pytest.mark.asyncio
async def test_fetch_template_summaries_excludes_archived_and_deleted(active_super_user):  # noqa: ARG001
    from datetime import datetime, timezone

    from langflow.services.database.models.template.model import Template

    archived = Template(
        name="ArchivedTpl",
        nodes=[],
        edges=[],
        scope="platform",
        agent_summary="x",
        archived_at=datetime.now(timezone.utc),
    )
    deleted = Template(
        name="DeletedTpl",
        nodes=[],
        edges=[],
        scope="platform",
        agent_summary="x",
        deleted_at=datetime.now(timezone.utc),
    )
    live = Template(name="LiveTpl", nodes=[], edges=[], scope="platform", agent_summary="x")

    async with session_scope() as session:
        session.add_all([archived, deleted, live])
        await session.commit()
        await session.refresh(archived)
        await session.refresh(deleted)
        await session.refresh(live)

    try:
        rows = await fetch_template_summaries()
        names = {r["template_name"] for r in rows}
        assert "LiveTpl" in names
        assert "ArchivedTpl" not in names
        assert "DeletedTpl" not in names
    finally:
        async with session_scope() as session:
            from sqlmodel import select

            for name in ["ArchivedTpl", "DeletedTpl", "LiveTpl"]:
                row = (
                    await session.exec(select(Template).where(Template.name == name))
                ).one_or_none()
                if row:
                    await session.delete(row)
            await session.commit()


@pytest.mark.asyncio
async def test_fetch_template_usage_notes_returns_notes(active_super_user):  # noqa: ARG001
    from langflow.services.database.models.template.model import Template

    t = Template(name="NotesTemplate", nodes=[], edges=[], scope="platform", agent_usage_notes="how to use")

    async with session_scope() as session:
        session.add(t)
        await session.commit()
        await session.refresh(t)

    try:
        out = await fetch_template_usage_notes(str(t.id))
        assert out == {
            "template_id": str(t.id),
            "template_name": "NotesTemplate",
            "agent_usage_notes": "how to use",
        }
    finally:
        async with session_scope() as session:
            from sqlmodel import select

            row = (
                await session.exec(select(Template).where(Template.name == "NotesTemplate"))
            ).one_or_none()
            if row:
                await session.delete(row)
            await session.commit()


@pytest.mark.asyncio
async def test_fetch_template_usage_notes_unknown_returns_none():
    out = await fetch_template_usage_notes("00000000-0000-0000-0000-000000000000")
    assert out is None


@pytest.mark.asyncio
async def test_fetch_template_usage_notes_malformed_returns_none():
    out = await fetch_template_usage_notes("not-a-uuid")
    assert out is None


# ---------------------------------------------------------------------------
# fetch_component_summaries / fetch_component_usage_notes — alias resolution
# ---------------------------------------------------------------------------


def _patch_aliases(monkeypatch: pytest.MonkeyPatch, mapping: dict[str, str]) -> None:
    """Replace the live-catalog resolver as seen by metadata_lookup."""

    async def _build():
        return mapping

    from langflow.services.assistant.tools import metadata_lookup as ml

    monkeypatch.setattr(ml, "build_component_name_resolver", _build)


async def _replace_webhook_metadata(*, agent_summary=None, agent_usage_notes=None, updated_by) -> None:
    """Delete any seeded ``Webhook`` row and insert a fresh one for the test."""
    from langflow.services.database.models import ComponentMetadata
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


async def _delete_webhook_metadata() -> None:
    from langflow.services.database.models import ComponentMetadata
    from sqlmodel import select

    async with session_scope() as session:
        row = (
            await session.exec(
                select(ComponentMetadata).where(ComponentMetadata.component_name == "Webhook")
            )
        ).one_or_none()
        if row:
            await session.delete(row)
            await session.commit()


@pytest.mark.asyncio
async def test_fetch_component_summaries_resolves_class_name_alias(
    monkeypatch: pytest.MonkeyPatch, active_super_user
):
    _patch_aliases(
        monkeypatch,
        {
            "Webhook": "Webhook",
            "WebhookComponent": "Webhook",
        },
    )

    await _replace_webhook_metadata(
        agent_summary="canonical summary", updated_by=active_super_user.id
    )
    try:
        result = await fetch_component_summaries(["WebhookComponent", "UnknownThing"])
        assert result["WebhookComponent"] == "canonical summary"
        assert result["UnknownThing"] is None
    finally:
        await _delete_webhook_metadata()


@pytest.mark.asyncio
async def test_fetch_component_usage_notes_resolves_class_name_alias(
    monkeypatch: pytest.MonkeyPatch, active_super_user
):
    _patch_aliases(
        monkeypatch,
        {
            "Webhook": "Webhook",
            "WebhookComponent": "Webhook",
        },
    )

    await _replace_webhook_metadata(
        agent_usage_notes="canonical notes", updated_by=active_super_user.id
    )
    try:
        assert await fetch_component_usage_notes("WebhookComponent") == "canonical notes"
        assert await fetch_component_usage_notes("UnknownThing") is None
    finally:
        await _delete_webhook_metadata()
