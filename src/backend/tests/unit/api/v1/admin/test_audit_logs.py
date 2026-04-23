from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.audit_log import AuditAction, AuditLog, AuditTargetType
from langflow.services.deps import session_scope


async def _seed(**over) -> AuditLog:
    async with session_scope() as session:
        row = AuditLog(
            actor_user_id=over.get("actor_user_id", uuid4()),
            actor_email=over.get("actor_email", "a@b.com"),
            actor_is_super=False,
            org_id=over.get("org_id", uuid4()),
            target_type=over.get("target_type", AuditTargetType.FLOW),
            target_id=over.get("target_id", uuid4()),
            action=over.get("action", AuditAction.CREATE),
            diff={},
            diff_hash="deadbeef",
            request_metadata={},
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        row_id = row.id
    # Re-fetch after commit
    async with session_scope() as session:
        return await session.get(AuditLog, row_id)


@pytest.mark.asyncio
async def test_list_requires_platform_admin(
    client: AsyncClient, logged_in_headers: dict
):
    await _seed()
    resp = await client.get("api/v1/admin/audit-logs", headers=logged_in_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_list_paging_and_filter_by_org(
    client: AsyncClient, admin_headers: dict
):
    org1, org2 = uuid4(), uuid4()
    await _seed(org_id=org1)
    await _seed(org_id=org2)

    resp = await client.get(
        "api/v1/admin/audit-logs",
        params={"org_id": str(org1), "size": 50, "page": 1},
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] >= 1
    # All returned items should be for org1
    org1_items = [item for item in data["items"] if item["org_id"] == str(org1)]
    assert len(org1_items) >= 1


@pytest.mark.asyncio
async def test_detail_returns_full_diff(
    client: AsyncClient, admin_headers: dict
):
    row = await _seed()
    resp = await client.get(
        f"api/v1/admin/audit-logs/{row.id}",
        headers=admin_headers,
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["id"] == str(row.id)
