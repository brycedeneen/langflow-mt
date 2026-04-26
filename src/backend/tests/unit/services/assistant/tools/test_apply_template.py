"""Unit tests for the apply_template assistant tool."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlmodel import select

from langflow.services.assistant.tools.template_apply import apply_template
from langflow.services.database.models import Flow
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.template.model import Template
from langflow.services.deps import session_scope


async def _make_test_org(session) -> Organization:
    slug = uuid.uuid4().hex[:8]
    org = Organization(name=f"test-org-{slug}", slug=f"test-org-{slug}", is_personal=False)
    session.add(org)
    await session.flush()
    await session.refresh(org)
    return org


@pytest.mark.asyncio
async def test_apply_template_copies_nodes_and_sets_pointer(active_super_user):
    """Happy-path: Template's nodes are written to target, pointer is set."""
    async with session_scope() as session:
        org = await _make_test_org(session)
        template = Template(
            name="Source Tpl",
            scope="platform",
            nodes=[{"id": "Webhook-aaaaa", "data": {"id": "Webhook-aaaaa", "type": "Webhook"}}],
            edges=[],
        )
        session.add(template)
        target = Flow(
            name="Empty",
            user_id=active_super_user.id,
            organization_id=org.id,
            data={"nodes": [], "edges": []},
        )
        session.add(target)
        await session.commit()
        await session.refresh(template)
        await session.refresh(target)

        target_id, template_id = str(target.id), str(template.id)
        actor_org_id = org.id

    result = await apply_template(
        target_flow_id=target_id,
        template_id=template_id,
        actor_org_id=actor_org_id,
    )
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
        org = await _make_test_org(session)
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
            organization_id=org.id,
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
        actor_org_id = org.id

    result = await apply_template(
        target_flow_id=target_id,
        template_id=template_id,
        actor_org_id=actor_org_id,
    )
    assert "error" in result
    assert "not empty" in result["error"].lower()


@pytest.mark.asyncio
async def test_apply_template_rejects_archived_template(active_super_user):
    """Refuses when the template is archived."""
    async with session_scope() as session:
        org = await _make_test_org(session)
        template = Template(
            name="Archived Tpl",
            scope="platform",
            nodes=[],
            edges=[],
            archived_at=datetime.now(timezone.utc),
        )
        session.add(template)
        target = Flow(
            name="Blank",
            user_id=active_super_user.id,
            organization_id=org.id,
            data={"nodes": [], "edges": []},
        )
        session.add(target)
        await session.commit()
        await session.refresh(template)
        await session.refresh(target)
        target_id, template_id = str(target.id), str(template.id)
        actor_org_id = org.id

    result = await apply_template(
        target_flow_id=target_id,
        template_id=template_id,
        actor_org_id=actor_org_id,
    )
    assert "error" in result
    assert "archived" in result["error"].lower()


@pytest.mark.asyncio
async def test_apply_template_unknown_template_returns_error(active_super_user):
    """Returns an error dict when the template UUID doesn't exist."""
    async with session_scope() as session:
        org = await _make_test_org(session)
        target = Flow(
            name="Blank2",
            user_id=active_super_user.id,
            organization_id=org.id,
            data={"nodes": [], "edges": []},
        )
        session.add(target)
        await session.commit()
        await session.refresh(target)
        target_id = str(target.id)
        actor_org_id = org.id

    result = await apply_template(
        target_flow_id=target_id,
        template_id="00000000-0000-0000-0000-000000000000",
        actor_org_id=actor_org_id,
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_apply_template_unknown_flow_id_errors():
    """Returns an error dict when neither target nor template exists."""
    result = await apply_template(
        target_flow_id="00000000-0000-0000-0000-000000000000",
        template_id="00000000-0000-0000-0000-000000000001",
        actor_org_id=uuid.uuid4(),
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_apply_template_rejects_cross_org_target(active_super_user):
    """Cross-org regression: target in a DIFFERENT org from actor returns 'not found'.

    Backports the security guard from p1/batch-1: actor_org_id must match the
    target flow's organization_id, otherwise apply_template refuses without
    leaking the target's existence.
    """
    async with session_scope() as session:
        actor_org = await _make_test_org(session)
        target_org = await _make_test_org(session)
        template = Template(name="Tpl-CrossOrg", scope="platform", nodes=[], edges=[])
        session.add(template)
        target = Flow(
            name="OtherOrgFlow",
            user_id=active_super_user.id,
            organization_id=target_org.id,  # NOT actor_org.id
            data={"nodes": [], "edges": []},
        )
        session.add(target)
        await session.commit()
        await session.refresh(template)
        await session.refresh(target)
        target_id, template_id = str(target.id), str(template.id)
        actor_org_id = actor_org.id

    result = await apply_template(
        target_flow_id=target_id,
        template_id=template_id,
        actor_org_id=actor_org_id,
    )
    assert "error" in result
    assert "not found" in result["error"].lower()
