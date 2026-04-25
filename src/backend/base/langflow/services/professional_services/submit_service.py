"""Submit service for Pro-Service Quotes.

Encapsulates the atomic side-effects of submitting a quote so the route
handler stays thin: insert the row, flip ``flow.ps_request_active``, and
broadcast bell rows to both admin audiences. Webhook delivery is a separate
concern (see ``webhook_service``) and is fired *after* the DB commit by the
route handler.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.v1.schemas.pro_service_quote import QuoteSubmitRequest
from langflow.services.database.models.admin_notification.model import (
    AdminNotification,
    NotificationAudience,
    NotificationCategory,
    NotificationSeverity,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)


class ActiveRequestError(Exception):
    """Raised when a flow already has ps_request_active=True at submit time."""


async def submit_quote(
    *,
    session: AsyncSession,
    flow: Flow,
    org: Organization,
    requester_user_id: UUID,
    payload: QuoteSubmitRequest,
) -> ProServiceQuote:
    """Atomically create the quote, set the flag, and write admin bell rows.

    Caller is responsible for ``session.commit()``. The ``session.flush()``
    here only ensures ``quote.id`` is populated for the bell metadata.
    """
    if flow.ps_request_active:
        raise ActiveRequestError()

    now = datetime.now(timezone.utc)
    quote = ProServiceQuote(
        org_id=org.id,
        flow_id=flow.id,
        requester_user_id=requester_user_id,
        status=ProServiceQuoteStatus.OPEN,
        estimated_minutes_low=payload.minutes_low,
        estimated_minutes_high=payload.minutes_high,
        rate_low_per_hour=payload.rate_low_per_hour,
        rate_high_per_hour=payload.rate_high_per_hour,
        headline_summary=payload.headline_summary,
        narrative=payload.narrative,
        conversation_summary=payload.conversation_summary,
        org_notes=payload.org_notes,
        submitted_at=now,
    )
    session.add(quote)
    flow.ps_request_active = True
    session.add(flow)
    await session.flush()  # populate quote.id for bell metadata

    for audience in (
        NotificationAudience.SUPER_ADMIN,
        NotificationAudience.PLATFORM_ADMIN,
    ):
        session.add(
            AdminNotification(
                org_id=org.id,
                category=NotificationCategory.PROFESSIONAL_SERVICES_REQUEST,
                severity=NotificationSeverity.INFO,
                title=f"New Pro-Service request from {org.name}",
                body_md=quote.headline_summary,
                metadata_json={"quote_id": str(quote.id), "event": "submitted"},
                audience=audience,
            )
        )
    return quote
