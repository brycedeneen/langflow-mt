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


# ---------------------------------------------------------------------------
# Membership tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def regular_user(client: AsyncClient):  # noqa: ARG001
    """Create a plain (non-admin) user for membership tests."""
    uid = uuid4()
    async with session_scope() as session:
        user = User(
            id=uid,
            username=f"regular_user_{uid}",
            password=get_auth_service().get_password_hash("password123"),
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


async def test_member_add_remove_happy(client: AsyncClient, admin_headers, regular_user):
    """Add a member to a non-personal org → 201; duplicate → 409; remove → 204."""
    from uuid import UUID as _UUID

    # Create a non-personal org via the admin endpoint
    slug = f"members-org-{uuid4().hex[:8]}"
    create_resp = await client.post(
        "api/v1/admin/organizations",
        json={"name": "Members Org", "slug": slug},
        headers=admin_headers,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    org_id = create_resp.json()["id"]
    user_id = regular_user["id"]

    # POST → 201
    add_resp = await client.post(
        f"api/v1/admin/organizations/{org_id}/members",
        json={"user_id": user_id, "role": "owner"},
        headers=admin_headers,
    )
    assert add_resp.status_code == status.HTTP_201_CREATED
    data = add_resp.json()
    assert data["user_id"] == user_id
    assert data["username"] == regular_user["username"]
    assert data["role"] == "owner"

    # Verify it appears in the list
    list_resp = await client.get(
        f"api/v1/admin/organizations/{org_id}/members",
        headers=admin_headers,
    )
    assert list_resp.status_code == status.HTTP_200_OK
    items = list_resp.json()["items"]
    assert any(m["user_id"] == user_id for m in items)

    # POST again → 409
    dupe_resp = await client.post(
        f"api/v1/admin/organizations/{org_id}/members",
        json={"user_id": user_id, "role": "owner"},
        headers=admin_headers,
    )
    assert dupe_resp.status_code == status.HTTP_409_CONFLICT

    # DELETE → 204
    del_resp = await client.request(
        "DELETE",
        f"api/v1/admin/organizations/{org_id}/members/{user_id}",
        headers=admin_headers,
    )
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT

    # Clean up org
    async with session_scope() as session:
        org = await session.get(Organization, _UUID(org_id))
        if org:
            await session.delete(org)


async def test_add_member_unknown_user(client: AsyncClient, admin_headers):
    """Adding a non-existent user → 404."""
    from uuid import UUID as _UUID

    slug = f"no-user-org-{uuid4().hex[:8]}"
    create_resp = await client.post(
        "api/v1/admin/organizations",
        json={"name": "No User Org", "slug": slug},
        headers=admin_headers,
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    org_id = create_resp.json()["id"]

    ghost_user_id = str(uuid4())
    resp = await client.post(
        f"api/v1/admin/organizations/{org_id}/members",
        json={"user_id": ghost_user_id, "role": "owner"},
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND

    # Clean up org
    async with session_scope() as session:
        org = await session.get(Organization, _UUID(org_id))
        if org:
            await session.delete(org)


@pytest.mark.asyncio
async def test_user_search_filters_by_username(client: AsyncClient, admin_headers):
    from langflow.services.database.models.user.model import User

    async with session_scope() as session:
        session.add(User(username=f"alpha-{uuid4().hex[:6]}", password="x", is_active=True))
        session.add(User(username=f"gamma-{uuid4().hex[:6]}", password="x", is_active=True))
        await session.flush()

    resp = await client.get("/api/v1/admin/users?q=alpha", headers=admin_headers)
    assert resp.status_code == 200
    names = [u["username"] for u in resp.json()["items"]]
    assert any(n.startswith("alpha-") for n in names)
    assert not any(n.startswith("gamma-") for n in names)


async def test_remove_member_from_personal_org_forbidden(
    client: AsyncClient, admin_headers, regular_user
):
    """Attempting to remove a member from a personal org → 403."""
    from uuid import UUID as _UUID

    from langflow.services.database.models.membership.model import Membership, MembershipRole

    personal_id: str | None = None
    user_uuid = _UUID(regular_user["id"])

    async with session_scope() as session:
        personal = Organization(
            name="Personal Org",
            slug=f"personal-{uuid4().hex[:8]}",
            is_personal=True,
        )
        session.add(personal)
        await session.flush()
        await session.refresh(personal)
        personal_id = str(personal.id)

        membership = Membership(
            user_id=user_uuid,
            organization_id=personal.id,
            role=MembershipRole.OWNER,
        )
        session.add(membership)
        await session.flush()

    try:
        del_resp = await client.request(
            "DELETE",
            f"api/v1/admin/organizations/{personal_id}/members/{regular_user['id']}",
            headers=admin_headers,
        )
        assert del_resp.status_code == status.HTTP_403_FORBIDDEN
    finally:
        async with session_scope() as session:
            # Delete membership then org
            from sqlmodel import select as _select
            m = (await session.exec(
                _select(Membership).where(
                    Membership.user_id == user_uuid,
                    Membership.organization_id == _UUID(personal_id),
                )
            )).first()
            if m:
                await session.delete(m)
            org = await session.get(Organization, _UUID(personal_id))
            if org:
                await session.delete(org)


# ---------------------------------------------------------------------------
# /whoami endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_whoami_includes_is_platform_admin_for_admin(client: AsyncClient, admin_headers):
    """The /whoami endpoint exposes is_platform_admin so the frontend can gate the Admin UI."""
    resp = await client.get("/api/v1/users/whoami", headers=admin_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert "is_platform_admin" in body
    assert body["is_platform_admin"] is True


@pytest.mark.asyncio
async def test_whoami_includes_is_platform_admin_false_for_regular_user(
    client: AsyncClient, logged_in_headers
):
    """Regular (non-admin) users should have is_platform_admin=False in /whoami."""
    resp = await client.get("/api/v1/users/whoami", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert "is_platform_admin" in body
    assert body["is_platform_admin"] is False
