"""Tests for GET /api/v1/memberships/me."""

from __future__ import annotations

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def seed_user_with_one_org_membership(client: AsyncClient):  # noqa: ARG001
    """Create a fresh user, log them in, create an org, and add them as OWNER.

    Yields (user, org, headers).

    NOTE: Inserting a User triggers the after-insert hook in scoping.py which
    auto-provisions a personal org + personal membership.  We create an
    *additional* non-personal org here so we can assert on the exact count.
    """
    uid = uuid.uuid4()
    password = "membership-test-pw"

    async with session_scope() as session:
        user = User(
            id=uid,
            username=f"mem_test_{uid.hex[:8]}",
            password=get_auth_service().get_password_hash(password),
            is_active=True,
            is_superuser=False,
            is_platform_admin=False,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        username = user.username

    # Log in to get auth headers.
    resp = await client.post(
        "api/v1/login",
        data={"username": username, "password": password},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create a non-personal org and add the user as OWNER.
    org_id = uuid.uuid4()
    async with session_scope() as session:
        org = Organization(
            id=org_id,
            name=f"Test Org {org_id.hex[:6]}",
            slug=f"test-org-{org_id.hex[:6]}",
            is_personal=False,
        )
        session.add(org)
        await session.flush()
        await session.refresh(org)

        m = Membership(
            user_id=uid,
            organization_id=org_id,
            role=MembershipRole.OWNER,
        )
        session.add(m)

    yield uid, org_id, headers

    # Cleanup: membership, org, and user (cascade handles dependent rows).
    async with session_scope() as session:
        m_obj = (
            await session.exec(
                __import__("sqlmodel", fromlist=["select"]).select(Membership)
                .where(Membership.user_id == uid)
                .where(Membership.organization_id == org_id)
            )
        ).one_or_none()
        if m_obj is not None:
            await session.delete(m_obj)
        await session.flush()

        org_obj = await session.get(Organization, org_id)
        if org_obj is not None:
            await session.delete(org_obj)
        await session.flush()

        user_obj = await session.get(User, uid)
        if user_obj is not None:
            await session.delete(user_obj)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_my_memberships_empty(client: AsyncClient, logged_in_headers: dict) -> None:
    """A user created by the standard fixture may have a personal org membership.

    Either [] or a non-empty list is fine — we only assert the shape.
    """
    res = await client.get("/api/v1/memberships/me", headers=logged_in_headers)
    assert res.status_code == status.HTTP_200_OK
    body = res.json()
    assert isinstance(body, list)
    for row in body:
        assert "id" in row and "role" in row and "organization" in row
        assert set(row["organization"].keys()) >= {"id", "name", "slug", "is_personal"}


@pytest.mark.asyncio
async def test_list_my_memberships_for_user_with_one_org(
    client: AsyncClient,
    seed_user_with_one_org_membership,
) -> None:
    """A user seeded with one non-personal org membership must appear in results."""
    user_id, org_id, headers = seed_user_with_one_org_membership
    res = await client.get("/api/v1/memberships/me", headers=headers)
    assert res.status_code == status.HTTP_200_OK, res.text
    body = res.json()
    # There may be more rows (e.g., a personal org from the after-insert hook).
    org_ids = [row["organization"]["id"] for row in body]
    assert str(org_id) in org_ids, f"Expected org {org_id} in {org_ids}"
    # Find the specific row we seeded.
    row = next(r for r in body if r["organization"]["id"] == str(org_id))
    assert row["is_org_admin"] is True  # seeded as OWNER
    assert row["role"] == MembershipRole.OWNER.value


@pytest.mark.asyncio
async def test_list_my_memberships_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/api/v1/memberships/me")
    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
