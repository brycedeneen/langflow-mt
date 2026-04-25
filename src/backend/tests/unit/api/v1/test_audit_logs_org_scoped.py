"""Tests for GET /api/v1/orgs/{org_id}/audit-logs (org-scoped audit history).

The endpoint requires ADMIN+ role on the requested org and forces
``org_id={org_id}`` server-side so callers cannot exfiltrate other orgs'
audit entries.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.audit_log import AuditAction, AuditLog, AuditTargetType
from langflow.services.deps import session_scope


async def _seed(org_id) -> None:
    async with session_scope() as session:
        session.add(
            AuditLog(
                actor_user_id=uuid4(),
                actor_email="a@b.com",
                actor_is_super=False,
                org_id=org_id,
                target_type=AuditTargetType.FLOW,
                target_id=uuid4(),
                action=AuditAction.CREATE,
                diff={},
                diff_hash="x",
                request_metadata={},
            )
        )


@pytest.mark.asyncio
async def test_org_audit_requires_admin_role(
    client: AsyncClient, org_viewer_headers: dict, non_personal_org
):
    """A VIEWER (not ADMIN) on the org receives 403."""
    resp = await client.get(
        f"api/v1/orgs/{non_personal_org}/audit-logs",
        headers=org_viewer_headers,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_org_audit_returns_only_caller_org_entries(
    client: AsyncClient, org_admin_headers: dict, non_personal_org
):
    other_org = uuid4()
    await _seed(non_personal_org)
    await _seed(other_org)

    resp = await client.get(
        f"api/v1/orgs/{non_personal_org}/audit-logs",
        headers=org_admin_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["org_id"] == str(non_personal_org)


@pytest.mark.asyncio
async def test_org_audit_rejects_non_member_admin(
    client: AsyncClient, org_admin_headers: dict
):
    """An admin of one org receives 403 querying a foreign org."""
    foreign_org = uuid4()
    resp = await client.get(
        f"api/v1/orgs/{foreign_org}/audit-logs",
        headers=org_admin_headers,
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
