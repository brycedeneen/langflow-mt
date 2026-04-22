"""Tests for PATCH /api/v1/users/{user_id} accepting `is_platform_admin`.

See Task 9 of the "User Detail Page & Role Expansion" plan.

The existing `PATCH /users/{user_id}` endpoint uses `is_superuser` as its
privilege gate — it refuses to let non-superusers modify other users at all
(see `src/backend/base/langflow/api/v1/users.py`). That existing guard also
transitively protects `is_platform_admin`: a non-superuser caller hitting
this endpoint against another user gets 403 before any field-level logic
runs (Option A in the plan — no new explicit `is_platform_admin` gate).
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope


@pytest.fixture
async def seeded_user(client: AsyncClient):  # noqa: ARG001
    """Create a plain user that can be the PATCH target.

    Style mirrors `platform_admin_user` in the shared conftest and
    `_create_user` helper in `admin/conftest.py`.
    """
    uid = uuid4()
    async with session_scope() as session:
        user = User(
            id=uid,
            username=f"seeded_{uid.hex[:8]}",
            password=get_auth_service().get_password_hash("seeded_password"),
            is_active=True,
            is_superuser=False,
            is_platform_admin=False,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        user_dict = {"id": str(uid), "username": user.username}

    yield user_dict

    async with session_scope() as session:
        db_user = await session.get(User, uid)
        if db_user:
            await session.delete(db_user)


async def test_platform_admin_flag_can_be_set_via_patch(
    client: AsyncClient, logged_in_headers_super_user, seeded_user
):
    """A superuser PATCHing another user can set `is_platform_admin=True`.

    We use `logged_in_headers_super_user` (not `admin_headers`) because the
    existing endpoint's privilege gate is `is_superuser`, and the shared
    `admin_headers` fixture is a *platform* admin but not a superuser — it
    would hit the "non-superusers can't modify other users" 403 guard.
    """
    r = await client.patch(
        f"api/v1/users/{seeded_user['id']}",
        headers=logged_in_headers_super_user,
        json={"is_platform_admin": True},
    )
    assert r.status_code == status.HTTP_200_OK, r.text
    body = r.json()
    assert body["is_platform_admin"] is True


async def test_non_superuser_cannot_set_platform_admin(
    client: AsyncClient, logged_in_headers, seeded_user
):
    """A non-superuser caller PATCHing another user is blocked with 403.

    This passes "by accident" (Option A in the plan) via the existing
    "non-superusers can't modify other users" guard — there is no
    explicit `is_platform_admin` privilege check in the endpoint.
    """
    r = await client.patch(
        f"api/v1/users/{seeded_user['id']}",
        headers=logged_in_headers,
        json={"is_platform_admin": True},
    )
    assert r.status_code == status.HTTP_403_FORBIDDEN
