"""Endpoint tests for /api/v1/categories CRUD router (Phase B)."""

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
    """Create a user with is_platform_admin=True."""
    uid = uuid.uuid4()
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
async def platform_admin_headers(client: AsyncClient, platform_admin_user):
    """JWT headers for the platform admin user."""
    resp = await client.post(
        "api/v1/login",
        data={"username": platform_admin_user["username"], "password": "adminpassword"},
    )
    assert resp.status_code == status.HTTP_200_OK
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seed_categories(client: AsyncClient, platform_admin_user):  # noqa: ARG001
    """Insert 3 categories with out-of-order names; yield them and clean up."""
    names = ["Banana", "apple", "Cherry"]
    created_ids: list[str] = []

    async with session_scope() as session:
        for name in names:
            cat = Category(
                name=name,
                icon="tag",
                color="#ffffff",
                description=f"desc for {name}",
                created_by=uuid.UUID(platform_admin_user["id"]),
            )
            session.add(cat)
        await session.flush()
        result = await session.exec(
            select(Category).where(Category.name.in_(names))
        )
        cats = result.all()
        for cat in cats:
            await session.refresh(cat)
            created_ids.append(str(cat.id))

    yield cats

    async with session_scope() as session:
        for cat_id in created_ids:
            obj = await session.get(Category, uuid.UUID(cat_id))
            if obj is not None:
                await session.delete(obj)


@pytest.fixture
async def seed_category_with_one_template(client: AsyncClient, platform_admin_user):  # noqa: ARG001
    """Insert one Category + one platform Template tagged with it. Yield (category_id, template_id)."""
    admin_uid = uuid.UUID(platform_admin_user["id"])
    cat_id: uuid.UUID | None = None
    tmpl_id: uuid.UUID | None = None

    async with session_scope() as session:
        cat = Category(
            name=f"TaggedCat-{uuid.uuid4()}",
            icon="star",
            color="#000000",
            created_by=admin_uid,
        )
        session.add(cat)
        await session.flush()
        await session.refresh(cat)
        cat_id = cat.id

        tmpl = Template(
            name=f"TaggedTmpl-{uuid.uuid4()}",
            nodes=[],
            edges=[],
            created_by=admin_uid,
            updated_by=admin_uid,
        )
        session.add(tmpl)
        await session.flush()
        await session.refresh(tmpl)
        tmpl_id = tmpl.id

        link = TemplateCategory(template_id=tmpl_id, category_id=cat_id)
        session.add(link)

    yield (cat_id, tmpl_id)

    async with session_scope() as session:
        # Remove remaining template_category links first
        link = (
            await session.exec(
                select(TemplateCategory)
                .where(TemplateCategory.template_id == tmpl_id)
                .where(TemplateCategory.category_id == cat_id)
            )
        ).one_or_none()
        if link is not None:
            await session.delete(link)
        await session.flush()

        tmpl_obj = await session.get(Template, tmpl_id)
        if tmpl_obj is not None:
            await session.delete(tmpl_obj)
        cat_obj = await session.get(Category, cat_id)
        if cat_obj is not None:
            await session.delete(cat_obj)


