"""Tests for `GET /api/v1/admin/users/{user_id}`."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope


@pytest.fixture
async def seeded_user_with_memberships(client: AsyncClient):  # noqa: ARG001
    """Seed a user that belongs to its auto-created personal org plus two
    non-personal orgs.

    The User insert trigger (see `services/database/scoping.py`) creates a
    personal workspace for every new user and adds an owner Membership, so we
    only need to add the non-personal ones here.

    Non-personal org names ``"Alpha Org"`` and ``"Beta Org"`` test
    alphabetical ordering *after* the personal org is placed first.
    """
    user_id = uuid4()
    alpha_id = uuid4()
    beta_id = uuid4()

    async with session_scope() as session:
        user = User(
            id=user_id,
            username=f"detail_user_{user_id.hex[:8]}",
            password=get_auth_service().get_password_hash("secret123"),
            is_active=True,
            is_superuser=False,
            is_platform_admin=False,
        )
        session.add(user)
        # Deliberately create "Beta Org" before "Alpha Org" to verify that the
        # endpoint's sort (alphabetical, personal-first) wins over insertion order.
        beta = Organization(
            id=beta_id,
            name="Beta Org",
            slug=f"beta-org-{beta_id.hex[:8]}",
            is_personal=False,
        )
        alpha = Organization(
            id=alpha_id,
            name="Alpha Org",
            slug=f"alpha-org-{alpha_id.hex[:8]}",
            is_personal=False,
        )
        session.add(beta)
        session.add(alpha)
        await session.flush()

        session.add(
            Membership(
                user_id=user_id,
                organization_id=beta_id,
                role=MembershipRole.MEMBER,
            )
        )
        session.add(
            Membership(
                user_id=user_id,
                organization_id=alpha_id,
                role=MembershipRole.ADMIN,
            )
        )
        await session.flush()
        username = user.username

    yield {
        "id": str(user_id),
        "username": username,
        "alpha_org_id": str(alpha_id),
        "beta_org_id": str(beta_id),
    }

    async with session_scope() as session:
        from sqlmodel import select as _select

        memberships = (
            await session.exec(
                _select(Membership).where(Membership.user_id == user_id)
            )
        ).all()
        for m in memberships:
            await session.delete(m)
        for org_id in (alpha_id, beta_id):
            org = await session.get(Organization, org_id)
            if org:
                await session.delete(org)
        db_user = await session.get(User, user_id)
        if db_user:
            await session.delete(db_user)


async def test_get_user_detail_success(
    client: AsyncClient, admin_headers, seeded_user_with_memberships
):
    """Platform admin can fetch user detail; personal org sorts first, then
    non-personal orgs alphabetically by name."""
    user_id = seeded_user_with_memberships["id"]
    resp = await client.get(f"api/v1/admin/users/{user_id}", headers=admin_headers)
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()
    assert data["id"] == user_id
    assert data["username"] == seeded_user_with_memberships["username"]
    assert data["is_active"] is True
    assert data["is_platform_admin"] is False
    assert data["is_superuser"] is False
    assert "create_at" in data
    assert "updated_at" in data
    assert "last_login_at" in data

    memberships = data["memberships"]
    # Expect 3: auto-created personal workspace + Alpha Org + Beta Org.
    assert len(memberships) == 3

    # Personal org first.
    assert memberships[0]["is_personal"] is True

    # Non-personal orgs follow, alphabetically by name — Alpha before Beta
    # (even though Beta was inserted first).
    assert memberships[1]["is_personal"] is False
    assert memberships[1]["organization_id"] == seeded_user_with_memberships["alpha_org_id"]
    assert memberships[1]["organization_name"] == "Alpha Org"
    assert memberships[1]["role"] == "admin"

    assert memberships[2]["is_personal"] is False
    assert memberships[2]["organization_id"] == seeded_user_with_memberships["beta_org_id"]
    assert memberships[2]["organization_name"] == "Beta Org"
    assert memberships[2]["role"] == "member"

    for m in memberships:
        assert "joined_at" in m
        assert "organization_id" in m
        assert "organization_name" in m


async def test_get_user_detail_not_found(client: AsyncClient, admin_headers):
    """GET against an unknown user id returns 404."""
    missing_id = str(uuid4())
    resp = await client.get(f"api/v1/admin/users/{missing_id}", headers=admin_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_get_user_detail_requires_platform_admin(
    client: AsyncClient, logged_in_headers, seeded_user_with_memberships
):
    """Non-platform-admin caller gets 403."""
    user_id = seeded_user_with_memberships["id"]
    resp = await client.get(f"api/v1/admin/users/{user_id}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN
