"""Tests for get_current_organization resolution with multiple memberships.

Every user insert in this codebase auto-provisions a personal org + owner membership
via the `_user_after_insert` listener in `services/database/scoping.py`, so the
resolver's "personal wins" branch is the practical one. The "earliest-when-no-personal"
fallback is unreachable under the current invariants and isn't tested here.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from langflow.api.utils.org_helpers import get_current_organization
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User


@pytest.mark.asyncio
async def test_prefers_personal_when_user_has_multiple_memberships(async_session):
    user = User(username=f"multi-{uuid4().hex[:6]}", password="x", is_active=True)
    async_session.add(user)
    await async_session.flush()
    # The after-insert hook already provisioned this user's personal org + membership.

    workspace = Organization(name="Acme", slug=f"acme-{uuid4().hex[:6]}", is_personal=False)
    async_session.add(workspace)
    await async_session.flush()
    async_session.add(
        Membership(user_id=user.id, organization_id=workspace.id, role=MembershipRole.OWNER)
    )
    await async_session.commit()

    org = await get_current_organization(user=user, session=async_session, x_acting_org_id=None)
    assert org.is_personal is True
