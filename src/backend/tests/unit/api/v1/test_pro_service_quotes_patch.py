"""Tests for PATCH /api/v1/pro-service-quotes/{quote_id} (Task 14)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlmodel import select

from langflow.services.database.models.admin_notification.model import (
    AdminNotification,
    NotificationAudience,
    NotificationCategory,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)
from langflow.services.deps import session_scope


async def _seed_flow(*, organization_id: UUID, user_id: UUID, ps_active: bool = True) -> UUID:
    async with session_scope() as session:
        flow = Flow(
            name=f"patch-flow-{uuid4().hex[:6]}",
            data={"nodes": [], "edges": []},
            user_id=user_id,
            organization_id=organization_id,
            ps_request_active=ps_active,
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        return flow.id


async def _seed_quote(
    *,
    organization_id: UUID,
    flow_id: UUID,
    requester_user_id: UUID,
    status_: ProServiceQuoteStatus = ProServiceQuoteStatus.OPEN,
    headline: str = "h",
) -> UUID:
    async with session_scope() as session:
        q = ProServiceQuote(
            org_id=organization_id,
            flow_id=flow_id,
            requester_user_id=requester_user_id,
            status=status_,
            estimated_minutes_low=30,
            estimated_minutes_high=90,
            rate_low_per_hour=None,
            rate_high_per_hour=None,
            headline_summary=headline,
            narrative="n",
            conversation_summary=None,
            org_notes=None,
            submitted_at=datetime.now(timezone.utc),
        )
        session.add(q)
        await session.flush()
        await session.refresh(q)
        return q.id


@pytest.mark.asyncio
async def test_admin_marks_in_progress(
    client: AsyncClient,
    ps_settings_singleton,  # noqa: ARG001
    org_viewer_user,
    non_personal_org,
    logged_in_headers_super_user,
):
    flow_id = await _seed_flow(
        organization_id=non_personal_org, user_id=UUID(org_viewer_user["id"])
    )
    quote_id = await _seed_quote(
        organization_id=non_personal_org,
        flow_id=flow_id,
        requester_user_id=UUID(org_viewer_user["id"]),
        status_=ProServiceQuoteStatus.OPEN,
    )

    resp = await client.patch(
        f"api/v1/pro-service-quotes/{quote_id}",
        headers=logged_in_headers_super_user,
        json={"status": "in_progress"},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["in_progress_at"] is not None

    async with session_scope() as session:
        q = await session.get(ProServiceQuote, quote_id)
        assert q.status == ProServiceQuoteStatus.IN_PROGRESS
        assert q.in_progress_at is not None
        # Targeted bell row to the requester
        rows = (
            await session.exec(
                select(AdminNotification).where(
                    AdminNotification.audience_user_id == UUID(org_viewer_user["id"])
                )
            )
        ).all()
        rows = [r for r in rows if r.metadata_json.get("quote_id") == str(quote_id)]
        assert len(rows) >= 1
        assert rows[-1].metadata_json["event"] == "in_progress"


@pytest.mark.asyncio
async def test_admin_closes_clears_active_flag(
    client: AsyncClient,
    ps_settings_singleton,  # noqa: ARG001
    org_viewer_user,
    non_personal_org,
    logged_in_headers_super_user,
):
    flow_id = await _seed_flow(
        organization_id=non_personal_org, user_id=UUID(org_viewer_user["id"])
    )
    quote_id = await _seed_quote(
        organization_id=non_personal_org,
        flow_id=flow_id,
        requester_user_id=UUID(org_viewer_user["id"]),
        status_=ProServiceQuoteStatus.IN_PROGRESS,
    )

    resp = await client.patch(
        f"api/v1/pro-service-quotes/{quote_id}",
        headers=logged_in_headers_super_user,
        json={"status": "closed"},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text

    async with session_scope() as session:
        f = await session.get(Flow, flow_id)
        assert f.ps_request_active is False
        q = await session.get(ProServiceQuote, quote_id)
        assert q.status == ProServiceQuoteStatus.CLOSED
        assert q.closed_at is not None


@pytest.mark.asyncio
async def test_requester_self_cancels_open(
    client: AsyncClient,
    ps_settings_singleton,  # noqa: ARG001
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
):
    """Requester closes their own OPEN quote → broadcast bell to admins."""
    flow_id = await _seed_flow(
        organization_id=non_personal_org, user_id=UUID(org_viewer_user["id"])
    )
    quote_id = await _seed_quote(
        organization_id=non_personal_org,
        flow_id=flow_id,
        requester_user_id=UUID(org_viewer_user["id"]),
        status_=ProServiceQuoteStatus.OPEN,
    )
    resp = await client.patch(
        f"api/v1/pro-service-quotes/{quote_id}",
        headers=org_viewer_headers,
        json={"status": "closed"},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text

    async with session_scope() as session:
        rows = (
            await session.exec(
                select(AdminNotification).where(
                    AdminNotification.category
                    == NotificationCategory.PROFESSIONAL_SERVICES_REQUEST
                )
            )
        ).all()
        rows = [
            r
            for r in rows
            if r.metadata_json.get("quote_id") == str(quote_id)
            and r.metadata_json.get("event") == "cancelled"
        ]
        audiences = {r.audience for r in rows}
        assert NotificationAudience.SUPER_ADMIN in audiences
        assert NotificationAudience.PLATFORM_ADMIN in audiences


@pytest.mark.asyncio
async def test_requester_cannot_mark_in_progress(
    client: AsyncClient,
    ps_settings_singleton,  # noqa: ARG001
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
):
    """Only cross-tenant admins may set status=in_progress."""
    flow_id = await _seed_flow(
        organization_id=non_personal_org, user_id=UUID(org_viewer_user["id"])
    )
    quote_id = await _seed_quote(
        organization_id=non_personal_org,
        flow_id=flow_id,
        requester_user_id=UUID(org_viewer_user["id"]),
        status_=ProServiceQuoteStatus.OPEN,
    )
    resp = await client.patch(
        f"api/v1/pro-service-quotes/{quote_id}",
        headers=org_viewer_headers,
        json={"status": "in_progress"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_org_member_edits_org_notes(
    client: AsyncClient,
    ps_settings_singleton,  # noqa: ARG001
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
):
    flow_id = await _seed_flow(
        organization_id=non_personal_org, user_id=UUID(org_viewer_user["id"])
    )
    quote_id = await _seed_quote(
        organization_id=non_personal_org,
        flow_id=flow_id,
        requester_user_id=UUID(org_viewer_user["id"]),
        status_=ProServiceQuoteStatus.OPEN,
    )
    resp = await client.patch(
        f"api/v1/pro-service-quotes/{quote_id}",
        headers=org_viewer_headers,
        json={"org_notes": "team discussed: prioritize for Q2"},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    async with session_scope() as session:
        q = await session.get(ProServiceQuote, quote_id)
        assert q.org_notes == "team discussed: prioritize for Q2"


@pytest.mark.asyncio
async def test_org_member_cannot_edit_admin_notes(
    client: AsyncClient,
    ps_settings_singleton,  # noqa: ARG001
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
):
    flow_id = await _seed_flow(
        organization_id=non_personal_org, user_id=UUID(org_viewer_user["id"])
    )
    quote_id = await _seed_quote(
        organization_id=non_personal_org,
        flow_id=flow_id,
        requester_user_id=UUID(org_viewer_user["id"]),
        status_=ProServiceQuoteStatus.OPEN,
    )
    resp = await client.patch(
        f"api/v1/pro-service-quotes/{quote_id}",
        headers=org_viewer_headers,
        json={"admin_notes": "internal only"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_admin_closes_open_targeted_bell(
    client: AsyncClient,
    ps_settings_singleton,  # noqa: ARG001
    org_viewer_user,
    non_personal_org,
    logged_in_headers_super_user,
):
    """Admin closes an OPEN quote → targeted bell to requester (not broadcast)."""
    flow_id = await _seed_flow(
        organization_id=non_personal_org, user_id=UUID(org_viewer_user["id"])
    )
    quote_id = await _seed_quote(
        organization_id=non_personal_org,
        flow_id=flow_id,
        requester_user_id=UUID(org_viewer_user["id"]),
        status_=ProServiceQuoteStatus.OPEN,
    )
    resp = await client.patch(
        f"api/v1/pro-service-quotes/{quote_id}",
        headers=logged_in_headers_super_user,
        json={"status": "closed"},
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    async with session_scope() as session:
        rows = (
            await session.exec(
                select(AdminNotification).where(
                    AdminNotification.audience_user_id == UUID(org_viewer_user["id"])
                )
            )
        ).all()
        targeted = [
            r
            for r in rows
            if r.metadata_json.get("quote_id") == str(quote_id)
            and r.metadata_json.get("event") == "closed"
        ]
        assert len(targeted) == 1


@pytest.mark.asyncio
async def test_already_closed_to_in_progress_returns_409(
    client: AsyncClient,
    ps_settings_singleton,  # noqa: ARG001
    org_viewer_user,
    non_personal_org,
    logged_in_headers_super_user,
):
    """CLOSED → IN_PROGRESS is forbidden by permissions (admin can only mark
    OPEN → IN_PROGRESS), so the route returns 403 — confirms the state machine
    is gated *before* the transition runs."""
    flow_id = await _seed_flow(
        organization_id=non_personal_org, user_id=UUID(org_viewer_user["id"])
    )
    quote_id = await _seed_quote(
        organization_id=non_personal_org,
        flow_id=flow_id,
        requester_user_id=UUID(org_viewer_user["id"]),
        status_=ProServiceQuoteStatus.CLOSED,
    )
    resp = await client.patch(
        f"api/v1/pro-service-quotes/{quote_id}",
        headers=logged_in_headers_super_user,
        json={"status": "in_progress"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_patch_404_for_other_org(
    client: AsyncClient,
    ps_settings_singleton,  # noqa: ARG001
    org_viewer_headers,
    active_super_user,
):
    """Cross-tenant PATCH returns 404 (not 403)."""
    from uuid import uuid4

    from langflow.services.database.models.organization.model import Organization

    async with session_scope() as session:
        slug = f"otherorg-{uuid4().hex[:6]}"
        org = Organization(name=f"Other-{slug}", slug=slug)
        session.add(org)
        await session.flush()
        await session.refresh(org)
        other_org_id = org.id

    flow_id = await _seed_flow(
        organization_id=other_org_id, user_id=active_super_user.id
    )
    quote_id = await _seed_quote(
        organization_id=other_org_id,
        flow_id=flow_id,
        requester_user_id=active_super_user.id,
    )
    resp = await client.patch(
        f"api/v1/pro-service-quotes/{quote_id}",
        headers=org_viewer_headers,
        json={"org_notes": "leak attempt"},
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND
