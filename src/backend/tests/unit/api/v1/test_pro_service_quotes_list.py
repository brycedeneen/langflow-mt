"""Tests for GET /api/v1/pro-service-quotes (list) and detail (Task 13)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)
from langflow.services.deps import session_scope


async def _seed_flow(*, organization_id: UUID, user_id: UUID) -> UUID:
    async with session_scope() as session:
        flow = Flow(
            name=f"list-flow-{uuid4().hex[:6]}",
            data={"nodes": [], "edges": []},
            user_id=user_id,
            organization_id=organization_id,
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
        now = datetime.now(timezone.utc)
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
            submitted_at=now,
        )
        session.add(q)
        await session.flush()
        await session.refresh(q)
        return q.id


async def _seed_other_org() -> UUID:
    """Create a second org distinct from the caller's tenant."""
    from uuid import uuid4 as _u

    async with session_scope() as session:
        slug = f"otherorg-{_u().hex[:8]}"
        org = Organization(name=f"Other-{slug}", slug=slug)
        session.add(org)
        await session.flush()
        await session.refresh(org)
        return org.id


@pytest.mark.asyncio
async def test_org_member_sees_only_own_org_quotes(
    client: AsyncClient,
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
    active_super_user,
):
    """Org member sees their org's quotes; quotes in another org are filtered out."""
    other_org_id = await _seed_other_org()
    flow_a = await _seed_flow(
        organization_id=non_personal_org, user_id=UUID(org_viewer_user["id"])
    )
    flow_b = await _seed_flow(
        organization_id=other_org_id, user_id=active_super_user.id
    )
    quote_a = await _seed_quote(
        organization_id=non_personal_org,
        flow_id=flow_a,
        requester_user_id=UUID(org_viewer_user["id"]),
    )
    quote_b = await _seed_quote(
        organization_id=other_org_id,
        flow_id=flow_b,
        requester_user_id=active_super_user.id,
    )

    resp = await client.get(
        "api/v1/pro-service-quotes", headers=org_viewer_headers
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    body = resp.json()
    ids = {item["id"] for item in body["items"]}
    assert str(quote_a) in ids
    assert str(quote_b) not in ids


@pytest.mark.asyncio
async def test_super_admin_sees_all_orgs(
    client: AsyncClient,
    org_viewer_user,
    non_personal_org,
    active_super_user,
    logged_in_headers_super_user,
):
    """Cross-tenant admin (is_superuser) sees both orgs' quotes."""
    other_org_id = await _seed_other_org()
    flow_a = await _seed_flow(
        organization_id=non_personal_org, user_id=UUID(org_viewer_user["id"])
    )
    flow_b = await _seed_flow(
        organization_id=other_org_id, user_id=active_super_user.id
    )
    quote_a = await _seed_quote(
        organization_id=non_personal_org,
        flow_id=flow_a,
        requester_user_id=UUID(org_viewer_user["id"]),
    )
    quote_b = await _seed_quote(
        organization_id=other_org_id,
        flow_id=flow_b,
        requester_user_id=active_super_user.id,
    )

    resp = await client.get(
        "api/v1/pro-service-quotes", headers=logged_in_headers_super_user
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    body = resp.json()
    ids = {item["id"] for item in body["items"]}
    assert str(quote_a) in ids
    assert str(quote_b) in ids


@pytest.mark.asyncio
async def test_detail_404_for_other_org_member(
    client: AsyncClient,
    org_viewer_headers,
    active_super_user,
):
    """Cross-tenant detail returns 404 (not 403) — don't leak existence."""
    other_org_id = await _seed_other_org()
    flow_b = await _seed_flow(
        organization_id=other_org_id, user_id=active_super_user.id
    )
    quote_b = await _seed_quote(
        organization_id=other_org_id,
        flow_id=flow_b,
        requester_user_id=active_super_user.id,
    )
    resp = await client.get(
        f"api/v1/pro-service-quotes/{quote_b}", headers=org_viewer_headers
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_status_filter(
    client: AsyncClient,
    org_viewer_user,
    non_personal_org,
    logged_in_headers_super_user,
):
    """`?status=open` filters out closed/in_progress rows."""
    flow_a = await _seed_flow(
        organization_id=non_personal_org, user_id=UUID(org_viewer_user["id"])
    )
    open_id = await _seed_quote(
        organization_id=non_personal_org,
        flow_id=flow_a,
        requester_user_id=UUID(org_viewer_user["id"]),
        status_=ProServiceQuoteStatus.OPEN,
        headline="open-quote",
    )
    closed_id = await _seed_quote(
        organization_id=non_personal_org,
        flow_id=flow_a,
        requester_user_id=UUID(org_viewer_user["id"]),
        status_=ProServiceQuoteStatus.CLOSED,
        headline="closed-quote",
    )

    resp = await client.get(
        "api/v1/pro-service-quotes?status=open",
        headers=logged_in_headers_super_user,
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    body = resp.json()
    statuses = {item["status"] for item in body["items"]}
    ids = {item["id"] for item in body["items"]}
    assert statuses == {"open"}
    assert str(open_id) in ids
    assert str(closed_id) not in ids


@pytest.mark.asyncio
async def test_detail_returns_denormalized_fields(
    client: AsyncClient,
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
):
    """Detail response includes org_name, flow_name, requester_email."""
    flow_id = await _seed_flow(
        organization_id=non_personal_org, user_id=UUID(org_viewer_user["id"])
    )
    quote_id = await _seed_quote(
        organization_id=non_personal_org,
        flow_id=flow_id,
        requester_user_id=UUID(org_viewer_user["id"]),
        headline="my quote",
    )
    resp = await client.get(
        f"api/v1/pro-service-quotes/{quote_id}", headers=org_viewer_headers
    )
    assert resp.status_code == status.HTTP_200_OK, resp.text
    body = resp.json()
    assert body["id"] == str(quote_id)
    assert body["org_name"]
    assert body["flow_name"].startswith("list-flow-")
    # requester_email surfaces username when User has no email column
    assert body["requester_email"] == org_viewer_user["username"]
