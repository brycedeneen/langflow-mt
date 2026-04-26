"""End-to-end lifecycle smoke for the Pro-Service Quotes feature (Phase H, Task 26).

Walks the full request lifecycle through the public API surface in a single
test, asserting both the wire-level responses and the side effects (flow flag,
admin bell rows). Intentionally NOT split into smaller tests — this is a smoke
that proves the whole flow works end-to-end:

    1. Owner previews a flow (200 with hours/rate fields).
    2. Owner submits the quote (201, status="open").
    3. Owner's preview re-attempt is blocked while the flow is active (409).
    4. Super-admin lists quotes and sees the new row.
    5. Two broadcast bell rows fired (SUPER_ADMIN + PLATFORM_ADMIN).
    6. Super-admin marks the quote in_progress (200, in_progress_at set).
    7. Super-admin closes the quote with admin_notes (200, closed_at set).
    8. flow.ps_request_active flips back to False; preview now succeeds.
    9. Two targeted bell rows landed in the requester's inbox (in_progress, closed).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlmodel import select

from langflow.api.v1 import pro_service_quotes as pro_service_quotes_module
from langflow.services.database.models.admin_notification.model import (
    AdminNotification,
    NotificationAudience,
    NotificationCategory,
)
from langflow.services.database.models.component_metadata.model import ComponentMetadata
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)
from langflow.services.database.models.professional_services_settings.model import (
    ProfessionalServicesSettings,
)
from langflow.services.deps import session_scope


class _FakeLLMProvider:
    """Deterministic LLM stub so the smoke test does not hit a real model."""

    async def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "headline_summary": "E2E smoke headline.",
            "narrative": "E2E smoke narrative — wiring components correctly.",
            "conversation_summary": None,
        }


@pytest.fixture
def stub_llm_provider(monkeypatch):
    """Patch the module-level provider so preview is deterministic and offline."""
    fake = _FakeLLMProvider()
    monkeypatch.setattr(
        pro_service_quotes_module, "_DEFAULT_PROVIDER", fake, raising=True
    )
    return fake


async def _seed_settings_rates(low: Decimal, high: Decimal) -> None:
    """Upsert the singleton settings row used to resolve the rate band."""
    async with session_scope() as session:
        row = (
            await session.exec(
                select(ProfessionalServicesSettings).where(
                    ProfessionalServicesSettings.id == 1
                )
            )
        ).one_or_none()
        if row is None:
            row = ProfessionalServicesSettings(
                id=1,
                default_hourly_rate_low=low,
                default_hourly_rate_high=high,
            )
            session.add(row)
        else:
            row.default_hourly_rate_low = low
            row.default_hourly_rate_high = high
            session.add(row)
        await session.commit()


async def _seed_component_metadata(
    component_name: str,
    *,
    minutes_low: int,
    minutes_high: int,
    updated_by: UUID,
) -> None:
    async with session_scope() as session:
        existing = (
            await session.exec(
                select(ComponentMetadata).where(
                    ComponentMetadata.component_name == component_name
                )
            )
        ).one_or_none()
        if existing is not None:
            existing.integration_minutes_low = minutes_low
            existing.integration_minutes_high = minutes_high
            session.add(existing)
        else:
            session.add(
                ComponentMetadata(
                    component_name=component_name,
                    integration_minutes_low=minutes_low,
                    integration_minutes_high=minutes_high,
                    updated_by=updated_by,
                )
            )
        await session.commit()


async def _seed_flow(
    *,
    organization_id: UUID,
    user_id: UUID,
    nodes: list[dict[str, Any]],
) -> UUID:
    async with session_scope() as session:
        flow = Flow(
            name=f"e2e-smoke-{user_id.hex[:6]}",
            data={"nodes": nodes, "edges": []},
            user_id=user_id,
            organization_id=organization_id,
            ps_request_active=False,
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        return flow.id


@pytest.mark.asyncio
async def test_full_lifecycle(
    client: AsyncClient,
    stub_llm_provider,  # noqa: ARG001 — fixture installs the stub
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
    active_super_user,
    logged_in_headers_super_user,
):
    """Walk the whole pro-service-quotes lifecycle in one shot."""
    requester_id = UUID(org_viewer_user["id"])

    # ---- Stage 0: seeds ----------------------------------------------------
    await _seed_settings_rates(Decimal("200.00"), Decimal("400.00"))
    await _seed_component_metadata(
        "Webhook", minutes_low=30, minutes_high=90, updated_by=active_super_user.id
    )
    await _seed_component_metadata(
        "ChatInput", minutes_low=15, minutes_high=45, updated_by=active_super_user.id
    )
    flow_id = await _seed_flow(
        organization_id=non_personal_org,
        user_id=requester_id,
        nodes=[
            {"id": "n1", "data": {"type": "Webhook"}},
            {"id": "n2", "data": {"type": "ChatInput"}},
        ],
    )

    # ---- Stage 1: preview as flow owner ------------------------------------
    preview_resp = await client.post(
        f"api/v1/flows/{flow_id}/pro-service-quotes/preview",
        headers=org_viewer_headers,
    )
    assert preview_resp.status_code == status.HTTP_200_OK, preview_resp.text
    preview_body = preview_resp.json()
    # Component minutes summed: 30+15=45 low, 90+45=135 high
    assert preview_body["minutes_low"] == 45
    assert preview_body["minutes_high"] == 135
    assert Decimal(preview_body["rate_low_per_hour"]) == Decimal("200.00")
    assert Decimal(preview_body["rate_high_per_hour"]) == Decimal("400.00")
    assert preview_body["headline_summary"] == "E2E smoke headline."
    assert preview_body["narrative"]

    # ---- Stage 2: submit (drop server-resolved rate fields) ---------------
    submit_payload = {
        "minutes_low": preview_body["minutes_low"],
        "minutes_high": preview_body["minutes_high"],
        "headline_summary": preview_body["headline_summary"],
        "narrative": preview_body["narrative"],
        "conversation_summary": preview_body["conversation_summary"],
        "org_notes": "We need this by end of quarter.",
    }
    submit_resp = await client.post(
        f"api/v1/flows/{flow_id}/pro-service-quotes",
        headers=org_viewer_headers,
        json=submit_payload,
    )
    assert submit_resp.status_code == status.HTTP_201_CREATED, submit_resp.text
    submit_body = submit_resp.json()
    assert submit_body["status"] == "open"
    quote_id = UUID(submit_body["id"])

    async with session_scope() as session:
        flow_after_submit = await session.get(Flow, flow_id)
        assert flow_after_submit is not None
        assert flow_after_submit.ps_request_active is True

    # ---- Stage 3: duplicate-submit guard via preview retry ----------------
    dup_resp = await client.post(
        f"api/v1/flows/{flow_id}/pro-service-quotes/preview",
        headers=org_viewer_headers,
    )
    assert dup_resp.status_code == status.HTTP_409_CONFLICT, dup_resp.text
    dup_detail = dup_resp.json()["detail"]
    if isinstance(dup_detail, dict):
        assert dup_detail.get("code") == "ps_request_active"
    else:
        assert "ps_request_active" in str(dup_detail)

    # ---- Stage 4: super-admin sees the new quote in the global list -------
    list_resp = await client.get(
        "api/v1/pro-service-quotes",
        headers=logged_in_headers_super_user,
    )
    assert list_resp.status_code == status.HTTP_200_OK, list_resp.text
    list_ids = {item["id"] for item in list_resp.json()["items"]}
    assert str(quote_id) in list_ids

    # ---- Stage 5: broadcast bell rows on submit ---------------------------
    async with session_scope() as session:
        broadcast_rows = (
            await session.exec(
                select(AdminNotification).where(
                    AdminNotification.category
                    == NotificationCategory.PROFESSIONAL_SERVICES_REQUEST
                )
            )
        ).all()
    broadcast_for_quote = [
        r for r in broadcast_rows
        if r.metadata_json.get("quote_id") == str(quote_id)
        and r.audience_user_id is None
    ]
    audiences = {r.audience for r in broadcast_for_quote}
    assert NotificationAudience.SUPER_ADMIN in audiences
    assert NotificationAudience.PLATFORM_ADMIN in audiences

    # ---- Stage 6: super-admin marks the quote in_progress -----------------
    in_progress_resp = await client.patch(
        f"api/v1/pro-service-quotes/{quote_id}",
        headers=logged_in_headers_super_user,
        json={"status": "in_progress"},
    )
    assert in_progress_resp.status_code == status.HTTP_200_OK, in_progress_resp.text
    in_progress_body = in_progress_resp.json()
    assert in_progress_body["status"] == "in_progress"
    assert in_progress_body["in_progress_at"] is not None
    in_progress_ts = in_progress_body["in_progress_at"]

    # ---- Stage 7: super-admin closes with admin notes ---------------------
    close_resp = await client.patch(
        f"api/v1/pro-service-quotes/{quote_id}",
        headers=logged_in_headers_super_user,
        json={"status": "closed", "admin_notes": "Engagement complete."},
    )
    assert close_resp.status_code == status.HTTP_200_OK, close_resp.text
    close_body = close_resp.json()
    assert close_body["status"] == "closed"
    assert close_body["closed_at"] is not None
    assert close_body["admin_notes"] == "Engagement complete."
    # in_progress_at must be preserved across the close transition.
    assert close_body["in_progress_at"] == in_progress_ts

    # ---- Stage 8: flag cleared; preview now succeeds ----------------------
    async with session_scope() as session:
        flow_after_close = await session.get(Flow, flow_id)
        assert flow_after_close is not None
        assert flow_after_close.ps_request_active is False
        quote_db = await session.get(ProServiceQuote, quote_id)
        assert quote_db is not None
        assert quote_db.status == ProServiceQuoteStatus.CLOSED
        assert quote_db.closed_at is not None
        assert quote_db.in_progress_at is not None

    rerun_preview = await client.post(
        f"api/v1/flows/{flow_id}/pro-service-quotes/preview",
        headers=org_viewer_headers,
    )
    assert rerun_preview.status_code == status.HTTP_200_OK, rerun_preview.text

    # ---- Stage 9: targeted bell rows landed in requester's inbox ----------
    async with session_scope() as session:
        targeted_rows = (
            await session.exec(
                select(AdminNotification)
                .where(AdminNotification.audience_user_id == requester_id)
                .order_by(AdminNotification.created_at.asc())
            )
        ).all()
    targeted_for_quote = [
        r for r in targeted_rows
        if r.metadata_json.get("quote_id") == str(quote_id)
    ]
    events = [r.metadata_json.get("event") for r in targeted_for_quote]
    assert "in_progress" in events
    assert "closed" in events
    # Both rows are addressed to the original requester.
    for r in targeted_for_quote:
        assert r.audience_user_id == requester_id
