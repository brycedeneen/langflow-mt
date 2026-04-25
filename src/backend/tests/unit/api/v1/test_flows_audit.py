"""Tests for GET /api/v1/flows/{flow_id}/audit-logs (per-flow audit history).

The endpoint is viewer+ on the flow's organization_id, and forces
target_type=FLOW + target_id={flow_id} server-side so clients cannot
exfiltrate other targets' audit entries.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.audit_log import AuditAction, AuditLog, AuditTargetType
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def audit_org():
    """Create a non-personal org distinct from any user's auto-provisioned org."""
    slug = f"auditorg-{uuid.uuid4().hex[:8]}"
    async with session_scope() as session:
        org = Organization(name=f"AuditOrg-{slug}", slug=slug)
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
async def org_member_user(client: AsyncClient, audit_org):  # noqa: ARG001
    """A user that is a Viewer member of audit_org."""
    uid = uuid4()
    async with session_scope() as session:
        user = User(
            id=uid,
            username=f"audit_member_{uid}",
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
                organization_id=audit_org,
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
async def org_member_headers(client: AsyncClient, org_member_user):
    resp = await client.post(
        "api/v1/login",
        data={"username": org_member_user["username"], "password": "memberpass"},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def created_flow(audit_org, org_member_user):
    """A flow inside ``audit_org``, owned by the org member.

    Yields a SimpleNamespace exposing ``id`` and ``organization_id`` so the
    test bodies in the plan can use attribute access (``created_flow.id``).
    """
    owner_id = uuid.UUID(org_member_user["id"])
    async with session_scope() as session:
        flow = Flow(
            name=f"audit-flow-{uuid.uuid4()}",
            data={"nodes": [], "edges": []},
            user_id=owner_id,
            organization_id=audit_org,
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


async def _seed_flow_audit(flow_id, org_id) -> None:
    async with session_scope() as session:
        session.add(
            AuditLog(
                actor_user_id=uuid4(),
                actor_email="a@b.com",
                actor_is_super=False,
                org_id=org_id,
                target_type=AuditTargetType.FLOW,
                target_id=flow_id,
                action=AuditAction.UPDATE,
                diff={"changed": {"name": ["old", "new"]}},
                diff_hash="abc",
                request_metadata={},
            )
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow_audit_requires_org_membership(
    client: AsyncClient, logged_in_headers: dict, created_flow
):
    # logged_in_headers user has no membership in created_flow.organization_id
    resp = await client.get(
        f"api/v1/flows/{created_flow.id}/audit-logs",
        headers=logged_in_headers,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_flow_audit_returns_only_target_flow_entries(
    client: AsyncClient, org_member_headers: dict, created_flow
):
    other_flow_id = uuid4()
    await _seed_flow_audit(created_flow.id, created_flow.organization_id)
    await _seed_flow_audit(other_flow_id, created_flow.organization_id)

    resp = await client.get(
        f"api/v1/flows/{created_flow.id}/audit-logs",
        headers=org_member_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["target_type"] == "flow"
        assert item["target_id"] == str(created_flow.id)


@pytest.mark.asyncio
async def test_flow_audit_404_when_flow_missing(
    client: AsyncClient, org_member_headers: dict
):
    resp = await client.get(
        f"api/v1/flows/{uuid4()}/audit-logs",
        headers=org_member_headers,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
