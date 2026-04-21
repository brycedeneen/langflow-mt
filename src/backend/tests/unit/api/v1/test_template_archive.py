"""Tests for POST /api/v1/templates/{id}/archive and /unarchive (Phase C5)."""

from __future__ import annotations

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.template.model import Template
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def platform_admin_user(client: AsyncClient):  # noqa: ARG001
    uid = uuid.uuid4()
    async with session_scope() as session:
        user = User(
            id=uid,
            username=f"padmin_{uid}",
            password=get_auth_service().get_password_hash("adminpass"),
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
async def regular_user(client: AsyncClient):  # noqa: ARG001
    uid = uuid.uuid4()
    async with session_scope() as session:
        user = User(
            id=uid,
            username=f"regular_{uid}",
            password=get_auth_service().get_password_hash("regularpass"),
            is_active=True,
            is_superuser=False,
            is_platform_admin=False,
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
    resp = await client.post(
        "api/v1/login",
        data={"username": platform_admin_user["username"], "password": "adminpass"},
    )
    assert resp.status_code == status.HTTP_200_OK
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def regular_headers(client: AsyncClient, regular_user):
    resp = await client.post(
        "api/v1/login",
        data={"username": regular_user["username"], "password": "regularpass"},
    )
    assert resp.status_code == status.HTTP_200_OK
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def platform_template(platform_admin_user):
    admin_uid = uuid.UUID(platform_admin_user["id"])
    async with session_scope() as session:
        t = Template(
            name=f"ArchivableTemplate-{uuid.uuid4()}",
            nodes=[],
            edges=[],
            scope="platform",
            created_by=admin_uid,
            updated_by=admin_uid,
        )
        session.add(t)
        await session.flush()
        await session.refresh(t)
        tmpl_id = t.id

    yield tmpl_id

    async with session_scope() as session:
        db = await session.get(Template, tmpl_id)
        if db:
            await session.delete(db)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_archive_sets_timestamp(
    client: AsyncClient,
    admin_headers,
    platform_template,
):
    """Archiving a template sets archived_at to a non-null timestamp."""
    resp = await client.post(
        f"api/v1/templates/{platform_template}/archive",
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["archived_at"] is not None

    # Confirm in DB
    async with session_scope() as session:
        tmpl = await session.get(Template, platform_template)
        assert tmpl is not None
        assert tmpl.archived_at is not None


async def test_archive_is_idempotent(
    client: AsyncClient,
    admin_headers,
    platform_template,
):
    """Archiving twice returns 200 both times, timestamp unchanged."""
    resp1 = await client.post(
        f"api/v1/templates/{platform_template}/archive",
        headers=admin_headers,
    )
    assert resp1.status_code == status.HTTP_200_OK
    ts1 = resp1.json()["archived_at"]

    resp2 = await client.post(
        f"api/v1/templates/{platform_template}/archive",
        headers=admin_headers,
    )
    assert resp2.status_code == status.HTTP_200_OK
    ts2 = resp2.json()["archived_at"]
    # Both timestamps must be non-null (idempotent = still archived)
    assert ts1 is not None
    assert ts2 is not None
    # Strip timezone suffix for comparison (SQLite may differ between calls)
    assert ts1.rstrip("Z") == ts2.rstrip("Z")


async def test_unarchive_clears_timestamp(
    client: AsyncClient,
    admin_headers,
    platform_template,
):
    """Unarchiving a template clears archived_at."""
    # Archive first
    await client.post(
        f"api/v1/templates/{platform_template}/archive",
        headers=admin_headers,
    )

    resp = await client.post(
        f"api/v1/templates/{platform_template}/unarchive",
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["archived_at"] is None

    async with session_scope() as session:
        tmpl = await session.get(Template, platform_template)
        assert tmpl is not None
        assert tmpl.archived_at is None


async def test_non_editor_cannot_archive(
    client: AsyncClient,
    regular_headers,
    platform_template,
):
    """Non-editor archiving a platform template → 403."""
    resp = await client.post(
        f"api/v1/templates/{platform_template}/archive",
        headers=regular_headers,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
