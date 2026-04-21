"""Tests for GET /api/v1/templates query params added in Phase C2.

Covers: category, scope, created_by_me, include_archived filtering.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models.category.model import Category, TemplateCategory
from langflow.services.database.models.template.model import Template
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope


# ---------------------------------------------------------------------------
# Helpers / fixtures
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


async def _make_template(
    session,
    *,
    name: str | None = None,
    scope: str = "platform",
    org_id: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
    archived: bool = False,
    categories: list[uuid.UUID] | None = None,
) -> Template:
    t = Template(
        name=name or f"tmpl-{uuid.uuid4()}",
        nodes=[],
        edges=[],
        scope=scope,
        org_id=org_id,
        created_by=created_by,
        updated_by=created_by,
        archived_at=datetime.now(timezone.utc) if archived else None,
    )
    session.add(t)
    await session.flush()
    await session.refresh(t)
    for cat_id in (categories or []):
        session.add(TemplateCategory(template_id=t.id, category_id=cat_id))
    await session.flush()
    return t


@pytest.fixture
async def _seed_templates(platform_admin_user, regular_user):
    """Seed a small set of templates; yield a dict with their IDs; clean up."""
    admin_uid = uuid.UUID(platform_admin_user["id"])
    regular_uid = uuid.UUID(regular_user["id"])
    ids: dict[str, uuid.UUID] = {}

    async with session_scope() as session:
        # One category: RAG
        cat = Category(name=f"RAG-{uuid.uuid4()}", icon="tag", color="#fff", created_by=admin_uid)
        session.add(cat)
        await session.flush()
        await session.refresh(cat)
        rag_cat_id = cat.id
        ids["rag_cat_id"] = rag_cat_id

        # platform template, no category, not archived
        t1 = await _make_template(session, name=f"P-normal-{uuid.uuid4()}", created_by=admin_uid)
        ids["platform_normal"] = t1.id

        # platform template with RAG category, not archived
        t2 = await _make_template(
            session, name=f"P-rag-{uuid.uuid4()}", created_by=admin_uid, categories=[rag_cat_id]
        )
        ids["platform_rag"] = t2.id

        # platform template, archived
        t3 = await _make_template(
            session, name=f"P-archived-{uuid.uuid4()}", created_by=admin_uid, archived=True
        )
        ids["platform_archived"] = t3.id

        # platform template, archived, owned by regular user
        t4 = await _make_template(
            session, name=f"P-archived-mine-{uuid.uuid4()}", created_by=regular_uid, archived=True
        )
        ids["platform_archived_mine"] = t4.id

        # platform template, created by regular user (not archived)
        t5 = await _make_template(
            session, name=f"P-mine-{uuid.uuid4()}", created_by=regular_uid
        )
        ids["platform_mine"] = t5.id

    yield ids

    async with session_scope() as session:
        for tid in list(ids.values()):
            if isinstance(tid, uuid.UUID):
                row = await session.get(Template, tid)
                if row:
                    await session.delete(row)
        cat_row = await session.get(Category, ids["rag_cat_id"])
        if cat_row:
            await session.delete(cat_row)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_seed_templates")
async def test_default_excludes_archived(client: AsyncClient, admin_headers, _seed_templates):
    """Default GET /templates must not return archived rows."""
    resp = await client.get("api/v1/templates", headers=admin_headers)
    assert resp.status_code == status.HTTP_200_OK
    ids = [r["id"] for r in resp.json()]
    assert str(_seed_templates["platform_archived"]) not in ids
    assert str(_seed_templates["platform_archived_mine"]) not in ids


@pytest.mark.usefixtures("_seed_templates")
async def test_category_filter(client: AsyncClient, admin_headers, _seed_templates):
    """?category=<name> returns only templates tagged with that category."""
    # Look up the RAG category name from the DB
    async with session_scope() as session:
        cat = await session.get(Category, _seed_templates["rag_cat_id"])
        cat_name = cat.name

    resp = await client.get(
        "api/v1/templates", headers=admin_headers, params={"category": cat_name}
    )
    assert resp.status_code == status.HTTP_200_OK
    ids = [r["id"] for r in resp.json()]
    assert str(_seed_templates["platform_rag"]) in ids
    assert str(_seed_templates["platform_normal"]) not in ids


@pytest.mark.usefixtures("_seed_templates")
async def test_scope_platform_excludes_org(client: AsyncClient, admin_headers, _seed_templates):
    """?scope=platform only returns platform-scoped rows."""
    resp = await client.get(
        "api/v1/templates", headers=admin_headers, params={"scope": "platform"}
    )
    assert resp.status_code == status.HTTP_200_OK
    scopes = [r.get("scope", "platform") for r in resp.json()]
    # All results should be platform-scoped (org rows excluded)
    assert all(s == "platform" for s in scopes)


@pytest.mark.usefixtures("_seed_templates")
async def test_created_by_me(client: AsyncClient, regular_headers, regular_user, _seed_templates):
    """?created_by_me=true returns only rows created by the caller."""
    resp = await client.get(
        "api/v1/templates", headers=regular_headers, params={"created_by_me": "true"}
    )
    assert resp.status_code == status.HTTP_200_OK
    ids = [r["id"] for r in resp.json()]
    assert str(_seed_templates["platform_mine"]) in ids
    # Should not include templates owned by admin
    assert str(_seed_templates["platform_normal"]) not in ids


@pytest.mark.usefixtures("_seed_templates")
async def test_non_admin_include_archived_without_created_by_me_is_403(
    client: AsyncClient, regular_headers
):
    """Non-admin ?include_archived=true without created_by_me → 403."""
    resp = await client.get(
        "api/v1/templates",
        headers=regular_headers,
        params={"include_archived": "true"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.usefixtures("_seed_templates")
async def test_non_admin_own_archived(
    client: AsyncClient, regular_headers, regular_user, _seed_templates
):
    """Non-admin ?created_by_me=true&include_archived=true returns own archived rows."""
    resp = await client.get(
        "api/v1/templates",
        headers=regular_headers,
        params={"created_by_me": "true", "include_archived": "true"},
    )
    assert resp.status_code == status.HTTP_200_OK
    ids = [r["id"] for r in resp.json()]
    assert str(_seed_templates["platform_archived_mine"]) in ids
    # Admin's archived template must NOT appear
    assert str(_seed_templates["platform_archived"]) not in ids


@pytest.mark.usefixtures("_seed_templates")
async def test_platform_admin_include_archived(
    client: AsyncClient, admin_headers, _seed_templates
):
    """Platform admin ?include_archived=true returns all archived rows across scopes."""
    resp = await client.get(
        "api/v1/templates",
        headers=admin_headers,
        params={"include_archived": "true"},
    )
    assert resp.status_code == status.HTTP_200_OK
    ids = [r["id"] for r in resp.json()]
    assert str(_seed_templates["platform_archived"]) in ids
    assert str(_seed_templates["platform_archived_mine"]) in ids
