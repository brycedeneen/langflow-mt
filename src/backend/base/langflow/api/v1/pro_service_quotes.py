"""Pro-Service Quotes API endpoints.

Phase C.1: ``POST /flows/{flow_id}/pro-service-quotes/preview``.

Subsequent tasks (C.2/C.3) will add submit, list/detail, PATCH, and admin
settings endpoints to this same router. The router uses **no prefix** because
preview/submit live under ``/flows/{flow_id}/...`` while list/detail/patch live
under ``/pro-service-quotes/...`` — using absolute paths inline keeps both
families on a single router.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.api.utils.org_helpers import (
    get_current_membership,
    get_current_organization,
)
from langflow.api.v1.schemas.pro_service_quote import (
    ComponentBreakdownItem,
    PreviewResponse,
    QuoteRead,
    QuoteSubmitRequest,
    quote_to_read,
)
from langflow.services.database.models.component_metadata.model import ComponentMetadata
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.professional_services.estimate_service import (
    compute_cost_range,
    sum_component_minutes,
)
from langflow.services.professional_services.llm_service import (
    LLMProvider,
    generate_quote_text,
)
from langflow.services.professional_services.permissions import (
    PrincipalContext,
    can_submit,
)
from langflow.services.professional_services.settings_service import (
    read_settings_singleton_async,
    resolve_rate_band,
)
from langflow.services.professional_services.submit_service import (
    ActiveRequestError,
    submit_quote,
)
from langflow.services.professional_services.webhook_service import fire_quote_webhook

router = APIRouter(tags=["Pro-Service Quotes"])


# ---------------------------------------------------------------------------
# LLM provider wiring
# ---------------------------------------------------------------------------


class _StubLLMProvider:
    """Temporary in-process stub.

    Phase D (Task 16) will wire the assistant's LLM provider into this seam.
    For Phase C.1 we ship deterministic canned text so the preview endpoint
    can be tested without depending on real LLM credentials. Tests swap this
    out via ``monkeypatch.setattr(module, "_DEFAULT_PROVIDER", fake)``.
    """

    async def complete_structured(
        self,
        system_prompt: str,  # noqa: ARG002
        user_prompt: str,  # noqa: ARG002
        schema: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        return {
            "headline_summary": "Pro-service estimate (preview).",
            "narrative": (
                "AI-generated narrative for the requested integration. "
                "Replace once the LLM provider is wired in Phase D."
            ),
            "conversation_summary": None,
        }


_DEFAULT_PROVIDER: LLMProvider = _StubLLMProvider()


def get_llm_provider() -> LLMProvider:
    """FastAPI dependency that yields the active LLM provider.

    Reads the module attribute lazily so ``monkeypatch.setattr`` swaps in
    tests work without ``app.dependency_overrides``.
    """
    # NOTE: read via globals() so tests can monkeypatch the module attribute
    # and have the change observed at request time.
    return globals()["_DEFAULT_PROVIDER"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_principal(
    user: User,
    org: Organization,
    membership: Membership,
) -> PrincipalContext:
    """Project request identity into the dataclass the permissions module expects."""
    is_org_admin = membership.role in (MembershipRole.OWNER, MembershipRole.ADMIN)
    return PrincipalContext(
        user_id=user.id,
        org_id=org.id,
        is_superuser=user.is_superuser,
        is_platform_admin=user.is_platform_admin,
        is_org_admin=is_org_admin,
    )


def _component_types_from_nodes(nodes: list[dict[str, Any]]) -> list[str]:
    """Collect unique component types from flow node payloads.

    Defensive: nodes may have missing ``data`` or ``type`` (corrupt rows,
    legacy flows). Empty/missing types are skipped so we don't query
    ComponentMetadata with an empty string.
    """
    types: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        data = node.get("data")
        if not isinstance(data, dict):
            continue
        component_type = data.get("type")
        if isinstance(component_type, str) and component_type:
            types.add(component_type)
    return sorted(types)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/flows/{flow_id}/pro-service-quotes/preview",
    response_model=PreviewResponse,
)
async def preview_quote(
    flow_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
    org: Organization = Depends(get_current_organization),  # noqa: ARG001  — required for tenant scoping; reserved for permission checks added in C.2
    membership: Membership = Depends(get_current_membership),  # noqa: ARG001  — same as above
    provider: LLMProvider = Depends(get_llm_provider),
) -> PreviewResponse:
    """Generate a non-persistent pro-service estimate for a flow.

    Aggregates per-component integration-minute metadata, applies the active
    rate band (org override → settings default), and asks the LLM provider for
    headline/narrative copy. Nothing is written to the database.

    Returns 404 if the flow does not exist, or 409 with detail
    ``{"code": "ps_request_active"}`` if a quote is already pending for the
    flow (per-flow single-active invariant).
    """
    flow = await session.get(Flow, flow_id)
    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="flow_not_found")
    if flow.ps_request_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ps_request_active"},
        )

    # 1. Gather component-name → (low, high) minutes from metadata table.
    nodes_raw = flow.data.get("nodes", []) if isinstance(flow.data, dict) else []
    nodes: list[dict[str, Any]] = [n for n in nodes_raw if isinstance(n, dict)]
    component_types = _component_types_from_nodes(nodes)
    metadata_by_type: dict[str, tuple[int | None, int | None]] = {}
    if component_types:
        rows = (
            await session.exec(
                select(ComponentMetadata).where(
                    ComponentMetadata.component_name.in_(component_types)
                )
            )
        ).all()
        metadata_by_type = {
            row.component_name: (
                row.integration_minutes_low,
                row.integration_minutes_high,
            )
            for row in rows
        }

    # 2. Sum minutes; 3. resolve rate band; 4. compute cost range.
    estimate = sum_component_minutes(nodes, metadata_by_type)
    settings_row = await read_settings_singleton_async(session)
    rate_band = resolve_rate_band(org, settings_row)
    cost_low, cost_high = compute_cost_range(
        estimate.low, estimate.high, rate_band.low, rate_band.high
    )

    # 5. Generate headline/narrative/summary via the injected LLM provider.
    # chat_history wiring is deferred to Phase D — pass None for now.
    generated = await generate_quote_text(
        flow_name=flow.name,
        component_breakdown=estimate.breakdown,
        chat_history=None,
        provider=provider,
    )

    return PreviewResponse(
        minutes_low=estimate.low,
        minutes_high=estimate.high,
        rate_low_per_hour=rate_band.low,
        rate_high_per_hour=rate_band.high,
        cost_low=cost_low,
        cost_high=cost_high,
        headline_summary=generated.headline_summary,
        narrative=generated.narrative,
        conversation_summary=generated.conversation_summary,
        component_breakdown=[
            ComponentBreakdownItem(**b) for b in estimate.breakdown
        ],
    )


@router.post(
    "/flows/{flow_id}/pro-service-quotes",
    response_model=QuoteRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_quote_endpoint(
    flow_id: UUID,
    payload: QuoteSubmitRequest,
    user: CurrentActiveUser,
    session: DbSession,
    org: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
) -> QuoteRead:
    """Persist a pro-service quote submission and broadcast bell rows to admins.

    After commit, fires an HMAC-signed webhook (best-effort) per ``settings``.
    Returns 404 if the flow is missing, 403 if the principal can't submit,
    409 with ``{"code": "ps_request_active"}`` if a request is already
    pending for this flow.
    """
    flow = await session.get(Flow, flow_id)
    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="flow_not_found")

    principal = _build_principal(user, org, membership)
    if not can_submit(flow_owner_id=flow.user_id, principal=principal):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    try:
        quote = await submit_quote(
            session=session,
            flow=flow,
            org=org,
            requester_user_id=user.id,
            payload=payload,
        )
    except ActiveRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ps_request_active"},
        ) from exc

    await session.commit()
    await session.refresh(quote)
    await session.refresh(flow)
    requester = await session.get(User, quote.requester_user_id)
    result = quote_to_read(quote, org, flow, requester)

    # Best-effort async webhook delivery. Failure is silent (logged at WARNING).
    # The webhook fires after the DB commit so the in-product quote remains
    # the source of truth even if the receiver is down.
    fire_quote_webhook(quote_id=quote.id, base_url="")
    return result
