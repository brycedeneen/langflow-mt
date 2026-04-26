"""Pro-Service Quotes API endpoints.

Phase C.1: ``POST /flows/{flow_id}/pro-service-quotes/preview``.

Subsequent tasks (C.2/C.3) will add submit, list/detail, PATCH, and admin
settings endpoints to this same router. The router uses **no prefix** because
preview/submit live under ``/flows/{flow_id}/...`` while list/detail/patch live
under ``/pro-service-quotes/...`` — using absolute paths inline keeps both
families on a single router.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import select

from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.api.utils.org_helpers import (
    get_current_membership,
    get_current_organization,
)
from langflow.api.v1.schemas.pro_service_quote import (
    ComponentBreakdownItem,
    PreviewResponse,
    QuoteListResponse,
    QuoteRead,
    QuoteSubmitRequest,
    QuoteUpdateRequest,
    quote_to_read,
)
from langflow.services.database.models.component_metadata.model import ComponentMetadata
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)
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
    can_close,
    can_edit_admin_notes,
    can_edit_org_notes,
    can_mark_in_progress,
    can_submit,
    can_view_quote,
)
from langflow.services.professional_services.settings_service import (
    read_settings_singleton_async,
    resolve_rate_band,
)
from langflow.services.professional_services.submit_service import (
    ActiveRequestError,
    submit_quote,
)
from langflow.services.professional_services.transitions import (
    IllegalTransitionError,
    transition_to_closed,
    transition_to_in_progress,
)
from langflow.services.professional_services.webhook_service import deliver_quote_webhook

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


async def _build_principal_for_user(
    user: User,
    session: "DbSession",
) -> list[PrincipalContext]:
    """Build a list of PrincipalContexts (one per org membership).

    Used by list/detail/PATCH which may be called by cross-tenant admins (no
    membership) or by org members with multiple memberships (e.g., personal
    org + non-personal org). Returning a list lets the caller filter quotes
    against any of the user's orgs without arbitrarily picking one.

    Cross-tenant admins (super-admin / platform-admin) without any membership
    still receive a single placeholder principal so ``is_admin`` checks work.
    """
    rows = (
        await session.exec(
            select(Membership).where(Membership.user_id == user.id)
        )
    ).all()
    if not rows:
        return [
            PrincipalContext(
                user_id=user.id,
                org_id=None,
                is_superuser=user.is_superuser,
                is_platform_admin=user.is_platform_admin,
                is_org_admin=False,
            )
        ]
    return [
        PrincipalContext(
            user_id=user.id,
            org_id=m.organization_id,
            is_superuser=user.is_superuser,
            is_platform_admin=user.is_platform_admin,
            is_org_admin=m.role in (MembershipRole.OWNER, MembershipRole.ADMIN),
        )
        for m in rows
    ]


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
    settings_row = await read_settings_singleton_async(session)
    result = quote_to_read(quote, org, flow, requester)

    # Best-effort async webhook delivery. Failure is silent (logged at WARNING).
    # The webhook fires after the DB commit so the in-product quote remains
    # the source of truth even if the receiver is down. The base_url is
    # currently empty; Phase C.3 will surface a configurable settings field
    # so receivers can deep-link back to the flow.
    await deliver_quote_webhook(
        settings_row=settings_row,
        quote=quote,
        org=org,
        requester=requester,
        base_url="",
    )
    return result


@router.get("/pro-service-quotes", response_model=QuoteListResponse)
async def list_quotes(
    user: CurrentActiveUser,
    session: DbSession,
    status_filter: Annotated[ProServiceQuoteStatus | None, Query(alias="status")] = None,
    org_id_filter: Annotated[UUID | None, Query(alias="org_id")] = None,
    limit: int = 50,
    offset: int = 0,
) -> QuoteListResponse:
    """List quotes visible to the calling principal.

    Org members see their own org's rows. Cross-tenant admins (super-admin or
    platform-admin) see all rows; they can narrow with ``?org_id=...``. Status
    filter is supported for both. Denormalized org/flow/requester fields are
    resolved in batch to avoid N+1.
    """
    principals = await _build_principal_for_user(user, session)
    is_admin = any(p.is_admin for p in principals)
    visible_org_ids = [p.org_id for p in principals if p.org_id is not None]

    query = select(ProServiceQuote).order_by(ProServiceQuote.created_at.desc())
    count_query = select(func.count(ProServiceQuote.id))

    if not is_admin:
        if not visible_org_ids:
            return QuoteListResponse(items=[], total=0)
        query = query.where(ProServiceQuote.org_id.in_(visible_org_ids))
        count_query = count_query.where(ProServiceQuote.org_id.in_(visible_org_ids))
    elif org_id_filter is not None:
        query = query.where(ProServiceQuote.org_id == org_id_filter)
        count_query = count_query.where(ProServiceQuote.org_id == org_id_filter)

    if status_filter is not None:
        query = query.where(ProServiceQuote.status == status_filter)
        count_query = count_query.where(ProServiceQuote.status == status_filter)

    total = (await session.exec(count_query)).one()
    rows = (await session.exec(query.limit(limit).offset(offset))).all()

    org_ids = {r.org_id for r in rows}
    flow_ids = {r.flow_id for r in rows if r.flow_id}
    user_ids = {r.requester_user_id for r in rows}
    orgs = (
        {
            o.id: o
            for o in (
                await session.exec(
                    select(Organization).where(Organization.id.in_(org_ids))
                )
            ).all()
        }
        if org_ids
        else {}
    )
    flows = (
        {
            f.id: f
            for f in (
                await session.exec(select(Flow).where(Flow.id.in_(flow_ids)))
            ).all()
        }
        if flow_ids
        else {}
    )
    users = (
        {
            u.id: u
            for u in (
                await session.exec(select(User).where(User.id.in_(user_ids)))
            ).all()
        }
        if user_ids
        else {}
    )

    items = [
        quote_to_read(
            r,
            orgs.get(r.org_id),
            flows.get(r.flow_id) if r.flow_id else None,
            users.get(r.requester_user_id),
        )
        for r in rows
    ]
    return QuoteListResponse(items=items, total=int(total))


@router.get("/pro-service-quotes/{quote_id}", response_model=QuoteRead)
async def get_quote(
    quote_id: UUID,
    user: CurrentActiveUser,
    session: DbSession,
) -> QuoteRead:
    """Fetch a single quote, denormalized.

    Returns 404 (not 403) for cross-tenant access so we don't leak existence.
    """
    quote = await session.get(ProServiceQuote, quote_id)
    principals = await _build_principal_for_user(user, session)
    if quote is None or not any(can_view_quote(quote, p) for p in principals):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="quote_not_found"
        )

    org = await session.get(Organization, quote.org_id)
    flow = await session.get(Flow, quote.flow_id) if quote.flow_id else None
    requester = await session.get(User, quote.requester_user_id)
    return quote_to_read(quote, org, flow, requester)


@router.patch("/pro-service-quotes/{quote_id}", response_model=QuoteRead)
async def update_quote(
    quote_id: UUID,
    payload: QuoteUpdateRequest,
    user: CurrentActiveUser,
    session: DbSession,
) -> QuoteRead:
    """Mutate a quote: notes / assignment / state transitions.

    Returns 404 (not 403) for cross-tenant access. Per-field permissions:

    - ``org_notes``: org member or cross-tenant admin
    - ``admin_notes``: cross-tenant admin only
    - ``assigned_admin_user_id``: cross-tenant admin only
    - ``status=in_progress``: cross-tenant admin only, source must be OPEN
    - ``status=closed``: cross-tenant admin (any non-CLOSED) or requester (OPEN only)
    """
    quote = await session.get(ProServiceQuote, quote_id)
    principals = await _build_principal_for_user(user, session)
    if quote is None or not any(can_view_quote(quote, p) for p in principals):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="quote_not_found"
        )

    if payload.org_notes is not None:
        if not any(can_edit_org_notes(quote, p) for p in principals):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="cannot_edit_org_notes"
            )
        quote.org_notes = payload.org_notes

    if payload.admin_notes is not None:
        if not any(can_edit_admin_notes(quote, p) for p in principals):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="cannot_edit_admin_notes"
            )
        quote.admin_notes = payload.admin_notes

    if payload.assigned_admin_user_id is not None:
        if not any(p.is_admin for p in principals):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="cannot_assign"
            )
        quote.assigned_admin_user_id = payload.assigned_admin_user_id

    if payload.status is not None and payload.status != quote.status:
        try:
            if payload.status == ProServiceQuoteStatus.IN_PROGRESS:
                if not any(can_mark_in_progress(quote, p) for p in principals):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="cannot_mark_in_progress",
                    )
                await transition_to_in_progress(
                    session=session, quote=quote, actor_user_id=user.id
                )
            elif payload.status == ProServiceQuoteStatus.CLOSED:
                if not any(can_close(quote, p) for p in principals):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="cannot_close"
                    )
                by_requester = (
                    user.id == quote.requester_user_id
                    and not any(p.is_admin for p in principals)
                )
                await transition_to_closed(
                    session=session,
                    quote=quote,
                    actor_user_id=user.id,
                    by_requester=by_requester,
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="unsupported_target_status",
                )
        except IllegalTransitionError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc

    session.add(quote)
    await session.commit()
    await session.refresh(quote)

    org = await session.get(Organization, quote.org_id)
    flow = await session.get(Flow, quote.flow_id) if quote.flow_id else None
    requester = await session.get(User, quote.requester_user_id)
    return quote_to_read(quote, org, flow, requester)
