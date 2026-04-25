"""Unit tests for the apply_template assistant tool."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlmodel import select

from langflow.services.assistant.tools.template_apply import apply_template
from langflow.services.database.models import Flow
from langflow.services.database.models.template.model import Template
from langflow.services.deps import session_scope


@pytest.mark.asyncio
async def test_apply_template_copies_nodes_and_sets_pointer(active_super_user):
    """Happy-path: Template's nodes are written to target, pointer is set."""
    async with session_scope() as session:
        template = Template(
            name="Source Tpl",
            scope="platform",
            nodes=[{"id": "Webhook-aaaaa", "data": {"id": "Webhook-aaaaa", "type": "Webhook"}}],
            edges=[],
        )
        session.add(template)
        await session.commit()
        await session.refresh(template)

        target = Flow(name="Empty", user_id=active_super_user.id, data={"nodes": [], "edges": []})
        session.add(target)
        await session.commit()
        await session.refresh(target)

        target_id, template_id = str(target.id), str(template.id)

    result = await apply_template(target_flow_id=target_id, template_id=template_id)
    assert "applied_patch" in result, result
    assert result["template_name"] == "Source Tpl"
    assert len(result["applied_patch"]["added_nodes"]) == 1

    async with session_scope() as session:
        updated = (await session.exec(select(Flow).where(Flow.id == UUID(target_id)))).one()
        assert updated.based_on_template_id == UUID(template_id)
        assert len(updated.data["nodes"]) == 1
        # Node id was regenerated — not equal to template's
        assert updated.data["nodes"][0]["id"] != "Webhook-aaaaa"


@pytest.mark.asyncio
async def test_apply_template_rejects_non_empty_target(active_super_user):
    """Refuses when target flow already has nodes."""
    async with session_scope() as session:
        template = Template(
            name="Tpl-Non-Empty",
            scope="platform",
            nodes=[{"id": "n1"}],
            edges=[],
        )
        session.add(template)
        target = Flow(
            name="Not empty",
            user_id=active_super_user.id,
            data={
                "nodes": [{"id": "Existing-11111", "data": {"id": "Existing-11111", "type": "Existing"}}],
                "edges": [],
            },
        )
        session.add(target)
        await session.commit()
        await session.refresh(template)
        await session.refresh(target)
        target_id, template_id = str(target.id), str(template.id)

    result = await apply_template(target_flow_id=target_id, template_id=template_id)
    assert "error" in result
    assert "not empty" in result["error"].lower()


@pytest.mark.asyncio
async def test_apply_template_rejects_archived_template(active_super_user):
    """Refuses when the template is archived."""
    async with session_scope() as session:
        template = Template(
            name="Archived Tpl",
            scope="platform",
            nodes=[],
            edges=[],
            archived_at=datetime.now(timezone.utc),
        )
        session.add(template)
        target = Flow(name="Blank", user_id=active_super_user.id, data={"nodes": [], "edges": []})
        session.add(target)
        await session.commit()
        await session.refresh(template)
        await session.refresh(target)
        target_id, template_id = str(target.id), str(template.id)

    result = await apply_template(target_flow_id=target_id, template_id=template_id)
    assert "error" in result
    assert "archived" in result["error"].lower()


@pytest.mark.asyncio
async def test_apply_template_unknown_template_returns_error(active_super_user):
    """Returns an error dict when the template UUID doesn't exist."""
    async with session_scope() as session:
        target = Flow(name="Blank2", user_id=active_super_user.id, data={"nodes": [], "edges": []})
        session.add(target)
        await session.commit()
        await session.refresh(target)
        target_id = str(target.id)

    result = await apply_template(
        target_flow_id=target_id,
        template_id="00000000-0000-0000-0000-000000000000",
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_apply_template_unknown_flow_id_errors():
    """Returns an error dict when neither target nor template exists."""
    result = await apply_template(
        target_flow_id="00000000-0000-0000-0000-000000000000",
        template_id="00000000-0000-0000-0000-000000000001",
    )
    assert "error" in result