# ---------------------------------------------------------------------------
# GET /categories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_categories_returns_alpha_sorted(
    client: AsyncClient,
    logged_in_headers,
    seed_categories,
):
    resp = await client.get("api/v1/categories", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    items = resp.json()
    # Filter to only the seeded names so other test data doesn't interfere
    seeded_names = {"Banana", "apple", "Cherry"}
    filtered = [item["name"] for item in items if item["name"] in seeded_names]
    assert filtered == sorted(filtered, key=str.casefold)


@pytest.mark.asyncio
async def test_list_categories_requires_auth(client: AsyncClient):
    resp = await client.get("api/v1/categories")
    assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# GET /categories/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_category_returns_row(
    client: AsyncClient,
    logged_in_headers,
    seed_categories,
):
    cat = seed_categories[0]
    resp = await client.get(f"api/v1/categories/{cat.id}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["id"] == str(cat.id)
    assert body["name"] == cat.name


@pytest.mark.asyncio
async def test_get_category_returns_404_for_missing_id(
    client: AsyncClient,
    logged_in_headers,
):
    missing_id = uuid.uuid4()
    resp = await client.get(f"api/v1/categories/{missing_id}", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# POST /categories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_category_as_regular_user_returns_403(
    client: AsyncClient,
    logged_in_headers,
):
    resp = await client.post(
        "api/v1/categories",
        json={"name": "ShouldFail", "icon": "x", "color": "#fff"},
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_create_category_as_platform_admin_returns_201(
    client: AsyncClient,
    platform_admin_headers,
):
    name = f"NewCat-{uuid.uuid4()}"
    resp = await client.post(
        "api/v1/categories",
        json={"name": name, "icon": "tag", "color": "#abc", "description": "hello"},
        headers=platform_admin_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    body = resp.json()
    assert body["name"] == name
    assert body["icon"] == "tag"
    assert body["color"] == "#abc"
    assert body["description"] == "hello"
    assert "id" in body

    # cleanup
    async with session_scope() as session:
        obj = await session.get(Category, uuid.UUID(body["id"]))
        if obj:
            await session.delete(obj)


@pytest.mark.asyncio
async def test_create_category_duplicate_name_returns_409(
    client: AsyncClient,
    platform_admin_headers,
):
    name = f"DupCat-{uuid.uuid4()}"
    payload = {"name": name, "icon": "tag", "color": "#abc"}
    resp1 = await client.post("api/v1/categories", json=payload, headers=platform_admin_headers)
    assert resp1.status_code == status.HTTP_201_CREATED, resp1.text

    resp2 = await client.post("api/v1/categories", json=payload, headers=platform_admin_headers)
    assert resp2.status_code == status.HTTP_409_CONFLICT

    # cleanup
    async with session_scope() as session:
        obj = await session.get(Category, uuid.UUID(resp1.json()["id"]))
        if obj:
            await session.delete(obj)


@pytest.mark.asyncio
async def test_create_category_duplicate_name_case_insensitive_returns_409(
    client: AsyncClient,
    platform_admin_headers,
):
    base_name = f"CaseDup-{uuid.uuid4()}"
    resp1 = await client.post(
        "api/v1/categories",
        json={"name": base_name.lower(), "icon": "tag", "color": "#abc"},
        headers=platform_admin_headers,
    )
    assert resp1.status_code == status.HTTP_201_CREATED, resp1.text

    resp2 = await client.post(
        "api/v1/categories",
        json={"name": base_name.upper(), "icon": "tag", "color": "#abc"},
        headers=platform_admin_headers,
    )
    assert resp2.status_code == status.HTTP_409_CONFLICT

    # cleanup
    async with session_scope() as session:
        obj = await session.get(Category, uuid.UUID(resp1.json()["id"]))
        if obj:
            await session.delete(obj)


# ---------------------------------------------------------------------------
# PATCH /categories/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_category_as_platform_admin_updates_fields(
    client: AsyncClient,
    platform_admin_headers,
    seed_categories,
):
    cat = seed_categories[0]
    new_name = f"Patched-{uuid.uuid4()}"
    resp = await client.patch(
        f"api/v1/categories/{cat.id}",
        json={"name": new_name, "color": "#123456"},
        headers=platform_admin_headers,
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    body = resp.json()
    assert body["name"] == new_name
    assert body["color"] == "#123456"
    # icon should be unchanged
    assert body["icon"] == cat.icon


@pytest.mark.asyncio
async def test_patch_category_missing_id_returns_404(
    client: AsyncClient,
    platform_admin_headers,
):
    missing_id = uuid.uuid4()
    resp = await client.patch(
        f"api/v1/categories/{missing_id}",
        json={"name": "Whatever"},
        headers=platform_admin_headers,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_patch_category_duplicate_name_returns_409(
    client: AsyncClient,
    platform_admin_headers,
    seed_categories,
):
    # seed_categories[0] and seed_categories[1] are already in DB
    cat0 = seed_categories[0]
    cat1 = seed_categories[1]
    # Try to rename cat0 to have the same name as cat1 (case-insensitive collision)
    resp = await client.patch(
        f"api/v1/categories/{cat0.id}",
        json={"name": cat1.name},
        headers=platform_admin_headers,
    )
    assert resp.status_code == status.HTTP_409_CONFLICT


# ---------------------------------------------------------------------------
# DELETE /categories/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_category_removes_category(
    client: AsyncClient,
    platform_admin_headers,
    logged_in_headers,
    seed_categories,
):
    cat = seed_categories[2]
    resp = await client.delete(
        f"api/v1/categories/{cat.id}",
        headers=platform_admin_headers,
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    get_resp = await client.get(f"api/v1/categories/{cat.id}", headers=logged_in_headers)
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_delete_category_missing_id_returns_404(
    client: AsyncClient,
    platform_admin_headers,
):
    missing_id = uuid.uuid4()
    resp = await client.delete(
        f"api/v1/categories/{missing_id}",
        headers=platform_admin_headers,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_delete_category_cascades_but_template_survives(
    client: AsyncClient,
    platform_admin_headers,
    logged_in_headers,
    seed_category_with_one_template,
):
    """Deleting a category removes the template_category join row but keeps the Template."""
    cat_id, tmpl_id = seed_category_with_one_template

    resp = await client.delete(
        f"api/v1/categories/{cat_id}",
        headers=platform_admin_headers,
    )
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    # Category should be gone
    async with session_scope() as session:
        cat_obj = await session.get(Category, cat_id)
    assert cat_obj is None

    # Template should still exist
    async with session_scope() as session:
        tmpl_obj = await session.get(Template, tmpl_id)
    assert tmpl_obj is not None

    # TemplateCategory link should be gone (cascaded)
    async with session_scope() as session:
        link = (
            await session.exec(
                select(TemplateCategory)
                .where(TemplateCategory.template_id == tmpl_id)
                .where(TemplateCategory.category_id == cat_id)
            )
        ).one_or_none()
    assert link is None

    # Cleanup template (category already deleted)
    async with session_scope() as session:
        tmpl_obj = await session.get(Template, tmpl_id)
        if tmpl_obj:
            await session.delete(tmpl_obj)
