"""Shared fixtures for tests under `src/backend/tests/unit/api/v1/`."""
from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.professional_services_settings.model import (
    ProfessionalServicesSettings,
)
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope


@pytest.fixture(autouse=True)
async def ps_settings_singleton(client: AsyncClient):  # noqa: ARG001
    """Ensure the ``professional_services_settings`` id=1 singleton exists.

    Production seeds id=1 via alembic; under ``SQLModel.metadata.create_all``
    (used by the test fixture) data inserts are skipped, so any test that
    touches the pro-service-quotes endpoints must bootstrap the row. Yields
    the row id (always 1) so tests can also overwrite rates without
    re-querying.

    Depends on ``client`` so we run **after** the test app's per-test sqlite
    engine is initialized (otherwise the row is inserted into a torn-down DB).
    Marked ``autouse=True`` so PS-endpoint tests don't have to repeat it on
    every signature; the bootstrap is idempotent for non-PS tests in this
    directory (a single insert; no teardown).
    """
    async with session_scope() as session:
        existing = (
            await session.exec(
                select(ProfessionalServicesSettings).where(
                    ProfessionalServicesSettings.id == 1
                )
            )
        ).one_or_none()
        if existing is None:
            session.add(
                ProfessionalServicesSettings(
                    id=1,
                    default_hourly_rate_low=Decimal("200.00"),
                    default_hourly_rate_high=Decimal("200.00"),
                )
            )
            await session.commit()
    yield 1


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


