"""Tests for get_current_organization resolution with multiple memberships."""
from __future__ import annotations

import asyncio
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

    workspace = Organization(name="Acme", slug=f"acme-{uuid4().hex[:6]}", is_personal=False)
    personal = Organization(name="Personal", slug=f"user-{user.id}", is_personal=True)
    async_session.add(workspace)
    async_session.add(personal)
    await async_session.flush()

    async_session.add(Membership(user_id=user.id, organization_id=workspace.id, role=MembershipRole.OWNER))
    async_session.add(Membership(user_id=user.id, organization_id=personal.id, role=MembershipRole.OWNER))
    await async_session.commit()

    org = await get_current_organization(user=user, session=async_session, x_acting_org_id=None)
    assert org.id == personal.id


@pytest.mark.asyncio
async def test_falls_back_to_earliest_when_no_personal(async_session):
    user = User(username=f"multi2-{uuid4().hex[:6]}", password="x", is_active=True)
    async_session.add(user)
    await async_session.flush()

    first = Organization(name="First", slug=f"first-{uuid4().hex[:6]}", is_personal=False)
    async_session.add(first)
    await async_session.flush()
    await asyncio.sleep(0.01)
    second = Organization(name="Second", slug=f"second-{uuid4().hex[:6]}", is_personal=False)
    async_session.add(second)
    await async_session.flush()

    async_session.add(Membership(user_id=user.id, organization_id=first.id, role=MembershipRole.OWNER))
    async_session.add(Membership(user_id=user.id, organization_id=second.id, role=MembershipRole.OWNER))
    await async_session.commit()

    org = await get_current_organization(user=user, session=async_session, x_acting_org_id=None)
    assert org.id == first.id
