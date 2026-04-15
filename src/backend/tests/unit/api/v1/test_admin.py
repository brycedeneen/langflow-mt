"""Tests for /api/v1/admin/* endpoints."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_list_orgs_unauthenticated(client: AsyncClient):
    """No token → 401/403 (the auth middleware returns 403 for missing credentials in this codebase)."""
    resp = await client.get("api/v1/admin/organizations")
    assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


async def test_list_orgs_requires_platform_admin(client: AsyncClient, logged_in_headers):
    """Regular user → 403."""
    resp = await client.get("api/v1/admin/organizations", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


async def test_list_orgs_returns_all(client: AsyncClient, admin_headers):
    """Platform admin can see all orgs including ones they are not a member of."""
    # Create two orgs via the endpoint
    resp1 = await client.post(
        "api/v1/admin/organizations",
        json={"name": "Org Alpha", "slug": f"org-alpha-{uuid4().hex[:8]}"},
        headers=admin_headers,
    )
    assert resp1.status_code == status.HTTP_201_CREATED
    resp2 = await client.post(
        "api/v1/admin/organizations",
        json={"name": "Org Beta", "slug": f"org-beta-{uuid4().hex[:8]}"},
        headers=admin_headers,
    )
    assert resp2.status_code == status.HTTP_201_CREATED

    resp = await client.get("api/v1/admin/organizations", headers=admin_headers)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 2
    slugs = {item["slug"] for item in data["items"]}
    assert resp1.json()["slug"] in slugs
    assert resp2.json()["slug"] in slugs


async def test_create_org_happy(client: AsyncClient, admin_headers):
    """Platform admin can create an org; response includes expected fields."""
    slug = f"new-org-{uuid4().hex[:8]}"
    resp = await client.post(
        "api/v1/admin/organizations",
        json={"name": "New Org", "slug": slug},
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["name"] == "New Org"
    assert data["slug"] == slug
    assert data["is_personal"] is False
    assert data["member_count"] == 0
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


async def test_create_org_duplicate_slug(client: AsyncClient, admin_headers):
    """Creating two orgs with the same slug → 409."""
    slug = f"dupe-org-{uuid4().hex[:8]}"
    payload = {"name": "Dupe Org", "slug": slug}
    resp1 = await client.post("api/v1/admin/organizations", json=payload, headers=admin_headers)
    assert resp1.status_code == status.HTTP_201_CREATED

    resp2 = await client.post("api/v1/admin/organizations", json=payload, headers=admin_headers)
    assert resp2.status_code == status.HTTP_409_CONFLICT


async def test_create_org_validates_slug(client: AsyncClient, admin_headers):
    """Slugs with uppercase or spaces → 422 validation error."""
    for bad_slug in ["BadSlug", "Bad Slug", "-starts-with-dash", "UPPER"]:
        resp = await client.post(
            "api/v1/admin/organizations",
            json={"name": "Bad Org", "slug": bad_slug},
            headers=admin_headers,
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, (
            f"Expected 422 for slug {bad_slug!r}, got {resp.status_code}"
        )


async def test_get_org_detail(client: AsyncClient, admin_headers):
    """Create an org via admin endpoint, then GET it — id matches and members is empty."""
    slug = f"detail-org-{uuid4().hex[:8]}"
    create_resp = await client.post(
        "api/v1/admin/organizations",
        json={"name": "Detail Org", "slug": slug},
        headers=admin_headers,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    org_id = create_resp.json()["id"]

    get_resp = await client.get(f"api/v1/admin/organizations/{org_id}", headers=admin_headers)
    assert get_resp.status_code == status.HTTP_200_OK
    data = get_resp.json()
    assert data["id"] == org_id
    assert data["slug"] == slug
    assert data["name"] == "Detail Org"
    assert data["is_personal"] is False
    assert data["members"] == []


async def test_get_org_detail_not_found(client: AsyncClient, admin_headers):
    """GET a non-existent org UUID → 404."""
    missing_id = str(uuid4())
    resp = await client.get(f"api/v1/admin/organizations/{missing_id}", headers=admin_headers)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_org_happy(client: AsyncClient, admin_headers):
    """Create an org, DELETE it with matching confirm_name, verify 200 and subsequent 404."""
    slug = f"del-org-{uuid4().hex[:8]}"
    create_resp = await client.post(
        "api/v1/admin/organizations",
        json={"name": "Delete Me", "slug": slug},
        headers=admin_headers,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    org_id = create_resp.json()["id"]

    del_resp = await client.request(
        "DELETE",
        f"api/v1/admin/organizations/{org_id}",
        json={"confirm_name": "Delete Me"},
        headers=admin_headers,
    )
    assert del_resp.status_code == status.HTTP_200_OK
    data = del_resp.json()
    assert "deleted" in data
    assert data["deleted"].get("organization") == 1

    # GET the org now returns 404
    get_resp = await client.get(f"api/v1/admin/organizations/{org_id}", headers=admin_headers)
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_org_wrong_confirm_name(client: AsyncClient, admin_headers):
    """DELETE with wrong confirm_name → 400."""
    slug = f"del-org-wrong-{uuid4().hex[:8]}"
    create_resp = await client.post(
        "api/v1/admin/organizations",
        json={"name": "Keep Me", "slug": slug},
        headers=admin_headers,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    org_id = create_resp.json()["id"]

    del_resp = await client.request(
        "DELETE",
        f"api/v1/admin/organizations/{org_id}",
        json={"confirm_name": "wrong name"},
        headers=admin_headers,
    )
    assert del_resp.status_code == status.HTTP_400_BAD_REQUEST


async def test_delete_personal_org_forbidden(client: AsyncClient, admin_headers):
    """DELETE a personal org → 403."""
    personal_id = None
    async with session_scope() as session:
        personal = Organization(
            name="Personal",
            slug=f"user-{uuid4()}",
            is_personal=True,
        )
        session.add(personal)
        await session.flush()
        await session.refresh(personal)
        personal_id = str(personal.id)

    try:
        del_resp = await client.request(
            "DELETE",
            f"api/v1/admin/organizations/{personal_id}",
            json={"confirm_name": "Personal"},
            headers=admin_headers,
        )
        assert del_resp.status_code == status.HTTP_403_FORBIDDEN
    finally:
        # Clean up the personal org
        from uuid import UUID as _UUID
        async with session_scope() as session:
            org = await session.get(Organization, _UUID(personal_id))
            if org:
                await session.delete(org)
