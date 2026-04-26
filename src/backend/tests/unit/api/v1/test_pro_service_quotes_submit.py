"""Tests for POST /api/v1/flows/{flow_id}/pro-service-quotes (submit).

Phase C.2 (Task 11). Exercises:

- Happy path: persists quote, sets ``flow.ps_request_active``, returns 201.
- Admin bell broadcast: rows for both SUPER_ADMIN and PLATFORM_ADMIN audiences.
- 409 conflict when ``flow.ps_request_active`` is already True.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

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


_VALID_PAYLOAD: dict[str, Any] = {
    "minutes_low": 30,
    "minutes_high": 90,
    "headline_summary": "Build Slack notifier",
    "narrative": "Send build events to Slack",
    "conversation_summary": None,
    "org_notes": "we need this by end of quarter",
}


async def _seed_flow(
    *,
    organization_id: UUID,
    user_id: UUID,
    ps_request_active: bool = False,
) -> UUID:
    async with session_scope() as session:
        flow = Flow(
            name=f"submit-test-{user_id.hex[:6]}",
            data={"nodes": [], "edges": []},
            user_id=user_id,
            organization_id=organization_id,
            ps_request_active=ps_request_active,
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        return flow.id


@pytest.mark.asyncio
async def test_submit_persists_and_sets_flag(
    client: AsyncClient,
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
):
    flow_id = await _seed_flow(
        organization_id=non_personal_org,
        user_id=UUID(org_viewer_user["id"]),
    )

    response = await client.post(
        f"api/v1/flows/{flow_id}/pro-service-quotes",
        headers=org_viewer_headers,
        json=_VALID_PAYLOAD,
    )

    assert response.status_code == status.HTTP_201_CREATED, response.text
    body = response.json()
    assert body["status"] == "open"
    assert body["headline_summary"] == "Build Slack notifier"
    assert body["org_notes"] == "we need this by end of quarter"

    # Flow flag flipped.
    async with session_scope() as session:
        refreshed_flow = await session.get(Flow, flow_id)
        assert refreshed_flow is not None
        assert refreshed_flow.ps_request_active is True

        quote_id = UUID(body["id"])
        quote = await session.get(ProServiceQuote, quote_id)
        assert quote is not None
        assert quote.status == ProServiceQuoteStatus.OPEN
        assert quote.requester_user_id == UUID(org_viewer_user["id"])


@pytest.mark.asyncio
async def test_submit_writes_admin_bell_rows(
    client: AsyncClient,
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
):
    flow_id = await _seed_flow(
        organization_id=non_personal_org,
        user_id=UUID(org_viewer_user["id"]),
    )
    response = await client.post(
        f"api/v1/flows/{flow_id}/pro-service-quotes",
        headers=org_viewer_headers,
        json=_VALID_PAYLOAD,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    quote_id = UUID(response.json()["id"])

    async with session_scope() as session:
        rows = (
            await session.exec(
                select(AdminNotification).where(
                    AdminNotification.category
                    == NotificationCategory.PROFESSIONAL_SERVICES_REQUEST
                )
            )
        ).all()
    # Filter to the rows that pertain to this quote
    rows = [r for r in rows if r.metadata_json.get("quote_id") == str(quote_id)]
    audiences = {r.audience for r in rows}
    assert NotificationAudience.SUPER_ADMIN in audiences
    assert NotificationAudience.PLATFORM_ADMIN in audiences
    # Both broadcast rows should have audience_user_id NULL.
    for r in rows:
        assert r.audience_user_id is None


@pytest.mark.asyncio
async def test_submit_409_when_active(
    client: AsyncClient,
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
):
    flow_id = await _seed_flow(
        organization_id=non_personal_org,
        user_id=UUID(org_viewer_user["id"]),
        ps_request_active=True,
    )
    response = await client.post(
        f"api/v1/flows/{flow_id}/pro-service-quotes",
        headers=org_viewer_headers,
        json=_VALID_PAYLOAD,
    )
    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    detail = response.json()["detail"]
    if isinstance(detail, dict):
        assert detail.get("code") == "ps_request_active"
    else:
        assert "ps_request_active" in str(detail)


@pytest.mark.asyncio
async def test_submit_404_when_flow_missing(
    client: AsyncClient,
    org_viewer_headers,
):
    bogus = UUID("00000000-0000-0000-0000-000000000000")
    response = await client.post(
        f"api/v1/flows/{bogus}/pro-service-quotes",
        headers=org_viewer_headers,
        json=_VALID_PAYLOAD,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_submit_ignores_client_rates_and_uses_server_resolved(
    client: AsyncClient,
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
):
    """Regression: a malicious/buggy client cannot dictate the persisted rates.

    The seeded settings singleton defaults to 200.00/200.00. Even if the
    payload tries to inject 999999.99 (Pydantic should silently drop unknown
    fields, but we send them anyway as a bytes-on-the-wire test), the
    persisted row must reflect the server-resolved band.
    """
    flow_id = await _seed_flow(
        organization_id=non_personal_org,
        user_id=UUID(org_viewer_user["id"]),
    )

    poisoned_payload: dict[str, Any] = {
        **_VALID_PAYLOAD,
        # Client tries to lie about the rate band:
        "rate_low_per_hour": "999999.99",
        "rate_high_per_hour": "999999.99",
    }

    response = await client.post(
        f"api/v1/flows/{flow_id}/pro-service-quotes",
        headers=org_viewer_headers,
        json=poisoned_payload,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text

    body = response.json()
    # Wire response reflects server-resolved (seeded) rates, not the client's.
    assert Decimal(body["rate_low_per_hour"]) == Decimal("200.00")
    assert Decimal(body["rate_high_per_hour"]) == Decimal("200.00")

    # And the persisted row matches.
    quote_id = UUID(body["id"])
    async with session_scope() as session:
        quote = await session.get(ProServiceQuote, quote_id)
        assert quote is not None
        assert quote.rate_low_per_hour == Decimal("200.00")
        assert quote.rate_high_per_hour == Decimal("200.00")