async def login_as(client: AsyncClient, username: str, password: str = "testpassword") -> dict[str, str]:
    """Log in as ``username`` and return the Authorization header for JWT auth.

    Promoted from the per-test ``_login`` helper so Tasks 5–7 (and any future
    custom-component-gate enforcement tests) can share one copy. The default
    ``password`` matches the value used by ``tenant_and_admin`` and by the
    2026-04-22 cross-org security regression tests.
    """
    resp = await client.post(
        "api/v1/login",
        data={"username": username, "password": password},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def tenant_and_admin(client: AsyncClient):  # noqa: ARG001
    """Provision one tenant (org member, not platform admin) and one platform admin.

    Both users share a single org so tests exercising the custom-component gate
    can flip between identity postures without re-seeding org membership. Used
    by Task 4 (execution gate) and will be reused by Tasks 5-7 (create / upload
    / template-create gates) which follow the same enforcement pattern.
    """
    slug = uuid.uuid4().hex[:8]
    async with session_scope() as session:
        org = Organization(name=f"OrgG-{slug}", slug=f"org-g-{slug}", is_personal=True)
        tenant = User(
            username=f"tenant-{slug}",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_platform_admin=False,
        )
        admin = User(
            username=f"admin-{slug}",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_platform_admin=True,
        )
        session.add_all([org, tenant, admin])
        await session.flush()
        session.add_all([
            Membership(user_id=tenant.id, organization_id=org.id, role=MembershipRole.OWNER),
            Membership(user_id=admin.id, organization_id=org.id, role=MembershipRole.OWNER),
        ])
        await session.commit()
        for obj in (org, tenant, admin):
            await session.refresh(obj)
        ids = {
            "org_id": org.id,
            "tenant_id": tenant.id,
            "tenant_username": tenant.username,
            "admin_id": admin.id,
            "admin_username": admin.username,
        }

    yield ids

    async with session_scope() as session:
        for model, pk in [
            (User, ids["tenant_id"]),
            (User, ids["admin_id"]),
            (Organization, ids["org_id"]),
        ]:
            row = await session.get(model, pk)
            if row is not None:
                await session.delete(row)
        await session.commit()


@pytest.fixture
async def two_org_fixture(client: AsyncClient):
    """Create two orgs with one member each.

    Returns (actor_user_dict, actor_org, other_user_dict, other_org) where
    *_user_dict contains ``id``, ``username``, and ``headers`` (pre-authenticated).
    Cleans up all created rows after the test.
    """
    slug = uuid4().hex[:8]
    actor_password = "actorpassword"
    other_password = "otherpassword"

    async with session_scope() as session:
        actor_org = Organization(name=f"actor-org-{slug}", slug=f"actor-org-{slug}", is_personal=False)
        other_org = Organization(name=f"other-org-{slug}", slug=f"other-org-{slug}", is_personal=False)
        session.add_all([actor_org, other_org])
        await session.flush()

        actor = User(
            username=f"actor-{slug}",
            password=get_password_hash(actor_password),
            is_active=True,
        )
        other = User(
            username=f"other-{slug}",
            password=get_password_hash(other_password),
            is_active=True,
        )
        session.add_all([actor, other])
        await session.flush()

        session.add_all([
            Membership(user_id=actor.id, organization_id=actor_org.id, role=MembershipRole.MEMBER),
            Membership(user_id=other.id, organization_id=other_org.id, role=MembershipRole.MEMBER),
        ])
        await session.commit()
        for obj in (actor_org, other_org, actor, other):
            await session.refresh(obj)

        ids = {
            "actor_id": actor.id,
            "actor_username": actor.username,
            "other_id": other.id,
            "other_username": other.username,
            "actor_org_id": actor_org.id,
            "other_org_id": other_org.id,
        }

    # Authenticate both users
    resp = await client.post("api/v1/login", data={"username": ids["actor_username"], "password": actor_password})
    assert resp.status_code == status.HTTP_200_OK, f"actor login failed: {resp.text}"
    actor_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = await client.post("api/v1/login", data={"username": ids["other_username"], "password": other_password})
    assert resp.status_code == status.HTTP_200_OK, f"other login failed: {resp.text}"
    other_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    actor_dict = {"id": ids["actor_id"], "username": ids["actor_username"], "headers": actor_headers}
    other_dict = {"id": ids["other_id"], "username": ids["other_username"], "headers": other_headers}

    yield actor_dict, ids["actor_org_id"], other_dict, ids["other_org_id"]

    async with session_scope() as session:
        from sqlalchemy import delete as sa_delete

        await session.exec(
            sa_delete(Membership).where(
                Membership.user_id.in_([ids["actor_id"], ids["other_id"]]),
            ),
        )
        for model, pk in [
            (User, ids["actor_id"]),
            (User, ids["other_id"]),
            (Organization, ids["actor_org_id"]),
            (Organization, ids["other_org_id"]),
        ]:
            row = await session.get(model, pk)
            if row is not None:
                await session.delete(row)
        await session.commit()


@pytest.fixture
async def non_personal_org():
    """Create an Organization distinct from any user's auto-provisioned personal org.

    Used by tests that need to exercise org-scoped behavior against an org other
    than the caller's own personal workspace.
    """
    slug = f"nonpersonal-{uuid.uuid4().hex[:8]}"
    async with session_scope() as session:
        org = Organization(name=f"NonPersonalOrg-{slug}", slug=slug)
        session.add(org)
        await session.flush()
        await session.refresh(org)
        org_id = org.id

    yield org_id

    async with session_scope() as session:
        db_org = await session.get(Organization, org_id)
        if db_org:
            await session.delete(db_org)


@pytest.fixture
async def org_viewer_user(client: AsyncClient, non_personal_org):  # noqa: ARG001
    """A user with VIEWER membership in ``non_personal_org``.

    Login password is ``"memberpass"``.
    """
    uid = uuid4()
    async with session_scope() as session:
        user = User(
            id=uid,
            username=f"org_viewer_{uid}",
            password=get_password_hash("memberpass"),
            is_active=True,
            is_superuser=False,
            is_platform_admin=False,
        )
        session.add(user)
        await session.flush()
        session.add(
            Membership(
                user_id=uid,
                organization_id=non_personal_org,
                role=MembershipRole.VIEWER,
            )
        )
        await session.flush()
        username = user.username

    yield {"id": str(uid), "username": username}

    async with session_scope() as session:
        db_user = await session.get(User, uid)
        if db_user:
            await session.delete(db_user)


@pytest.fixture
async def org_viewer_headers(client: AsyncClient, org_viewer_user):
    """JWT auth headers for ``org_viewer_user``."""
    resp = await client.post(
        "api/v1/login",
        data={"username": org_viewer_user["username"], "password": "memberpass"},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def org_admin_user(client: AsyncClient, non_personal_org):  # noqa: ARG001
    """A user with ADMIN membership in ``non_personal_org``.

    Login password is ``"adminpass"``. Mirrors the shape of ``org_viewer_user``
    but with ``MembershipRole.ADMIN`` so tests can exercise admin-gated
    org-scoped endpoints.
    """
    uid = uuid4()
    async with session_scope() as session:
        user = User(
            id=uid,
            username=f"org_admin_{uid}",
            password=get_password_hash("adminpass"),
            is_active=True,
            is_superuser=False,
            is_platform_admin=False,
        )
        session.add(user)
        await session.flush()
        session.add(
            Membership(
                user_id=uid,
                organization_id=non_personal_org,
                role=MembershipRole.ADMIN,
            )
        )
        await session.flush()
        username = user.username

    yield {"id": str(uid), "username": username}

    async with session_scope() as session:
        db_user = await session.get(User, uid)
        if db_user:
            await session.delete(db_user)


@pytest.fixture
async def org_admin_headers(client: AsyncClient, org_admin_user):
    """JWT auth headers for ``org_admin_user``."""
    resp = await client.post(
        "api/v1/login",
        data={"username": org_admin_user["username"], "password": "adminpass"},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def created_flow(non_personal_org, org_viewer_user):
    """A Flow inside ``non_personal_org``, owned by ``org_viewer_user``.

    Yields a ``SimpleNamespace`` with ``id`` and ``organization_id`` so callers
    can use attribute access (``created_flow.id``).
    """
    owner_id = uuid.UUID(org_viewer_user["id"])
    async with session_scope() as session:
        flow = Flow(
            name=f"flow-{uuid.uuid4()}",
            data={"nodes": [], "edges": []},
            user_id=owner_id,
            organization_id=non_personal_org,
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        flow_id = flow.id
        org_id = flow.organization_id

    yield SimpleNamespace(id=flow_id, organization_id=org_id)

    async with session_scope() as session:
        db_flow = await session.get(Flow, flow_id)
        if db_flow:
            await session.delete(db_flow)
