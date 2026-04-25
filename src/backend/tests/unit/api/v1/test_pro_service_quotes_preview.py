"""Tests for POST /api/v1/flows/{flow_id}/pro-service-quotes/preview.

Phase C.1 of the Pro-Service Quotes feature. Exercises:

- Happy-path preview against a flow with a known component breakdown.
- 409 conflict when ``flow.ps_request_active`` is already True.
- LLM provider injection via a swap-in stub so tests don't hit a real LLM.
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
from langflow.services.database.models.component_metadata.model import ComponentMetadata
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.professional_services_settings.model import (
    ProfessionalServicesSettings,
)
from langflow.services.deps import session_scope


class _FakeLLMProvider:
    """Returns a deterministic structured response so tests can assert exact
    headline/narrative output without invoking a real LLM."""

    async def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "headline_summary": "Stub headline for unit tests.",
            "narrative": "Stub narrative — preview endpoint is wiring components correctly.",
            "conversation_summary": None,
        }


@pytest.fixture
def stub_llm_provider(monkeypatch):
    """Swap the module-level ``_DEFAULT_PROVIDER`` for a deterministic stub.

    The endpoint's ``get_llm_provider`` reads the module attribute lazily on
    every request, so patching the module global is sufficient — no FastAPI
    ``dependency_overrides`` needed.
    """
    fake = _FakeLLMProvider()
    monkeypatch.setattr(
        pro_service_quotes_module, "_DEFAULT_PROVIDER", fake, raising=True
    )
    return fake


async def _seed_flow(
    *,
    organization_id: UUID,
    user_id: UUID,
    nodes: list[dict[str, Any]],
    ps_request_active: bool = False,
) -> UUID:
    """Insert a Flow with the given nodes and return its id."""
    async with session_scope() as session:
        flow = Flow(
            name=f"preview-test-{user_id.hex[:6]}",
            data={"nodes": nodes, "edges": []},
            user_id=user_id,
            organization_id=organization_id,
            ps_request_active=ps_request_active,
        )
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        return flow.id


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


async def _seed_settings_rates(low: Decimal, high: Decimal) -> None:
    """Upsert the singleton settings row.

    The alembic migration seeds id=1 in production, but ``SQLModel.metadata
    .create_all`` (used by the test fixture) skips data inserts — so create
    the row on first call.
    """
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


@pytest.mark.asyncio
async def test_preview_happy_path_returns_estimate(
    client: AsyncClient,
    stub_llm_provider,  # noqa: ARG001  — fixture installs the stub
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
    active_super_user,
):
    """Seed a flow with two known components → assert minutes/rates/headline."""
    await _seed_settings_rates(Decimal("200.00"), Decimal("400.00"))
    await _seed_component_metadata(
        "Webhook", minutes_low=30, minutes_high=90, updated_by=active_super_user.id
    )
    await _seed_component_metadata(
        "ChatInput", minutes_low=15, minutes_high=45, updated_by=active_super_user.id
    )
    nodes = [
        {"id": "n1", "data": {"type": "Webhook"}},
        {"id": "n2", "data": {"type": "ChatInput"}},
    ]
    flow_id = await _seed_flow(
        organization_id=non_personal_org,
        user_id=UUID(org_viewer_user["id"]),
        nodes=nodes,
    )

    response = await client.post(
        f"api/v1/flows/{flow_id}/pro-service-quotes/preview",
        headers=org_viewer_headers,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    body = response.json()
    # Sum of seeded components: 30+15 = 45 low, 90+45 = 135 high.
    assert body["minutes_low"] == 45
    assert body["minutes_high"] == 135
    assert body["minutes_low"] >= 15  # task-spec assertion
    # Decimals serialize to strings on the wire.
    assert body["rate_low_per_hour"] == "200.00"
    assert body["rate_high_per_hour"] == "400.00"
    # 45 min * $200/hr / 60 = $150.00; 135 min * $400/hr / 60 = $900.00
    assert body["cost_low"] == "150.00"
    assert body["cost_high"] == "900.00"
    assert body["headline_summary"] == "Stub headline for unit tests."
    assert body["narrative"]
    assert body["conversation_summary"] is None
    # Component breakdown should reflect each node, sorted-or-stable.
    types_in_breakdown = {b["type"] for b in body["component_breakdown"]}
    assert {"Webhook", "ChatInput"}.issubset(types_in_breakdown)


@pytest.mark.asyncio
async def test_preview_409_when_ps_request_active(
    client: AsyncClient,
    stub_llm_provider,  # noqa: ARG001
    org_viewer_user,
    org_viewer_headers,
    non_personal_org,
):
    """If a flow already has an active PS request, preview returns 409."""
    flow_id = await _seed_flow(
        organization_id=non_personal_org,
        user_id=UUID(org_viewer_user["id"]),
        nodes=[],
        ps_request_active=True,
    )

    response = await client.post(
        f"api/v1/flows/{flow_id}/pro-service-quotes/preview",
        headers=org_viewer_headers,
    )

    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    detail = response.json()["detail"]
    # FastAPI wraps a dict detail as-is; assert the structured code.
    if isinstance(detail, dict):
        assert detail.get("code") == "ps_request_active"
    else:
        assert "ps_request_active" in str(detail)


@pytest.mark.asyncio
async def test_preview_404_when_flow_missing(
    client: AsyncClient,
    stub_llm_provider,  # noqa: ARG001
    org_viewer_headers,
):
    """Unknown flow id returns 404."""
    bogus = UUID("00000000-0000-0000-0000-000000000000")
    response = await client.post(
        f"api/v1/flows/{bogus}/pro-service-quotes/preview",
        headers=org_viewer_headers,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
