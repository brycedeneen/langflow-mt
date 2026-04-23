"""Shared fixtures for tests under `src/backend/tests/unit/api/v1/`."""
from __future__ import annotations

import uuid
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope


@pytest.fixture
async def platform_admin_user(client: AsyncClient):  # noqa: ARG001
    """Create a user with is_platform_admin=True."""
    uid = uuid4()
    async with session_scope() as session:
        user = User(
            id=uid,
            username=f"platform_admin_{uid}",
            password=get_auth_service().get_password_hash("adminpassword"),
            is_active=True,
            is_superuser=False,
            is_platform_admin=True,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        username = user.username

    yield {"id": str(uid), "username": username}

    async with session_scope() as session:
        db_user = await session.get(User, uid)
        if db_user:
            await session.delete(db_user)


@pytest.fixture
async def admin_headers(client: AsyncClient, platform_admin_user):
    """JWT headers for the platform admin user."""
    resp = await client.post(
        "api/v1/login",
        data={"username": platform_admin_user["username"], "password": "adminpassword"},
    )
    assert resp.status_code == status.HTTP_200_OK
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def login_as(client: AsyncClient, username: str, password: str = "testpassword") -> dict[str, str]:
    """Log in as ``username`` and return the Authorization header for JWT auth.

    Promoted from the per-test ``_login`` helper so Tasks 5–7 (and any future
    custom-component-gate enforcement tests) can share one copy. The default
    ``password`` matches the value used by ``tenant_and_admin`` and by the
    2026-04-22 cross-org security regression tests.
    """
    resp = await client.post(
        "api/v1/login",
        data={"username": username, "password": password},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def tenant_and_admin(client: AsyncClient):  # noqa: ARG001
    """Provision one tenant (org member, not platform admin) and one platform admin.

    Both users share a single org so tests exercising the custom-component gate
    can flip between identity postures without re-seeding org membership. Used
    by Task 4 (execution gate) and will be reused by Tasks 5-7 (create / upload
    / template-create gates) which follow the same enforcement pattern.
    """
    slug = uuid.uuid4().hex[:8]
    async with session_scope() as session:
        org = Organization(name=f"OrgG-{slug}", slug=f"org-g-{slug}", is_personal=True)
        tenant = User(
            username=f"tenant-{slug}",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_platform_admin=False,
        )
        admin = User(
            username=f"admin-{slug}",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_platform_admin=True,
        )
        session.add_all([org, tenant, admin])
        await session.flush()
        session.add_all([
            Membership(user_id=tenant.id, organization_id=org.id, role=MembershipRole.OWNER),
            Membership(user_id=admin.id, organization_id=org.id, role=MembershipRole.OWNER),
        ])
        await session.commit()
        for obj in (org, tenant, admin):
            await session.refresh(obj)
        ids = {
            "org_id": org.id,
            "tenant_id": tenant.id,
            "tenant_username": tenant.username,
            "admin_id": admin.id,
            "admin_username": admin.username,
        }

    yield ids

    async with session_scope() as session:
        for model, pk in [
            (User, ids["tenant_id"]),
            (User, ids["admin_id"]),
            (Organization, ids["org_id"]),
        ]:
            row = await session.get(model, pk)
            if row is not None:
                await session.delete(row)
        await session.commit()
