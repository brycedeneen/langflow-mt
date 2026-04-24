"""Tests for POST /api/v1/templates with scope, org_id, category_ids (Phase C3)."""

from __future__ import annotations

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models.category.model import Category, TemplateCategory
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
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
async def sample_org():
    """Create a test organization; clean up after."""
    slug = f"testorg-{uuid.uuid4().hex[:8]}"
    async with session_scope() as session:
        org = Organization(name=f"TestOrg-{slug}", slug=slug)
        session.add(org)
        await session.flush()
        await session.refresh(org)
        org_id = uuid.UUID(str(org.id))

    yield org_id

    async with session_scope() as session:
        db_org = await session.get(Organization, org_id)
        if db_org:
            await session.delete(db_org)


@pytest.fixture
async def org_member_user(client: AsyncClient, sample_org):  # noqa: ARG001
    """A user that is a member of sample_org."""
    uid = uuid.uuid4()
    async with session_scope() as session:
        user = User(
            id=uid,
            username=f"orgmember_{uid}",
            password=get_auth_service().get_password_hash("memberpass"),
            is_active=True,
            is_superuser=False,
            is_platform_admin=False,
        )
        session.add(user)
        await session.flush()
        membership = Membership(
            user_id=uid,
            organization_id=sample_org,
            role=MembershipRole.OWNER,
        )
        session.add(membership)
        await session.flush()
        await session.refresh(user)
        username = user.username

    yield {"id": str(uid), "username": username}

    async with session_scope() as session:
        db_user = await session.get(User, uid)
        if db_user:
            await session.delete(db_user)


@pytest.fixture
async def org_member_headers(client: AsyncClient, org_member_user):
    resp = await client.post(
        "api/v1/login",
        data={"username": org_member_user["username"], "password": "memberpass"},
    )
    assert resp.status_code == status.HTTP_200_OK
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def source_flow(platform_admin_user, sample_org):
    """A flow in ``sample_org`` owned by platform_admin, used as a template source.

    Scoped to ``sample_org`` rather than the admin's auto-provisioned personal
    workspace so ``_load_source_and_blank`` can resolve it for non-admin callers
    (e.g. org members in ``sample_org``). Admin still owns it, which is fine — the
    server's source-flow load only cares about ``flow.organization_id``.
    """
    admin_uid = uuid.UUID(platform_admin_user["id"])
    async with session_scope() as session:
        flow = Flow(
            name=f"src-flow-{uuid.uuid4()}",
            data={"nodes": [], "edges": []},
            user_id=admin_uid,
            organization_id=sample_org,
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        flow_id = flow.id

    yield flow_id

    async with session_scope() as session:
        db_flow = await session.get(Flow, flow_id)
        if db_flow:
            await session.delete(db_flow)


@pytest.fixture
async def rag_category(platform_admin_user):
    """Create a 'RAG' category; yield its id; clean up."""
    admin_uid = uuid.UUID(platform_admin_user["id"])
    async with session_scope() as session:
        cat = Category(
            name=f"RAG-{uuid.uuid4()}",
            icon="tag",
            color="#aabbcc",
            created_by=admin_uid,
        )
        session.add(cat)
        await session.flush()
        await session.refresh(cat)
        cat_id = cat.id

    yield cat_id

    async with session_scope() as session:
        db_cat = await session.get(Category, cat_id)
        if db_cat:
            await session.delete(db_cat)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_platform_admin_creates_platform_template(
    client: AsyncClient,
    admin_headers,
    source_flow,
    rag_category,
):
    """Platform admin can create a platform-scoped template — returns 201."""
    resp = await client.post(
        "api/v1/templates",
        headers=admin_headers,
        json={
            "source_flow_id": str(source_flow),
            "name": f"PlatformTmpl-{uuid.uuid4()}",
            "scope": "platform",
            "category_ids": [str(rag_category)],
        },
    )
    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    cat_ids = [c["id"] for c in body.get("categories", [])]
    assert str(rag_category) in cat_ids

    # Verify in DB that scope is correct
    async with session_scope() as session:
        tmpl = await session.get(Template, uuid.UUID(body["id"]))
        assert tmpl is not None
        assert tmpl.scope == "platform"
        await session.delete(tmpl)


async def test_non_admin_cannot_create_platform_template(
    client: AsyncClient,
    regular_headers,
    source_flow,
):
    """Regular user creating a platform-scoped template → 403."""
    resp = await client.post(
        "api/v1/templates",
        headers=regular_headers,
        json={
            "source_flow_id": str(source_flow),
            "name": f"ShouldFail-{uuid.uuid4()}",
            "scope": "platform",
        },
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


async def test_org_member_creates_org_template_with_categories(
    client: AsyncClient,
    org_member_headers,
    org_member_user,
    source_flow,
    sample_org,
    rag_category,
):
    """Org member creating an org-scoped template → 201, DB has template_category links."""
    resp = await client.post(
        "api/v1/templates",
        headers=org_member_headers,
        json={
            "source_flow_id": str(source_flow),
            "name": f"OrgTmpl-{uuid.uuid4()}",
            "scope": "org",
            "org_id": str(sample_org),
            "category_ids": [str(rag_category)],
        },
    )
    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    tmpl_id = uuid.UUID(body["id"])

    # Verify DB has the template_category link
    async with session_scope() as session:
        tc = (
            await session.exec(
                select(TemplateCategory)
                .where(TemplateCategory.template_id == tmpl_id)
                .where(TemplateCategory.category_id == rag_category)
            )
        ).first()
        assert tc is not None

        # Cleanup
        tmpl = await session.get(Template, tmpl_id)
        if tmpl:
            await session.delete(tmpl)


async def test_org_member_cannot_create_template_for_other_org(
    client: AsyncClient,
    org_member_headers,
    source_flow,
):
    """Org member trying to create a template for an org they're NOT in → 403."""
    slug = f"otherorg-{uuid.uuid4().hex[:8]}"
    async with session_scope() as session:
        org = Organization(name=f"OtherOrg-{slug}", slug=slug)
        session.add(org)
        await session.flush()
        await session.refresh(org)
        other_org_id = uuid.UUID(str(org.id))

    try:
        resp = await client.post(
            "api/v1/templates",
            headers=org_member_headers,
            json={
                "source_flow_id": str(source_flow),
                "name": f"ShouldFail-{uuid.uuid4()}",
                "scope": "org",
                "org_id": str(other_org_id),
            },
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
    finally:
        async with session_scope() as session:
            db_org = await session.get(Organization, other_org_id)
            if db_org:
                await session.delete(db_org)


async def test_unknown_category_id_returns_422(
    client: AsyncClient,
    admin_headers,
    source_flow,
):
    """Providing a non-existent category_id → 422."""
    resp = await client.post(
        "api/v1/templates",
        headers=admin_headers,
        json={
            "source_flow_id": str(source_flow),
            "name": f"BadCat-{uuid.uuid4()}",
            "scope": "platform",
            "category_ids": [str(uuid.uuid4())],
        },
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Unknown category_ids" in resp.json()["detail"]
