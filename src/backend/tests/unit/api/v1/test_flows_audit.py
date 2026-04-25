"""Tests for GET /api/v1/flows/{flow_id}/audit-logs (per-flow audit history).

The endpoint is viewer+ on the flow's organization_id, and forces
target_type=FLOW + target_id={flow_id} server-side so clients cannot
exfiltrate other targets' audit entries.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.audit_log import AuditAction, AuditLog, AuditTargetType
from langflow.services.deps import session_scope


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
    client: AsyncClient, org_viewer_headers: dict, created_flow
):
    other_flow_id = uuid4()
    await _seed_flow_audit(created_flow.id, created_flow.organization_id)
    await _seed_flow_audit(other_flow_id, created_flow.organization_id)

    resp = await client.get(
        f"api/v1/flows/{created_flow.id}/audit-logs",
        headers=org_viewer_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["target_type"] == "flow"
        assert item["target_id"] == str(created_flow.id)


@pytest.mark.asyncio
async def test_flow_audit_404_when_flow_missing(
    client: AsyncClient, org_viewer_headers: dict
):
    resp = await client.get(
        f"api/v1/flows/{uuid4()}/audit-logs",
        headers=org_viewer_headers,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
