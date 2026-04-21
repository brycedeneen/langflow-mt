"""Tests for PATCH /api/v1/templates/{id} with category_ids (Phase C4)."""

from __future__ import annotations

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models.category.model import Category, TemplateCategory
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
    """A platform-scoped template owned by admin."""
    admin_uid = uuid.UUID(platform_admin_user["id"])
    async with session_scope() as session:
        t = Template(
            name=f"PatchMe-{uuid.uuid4()}",
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


@pytest.fixture
async def cat_a(platform_admin_user):
    admin_uid = uuid.UUID(platform_admin_user["id"])
    async with session_scope() as session:
        cat = Category(name=f"CatA-{uuid.uuid4()}", icon="tag", color="#aaa", created_by=admin_uid)
        session.add(cat)
        await session.flush()
        await session.refresh(cat)
        cid = cat.id

    yield cid

    async with session_scope() as session:
        db = await session.get(Category, cid)
        if db:
            await session.delete(db)


@pytest.fixture
async def cat_b(platform_admin_user):
    admin_uid = uuid.UUID(platform_admin_user["id"])
    async with session_scope() as session:
        cat = Category(name=f"CatB-{uuid.uuid4()}", icon="tag", color="#bbb", created_by=admin_uid)
        session.add(cat)
        await session.flush()
        await session.refresh(cat)
        cid = cat.id

    yield cid

    async with session_scope() as session:
        db = await session.get(Category, cid)
        if db:
            await session.delete(db)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_non_editor_gets_403(
    client: AsyncClient,
    regular_headers,
    platform_template,
):
    """Non-editor patching a platform template → 403."""
    resp = await client.patch(
        f"api/v1/templates/{platform_template}",
        headers=regular_headers,
        json={"name": "HackedName"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


async def test_category_ids_empty_clears_tags(
    client: AsyncClient,
    admin_headers,
    platform_template,
    cat_a,
):
    """PATCH with category_ids=[] removes all tags."""
    # First tag the template
    async with session_scope() as session:
        session.add(TemplateCategory(template_id=platform_template, category_id=cat_a))
        await session.flush()

    resp = await client.patch(
        f"api/v1/templates/{platform_template}",
        headers=admin_headers,
        json={"category_ids": []},
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["categories"] == []

    # Verify in DB
    async with session_scope() as session:
        links = (
            await session.exec(
                select(TemplateCategory).where(TemplateCategory.template_id == platform_template)
            )
        ).all()
        assert links == []


async def test_category_ids_replaces_tag_set(
    client: AsyncClient,
    admin_headers,
    platform_template,
    cat_a,
    cat_b,
):
    """PATCH with category_ids=[a,b] replaces old tag set."""
    # Seed with only cat_a
    async with session_scope() as session:
        session.add(TemplateCategory(template_id=platform_template, category_id=cat_a))
        await session.flush()

    resp = await client.patch(
        f"api/v1/templates/{platform_template}",
        headers=admin_headers,
        json={"category_ids": [str(cat_a), str(cat_b)]},
    )
    assert resp.status_code == status.HTTP_200_OK
    cat_ids_in_resp = {c["id"] for c in resp.json()["categories"]}
    assert str(cat_a) in cat_ids_in_resp
    assert str(cat_b) in cat_ids_in_resp


async def test_omitting_category_ids_leaves_tags_untouched(
    client: AsyncClient,
    admin_headers,
    platform_template,
    cat_a,
):
    """Omitting category_ids from PATCH body leaves existing tags unchanged."""
    # Seed with cat_a
    async with session_scope() as session:
        session.add(TemplateCategory(template_id=platform_template, category_id=cat_a))
        await session.flush()

    resp = await client.patch(
        f"api/v1/templates/{platform_template}",
        headers=admin_headers,
        json={"description": "updated desc"},
    )
    assert resp.status_code == status.HTTP_200_OK
    cat_ids_in_resp = {c["id"] for c in resp.json()["categories"]}
    assert str(cat_a) in cat_ids_in_resp


async def test_unknown_category_id_returns_422(
    client: AsyncClient,
    admin_headers,
    platform_template,
):
    """PATCH with unknown category id → 422."""
    resp = await client.patch(
        f"api/v1/templates/{platform_template}",
        headers=admin_headers,
        json={"category_ids": [str(uuid.uuid4())]},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Unknown category_ids" in resp.json()["detail"]
