"""Shared fixtures for tests under `src/backend/tests/unit/api/v1/admin/`."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

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
