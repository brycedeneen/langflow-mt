"""TDD tests for apply_template org-isolation (5C).

Verifies that a caller from org_A cannot overwrite a flow owned by org_B,
and that a same-org call still succeeds.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import select

from langflow.services.assistant.tools.template_apply import apply_template
from langflow.services.database.models import Flow, Folder
from langflow.services.database.models.flow.starter import STARTER_FOLDER_NAME
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_org(session, slug_suffix: str) -> Organization:
    org = Organization(
        name=f"test-org-{slug_suffix}",
        slug=f"test-org-{slug_suffix}",
        is_personal=False,
    )
    session.add(org)
    await session.flush()
    await session.refresh(org)
    return org


async def _make_user(session, username: str) -> User:
    user = User(
        username=username,
        password="hashed_pw_placeholder",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _make_template_flow(session, user_id, org_id=None) -> Flow:
    """Create a starter-project template flow in the STARTER_FOLDER_NAME folder."""
    folder = Folder(name=STARTER_FOLDER_NAME, user_id=user_id, organization_id=org_id)
    session.add(folder)
    await session.flush()
    await session.refresh(folder)

    template = Flow(
        name="Test Template",
        user_id=user_id,
        folder_id=folder.id,
        organization_id=org_id,
        data={
            "nodes": [{"id": "Node-abc", "data": {"id": "Node-abc", "type": "Webhook"}}],
            "edges": [],
        },
    )
    session.add(template)
    await session.flush()
    await session.refresh(template)
    return template


async def _make_target_flow(session, user_id, org_id=None) -> Flow:
    """Create a blank target flow."""
    flow = Flow(
        name="Victim Flow",
        user_id=user_id,
        organization_id=org_id,
        data={"nodes": [], "edges": []},
    )
    session.add(flow)
    await session.flush()
    await session.refresh(flow)
    return flow


# ---------------------------------------------------------------------------
# Test 1: Cross-org target is rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_template_cross_org_target_rejected(active_super_user, monkeypatch):
    """org_A actor must NOT be able to overwrite org_B's flow."""
    # Monkeypatch is_flow_a_starter_project_async so the template check passes
    # without needing to satisfy its full folder-name resolution logic.
    from langflow.services.database.models.flow import starter as starter_mod
    monkeypatch.setattr(starter_mod, "is_flow_a_starter_project_async", lambda _flow, _session: True)

    suffix = uuid.uuid4().hex[:8]

    async with session_scope() as session:
        org_a = await _make_org(session, f"a-{suffix}")
        org_b = await _make_org(session, f"b-{suffix}")
        user_a = await _make_user(session, f"user-a-{suffix}")
        user_b = await _make_user(session, f"user-b-{suffix}")

        template = await _make_template_flow(session, user_a.id, org_id=org_a.id)
        victim = await _make_target_flow(session, user_b.id, org_id=org_b.id)

        original_data = dict(victim.data)
        original_template_ptr = victim.based_on_template_flow_id

        target_id = str(victim.id)
        template_id = str(template.id)
        org_a_id = org_a.id
        org_b_id = org_b.id

        await session.commit()

    # Actor is in org_A; victim belongs to org_B — should be rejected.
    result = await apply_template(
        target_flow_id=target_id,
        template_flow_id=template_id,
        actor_org_id=org_a_id,
    )

    assert "error" in result, f"Expected error, got: {result}"
    assert result["error"] == "Target flow not found."

    # Verify the victim flow in the DB is UNCHANGED.
    async with session_scope() as session:
        from uuid import UUID
        db_victim = (await session.exec(select(Flow).where(Flow.id == UUID(target_id)))).one()
        assert db_victim.data == original_data, (
            f"Victim data was mutated! Before={original_data}, After={db_victim.data}"
        )
        assert db_victim.based_on_template_flow_id == original_template_ptr, (
            "Victim based_on_template_flow_id was changed!"
        )

    # Cleanup
    async with session_scope() as session:
        for obj_id, model in [
            (UUID(target_id), Flow),
            (UUID(template_id), Flow),
            (org_a_id, Organization),
            (org_b_id, Organization),
            (user_a.id, User),
            (user_b.id, User),
        ]:
            row = await session.get(model, obj_id)
            if row is not None:
                await session.delete(row)
        await session.commit()


# ---------------------------------------------------------------------------
# Test 2: Same-org target succeeds (positive control)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_template_same_org_target_succeeds(active_super_user, monkeypatch):
    """org_A actor CAN overwrite an org_A flow."""
    from langflow.services.database.models.flow import starter as starter_mod
    monkeypatch.setattr(starter_mod, "is_flow_a_starter_project_async", lambda _flow, _session: True)

    suffix = uuid.uuid4().hex[:8]

    async with session_scope() as session:
        org = await _make_org(session, f"same-{suffix}")
        user = await _make_user(session, f"user-same-{suffix}")

        template = await _make_template_flow(session, user.id, org_id=org.id)
        target = await _make_target_flow(session, user.id, org_id=org.id)

        target_id = str(target.id)
        template_id = str(template.id)
        org_id = org.id

        await session.commit()

    result = await apply_template(
        target_flow_id=target_id,
        template_flow_id=template_id,
        actor_org_id=org_id,
    )

    assert "applied_patch" in result, f"Expected success, got: {result}"
    assert result["template_name"] == "Test Template"
    assert len(result["applied_patch"]["added_nodes"]) == 1

    # Verify the target's pointer was set.
    async with session_scope() as session:
        from uuid import UUID
        updated = (await session.exec(select(Flow).where(Flow.id == UUID(target_id)))).one()
        assert updated.based_on_template_flow_id == UUID(template_id)
        assert len(updated.data["nodes"]) == 1

    # Cleanup
    async with session_scope() as session:
        for obj_id, model in [
            (UUID(target_id), Flow),
            (UUID(template_id), Flow),
            (org_id, Organization),
            (user.id, User),
        ]:
            row = await session.get(model, obj_id)
            if row is not None:
                await session.delete(row)
        await session.commit()
