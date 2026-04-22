"""Fixtures local to admin-endpoint tests.

These fixtures build on the shared `platform_admin_user` / `admin_headers`
fixtures promoted into `src/backend/tests/unit/api/v1/conftest.py`.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope


async def _login(client: AsyncClient, username: str, password: str) -> dict[str, str]:
    resp = await client.post(
        "api/v1/login",
        data={"username": username, "password": password},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_user(
    username: str,
    password: str = "secret123",
    *,
    is_platform_admin: bool = False,
) -> UUID:
    uid = uuid4()
    async with session_scope() as session:
        user = User(
            id=uid,
            username=username,
            password=get_auth_service().get_password_hash(password),
            is_active=True,
            is_superuser=False,
            is_platform_admin=is_platform_admin,
        )
        session.add(user)
        await session.flush()
    return uid


async def _delete_user(user_id: UUID) -> None:
    async with session_scope() as session:
        # Remove memberships first, then the user (personal org is auto-created
        # via trigger and owned by this user; drop it too).
        memberships = (
            await session.exec(select(Membership).where(Membership.user_id == user_id))
        ).all()
        personal_org_ids: list[UUID] = []
        for m in memberships:
            org = await session.get(Organization, m.organization_id)
            if org is not None and org.is_personal:
                personal_org_ids.append(org.id)
            await session.delete(m)
        for org_id in personal_org_ids:
            org = await session.get(Organization, org_id)
            if org is not None:
                await session.delete(org)
        db_user = await session.get(User, user_id)
        if db_user:
            await session.delete(db_user)


async def _delete_org(org_id: UUID) -> None:
    async with session_scope() as session:
        memberships = (
            await session.exec(
                select(Membership).where(Membership.organization_id == org_id)
            )
        ).all()
        for m in memberships:
            await session.delete(m)
        org = await session.get(Organization, org_id)
        if org is not None:
            await session.delete(org)


@pytest.fixture
async def org_with_member(client: AsyncClient, platform_admin_user):  # noqa: ARG001
    """Non-personal org. Platform admin is Owner; a second user is a Member."""
    org_id = uuid4()
    target_user_id = uuid4()
    async with session_scope() as session:
        org = Organization(
            id=org_id,
            name=f"OrgWithMember {org_id.hex[:6]}",
            slug=f"org-with-member-{org_id.hex[:8]}",
            is_personal=False,
        )
        session.add(org)

        target = User(
            id=target_user_id,
            username=f"target_user_{target_user_id.hex[:8]}",
            password=get_auth_service().get_password_hash("secret123"),
            is_active=True,
            is_superuser=False,
            is_platform_admin=False,
        )
        session.add(target)
        await session.flush()

        session.add(
            Membership(
                user_id=UUID(platform_admin_user["id"]),
                organization_id=org_id,
                role=MembershipRole.OWNER,
            )
        )
        session.add(
            Membership(
                user_id=target_user_id,
                organization_id=org_id,
                role=MembershipRole.MEMBER,
            )
        )
        await session.flush()

    yield {"org_id": str(org_id), "user_id": str(target_user_id)}

    await _delete_org(org_id)
    await _delete_user(target_user_id)


@pytest.fixture
async def sole_owner_org(client: AsyncClient):  # noqa: ARG001
    """Non-personal org where exactly one user is the Owner."""
    org_id = uuid4()
    owner_id = uuid4()
    async with session_scope() as session:
        owner = User(
            id=owner_id,
            username=f"sole_owner_{owner_id.hex[:8]}",
            password=get_auth_service().get_password_hash("secret123"),
            is_active=True,
            is_superuser=False,
            is_platform_admin=False,
        )
        session.add(owner)
        org = Organization(
            id=org_id,
            name=f"SoleOwnerOrg {org_id.hex[:6]}",
            slug=f"sole-owner-{org_id.hex[:8]}",
            is_personal=False,
        )
        session.add(org)
        await session.flush()
        session.add(
            Membership(
                user_id=owner_id,
                organization_id=org_id,
                role=MembershipRole.OWNER,
            )
        )
        await session.flush()

    yield {"org_id": str(org_id), "owner_id": str(owner_id)}

    await _delete_org(org_id)
    await _delete_user(owner_id)


@pytest.fixture
async def personal_org(client: AsyncClient):  # noqa: ARG001
    """Auto-created personal org for a freshly-made user."""
    user_id = uuid4()
    async with session_scope() as session:
        user = User(
            id=user_id,
            username=f"personal_org_user_{user_id.hex[:8]}",
            password=get_auth_service().get_password_hash("secret123"),
            is_active=True,
            is_superuser=False,
            is_platform_admin=False,
        )
        session.add(user)
        await session.flush()

        # The User insert trigger creates the personal org + owner Membership.
        membership = (
            await session.exec(
                select(Membership).where(Membership.user_id == user_id)
            )
        ).first()
        assert membership is not None, "expected auto-created personal-org membership"
        org_id = membership.organization_id

    yield {"org_id": str(org_id), "user_id": str(user_id)}

    await _delete_user(user_id)


@pytest.fixture
async def org_admin_headers(client: AsyncClient, org_with_member):
    """Headers for a user who is ADMIN in `org_with_member` (not an Owner)."""
    username = f"org_admin_{uuid4().hex[:8]}"
    password = "secret123"
    user_id = await _create_user(username, password)
    async with session_scope() as session:
        session.add(
            Membership(
                user_id=user_id,
                organization_id=UUID(org_with_member["org_id"]),
                role=MembershipRole.ADMIN,
            )
        )
        await session.flush()

    headers = await _login(client, username, password)
    yield headers

    await _delete_user(user_id)


@pytest.fixture
async def viewer_headers(client: AsyncClient, org_with_member):
    """Headers for a user who is VIEWER in `org_with_member`."""
    username = f"viewer_{uuid4().hex[:8]}"
    password = "secret123"
    user_id = await _create_user(username, password)
    async with session_scope() as session:
        session.add(
            Membership(
                user_id=user_id,
                organization_id=UUID(org_with_member["org_id"]),
                role=MembershipRole.VIEWER,
            )
        )
        await session.flush()

    headers = await _login(client, username, password)
    yield headers

    await _delete_user(user_id)
