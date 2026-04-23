from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models.audit_log import AuditAction, AuditLog, AuditTargetType
from langflow.services.database.models.flow.model import FlowCreate


@pytest.mark.asyncio
async def test_flow_create_via_api_emits_audit_row(
    client: AsyncClient, logged_in_headers: dict
):
    from langflow.services.deps import get_db_service

    session_factory = get_db_service().async_session_maker

    # POST a new flow
    payload = FlowCreate(name="audit-flow", description="x", data={"nodes": [], "edges": []})
    resp = await client.post(
        "api/v1/flows/", json=payload.model_dump(), headers=logged_in_headers
    )
    assert resp.status_code == 201
    flow_id = resp.json()["id"]

    # The audit write is dispatched as a create_task in after_commit - give it a moment to complete.
    await asyncio.sleep(0.2)

    # audit_log should contain one CREATE row for the flow
    async with session_factory() as session:
        rows = (
            await session.exec(
                select(AuditLog).where(
                    AuditLog.target_type == AuditTargetType.FLOW,
                    AuditLog.action == AuditAction.CREATE,
                )
            )
        ).all()

    matching = [r for r in rows if str(r.target_id) == flow_id]
    assert len(matching) >= 1
    row = matching[-1]
    assert row.actor_email != ""
    assert "after" in row.diff or "summary" in row.diff  # full or truncated
    assert row.request_metadata.get("method") == "POST"


@pytest.mark.asyncio
async def test_system_write_produces_no_audit_row(
    client: AsyncClient,  # noqa: ARG001 -- ensures DB service is initialized
):
    """Writes outside an HTTP request (audit_ctx is None) must not create audit rows."""
    from uuid import uuid4
    from langflow.services.database.models.organization.model import Organization
    from langflow.services.deps import get_db_service

    session_factory = get_db_service().async_session_maker

    async with session_factory() as session:
        before = (await session.exec(select(AuditLog))).all()
        before_count = len(before)

        org = Organization(id=uuid4(), name="system-bg", slug=f"system-bg-{uuid4().hex[:8]}")
        session.add(org)
        await session.commit()

        after = (await session.exec(select(AuditLog))).all()

    assert len(after) == before_count
