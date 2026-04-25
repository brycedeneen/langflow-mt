"""Tests for DELETE /api/v1/templates/{id} (hard delete, Phase C6)."""

from __future__ import annotations

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_delete_succeeds_when_no_flow_references(
    client: AsyncClient,
    admin_headers,
    platform_admin_user,
):
    """DELETE returns 204 and row is gone when no flows reference the template."""
    admin_uid = uuid.UUID(platform_admin_user["id"])
    async with session_scope() as session:
        t = Template(
            name=f"DeleteMe-{uuid.uuid4()}",
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

    resp = await client.delete(
        f"api/v1/templates/{tmpl_id}",
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    # Verify the row is truly gone (hard delete)
    async with session_scope() as session:
        row = await session.get(Template, tmpl_id)
        assert row is None


async def test_delete_returns_409_when_flow_references(
    client: AsyncClient,
    admin_headers,
    platform_admin_user,
):
    """DELETE returns 409 with referencing_flow_ids when a flow references the template."""
    admin_uid = uuid.UUID(platform_admin_user["id"])

    # Create template
    async with session_scope() as session:
        t = Template(
            name=f"LockedTemplate-{uuid.uuid4()}",
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

    # Create a flow that "references" this template via based_on_template_id.
    # SQLite doesn't enforce FK constraints by default, so we can set
    # based_on_template_id = tmpl_id (a Template UUID).
    flow_id = uuid.uuid4()
    async with session_scope() as session:
        flow = Flow(
            id=flow_id,
            name=f"RefFlow-{uuid.uuid4()}",
            data={"nodes": [], "edges": []},
            user_id=admin_uid,
            based_on_template_id=tmpl_id,
        )
        session.add(flow)
        await session.flush()

    try:
        resp = await client.delete(
            f"api/v1/templates/{tmpl_id}",
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_409_CONFLICT
        detail = resp.json()["detail"]
        assert "referencing_flow_ids" in detail
        assert str(flow_id) in detail["referencing_flow_ids"]
    finally:
        # Clean up flow then template
        async with session_scope() as session:
            db_flow = await session.get(Flow, flow_id)
            if db_flow:
                await session.delete(db_flow)
            db_tmpl = await session.get(Template, tmpl_id)
            if db_tmpl:
                await session.delete(db_tmpl)


async def test_non_editor_cannot_delete(
    client: AsyncClient,
    regular_headers,
    platform_admin_user,
):
    """Non-editor deleting a platform template → 403."""
    admin_uid = uuid.UUID(platform_admin_user["id"])
    async with session_scope() as session:
        t = Template(
            name=f"ProtectedTemplate-{uuid.uuid4()}",
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

    try:
        resp = await client.delete(
            f"api/v1/templates/{tmpl_id}",
            headers=regular_headers,
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
    finally:
        async with session_scope() as session:
            db = await session.get(Template, tmpl_id)
            if db:
                await session.delete(db)
