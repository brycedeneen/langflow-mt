"""Regression tests for langflow.services.database.scoping guards.

The `_insert_guard` before-insert hook auto-provisions a personal org +
membership for tenant-scoped inserts whose `user_id` has no membership yet.
It must be idempotent against a User that was *already* given a personal org
by `_user_after_insert` — otherwise the user ends up with two personal orgs
and `get_current_organization` becomes non-deterministic.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.membership.model import Membership
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from sqlmodel import select


@pytest.mark.asyncio
async def test_insert_guard_does_not_duplicate_personal_org(client):  # noqa: ARG001
    """A fresh User + one tenant-scoped insert must leave exactly 1 membership.

    Prior bug: `_insert_guard` used `str(user_id)` in its SELECT, which on
    SQLite does not match the 32-char-no-dash form SQLAlchemy stores. The
    lookup missed, the guard provisioned a second personal org, and the user
    ended up with two.
    """
    async with session_scope() as session:
        user = User(username=f"guard-test-{uuid4().hex[:8]}", password="x", is_active=True)
        session.add(user)
        await session.flush()
        await session.refresh(user)
        user_id = user.id

        # Memberships immediately after user insert — must be exactly 1
        # (_user_after_insert auto-provisioned it).
        mship_after_user = (
            await session.exec(select(Membership).where(Membership.user_id == user_id))
        ).all()
        assert len(mship_after_user) == 1, (
            f"_user_after_insert must provision exactly one membership, got {len(mship_after_user)}"
        )

        # Now force the before_insert guard to run by inserting a tenant-scoped
        # row (Folder) with no organization_id. The guard should resolve it
        # from the existing membership — not provision a new one.
        folder = Folder(user_id=user_id, name="guard-test-folder")
        session.add(folder)
        await session.flush()
        await session.refresh(folder)

        mship_after_folder = (
            await session.exec(select(Membership).where(Membership.user_id == user_id))
        ).all()
        assert len(mship_after_folder) == 1, (
            f"_insert_guard must reuse the existing membership, got {len(mship_after_folder)} "
            f"(guard over-provisioned a duplicate)"
        )

        # And the folder must have been tagged with that same org.
        assert folder.organization_id == mship_after_folder[0].organization_id, (
            "Folder landed in a different org than the user's membership"
        )


@pytest.mark.asyncio
async def test_insert_guard_resolves_via_folder_id(client):  # noqa: ARG001
    """If the row has a folder_id, the guard must resolve via folder, not user_id.

    This covers the same UUID-format bug on the folder lookup path.
    """
    async with session_scope() as session:
        user = User(username=f"guard-folder-{uuid4().hex[:8]}", password="x", is_active=True)
        session.add(user)
        await session.flush()

        folder = Folder(user_id=user.id, name="parent-folder")
        session.add(folder)
        await session.flush()
        await session.refresh(folder)
        parent_folder_id = folder.id
        parent_folder_org = folder.organization_id
        assert parent_folder_org is not None

        # A child insert (flow) that has a folder_id but no organization_id
        # should inherit the folder's org — not fall through to the user_id
        # branch (which would work, but only by accident).
        from langflow.services.database.models.flow.model import Flow

        flow = Flow(user_id=user.id, folder_id=parent_folder_id, name="child-flow", data={})
        session.add(flow)
        await session.flush()
        await session.refresh(flow)

        assert flow.organization_id == parent_folder_org, (
            "Flow must inherit organization_id from its folder"
        )

        # The user should STILL have exactly one membership — the folder
        # lookup succeeded so the guard never hit the provisioning path.
        memberships = (
            await session.exec(select(Membership).where(Membership.user_id == user.id))
        ).all()
        assert len(memberships) == 1, f"Expected 1 membership, got {len(memberships)}"


@pytest.mark.asyncio
async def test_get_current_organization_prefers_oldest_personal_org(client, active_user):  # noqa: ARG001
    """When two personal orgs somehow survive for a user, pick the oldest.

    Covers the defensive tiebreaker added to `get_current_organization` so
    legacy duplicate state doesn't produce non-deterministic org picks.
    """
    from datetime import datetime, timedelta, timezone

    from langflow.api.utils.org_helpers import get_current_organization

    async with session_scope() as session:
        # Fetch the active_user's existing personal org (auto-provisioned by fixture)
        from sqlmodel import select as sql_select
        rows = (await session.exec(sql_select(Membership).where(Membership.user_id == active_user.id))).all()
        org_ids = [r.organization_id for r in rows]
        existing_orgs = (await session.exec(sql_select(Organization).where(Organization.id.in_(org_ids)))).all()
        existing_personal = [o for o in existing_orgs if o.is_personal]
        assert len(existing_personal) == 1, f"Expected 1 personal org, got {len(existing_personal)}"
        original_org = existing_personal[0]
        original_created_at = original_org.created_at

        # Give active_user a *second* personal org + membership deliberately
        # to simulate the legacy-duplicate state. Use naive datetime to match
        # what SQLite retrieves (existing org's created_at loses timezone info).
        newer = Organization(
            name=f"fake-dup-{uuid4().hex[:8]}",
            slug=f"fake-dup-{uuid4().hex[:8]}",
            is_personal=True,
            created_at=original_created_at + timedelta(hours=1) if isinstance(original_created_at, datetime) else datetime.now() + timedelta(hours=1),
        )
        session.add(newer)
        await session.flush()
        session.add(Membership(user_id=active_user.id, organization_id=newer.id))
        await session.commit()

        org = await get_current_organization(user=active_user, session=session, x_acting_org_id=None)

    # Must pick the oldest personal org, not `newer`.
    assert org.id == original_org.id, (
        f"get_current_organization should return the original org {original_org.id}, "
        f"but returned {org.id} instead. The tiebreaker should prefer the earliest-created one."
    )
