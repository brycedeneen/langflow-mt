"""State transitions for ProServiceQuote.

Each transition function applies the side effects (status, timestamps,
``flow.ps_request_active`` flag, AdminNotification rows) and leaves the
caller to commit. Permission checks live in ``permissions.py`` — these
helpers only validate the source state machine.

Bell rows for the requester use ``audience_user_id`` so the bell endpoint
can surface them to a single user. Bell rows for admins use the audience
enum (``SUPER_ADMIN`` / ``PLATFORM_ADMIN``) with ``audience_user_id`` NULL
so both audiences see them.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.admin_notification.model import (
    AdminNotification,
    NotificationAudience,
    NotificationCategory,
    NotificationSeverity,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)


class IllegalTransitionError(Exception):
    """Raised when a state transition is not legal from the current status."""


async def transition_to_in_progress(
    *,
    session: AsyncSession,
    quote: ProServiceQuote,
    actor_user_id: UUID,
) -> None:
    """Move OPEN → IN_PROGRESS, stamp timestamp, optionally claim, notify requester."""
    if quote.status != ProServiceQuoteStatus.OPEN:
        raise IllegalTransitionError(
            f"cannot move from {quote.status.value} to in_progress"
        )
    quote.status = ProServiceQuoteStatus.IN_PROGRESS
    quote.in_progress_at = datetime.now(timezone.utc)
    if quote.assigned_admin_user_id is None:
        quote.assigned_admin_user_id = actor_user_id
    session.add(quote)
    _bell_for_requester(session, quote, "in_progress")


async def transition_to_closed(
    *,
    session: AsyncSession,
    quote: ProServiceQuote,
    actor_user_id: UUID,
    by_requester: bool,
) -> None:
    """Move OPEN/IN_PROGRESS → CLOSED, stamp timestamps, clear flow flag, notify."""
    if quote.status == ProServiceQuoteStatus.CLOSED:
        raise IllegalTransitionError("already closed")
    quote.status = ProServiceQuoteStatus.CLOSED
    quote.closed_at = datetime.now(timezone.utc)
    quote.closed_by_user_id = actor_user_id
    session.add(quote)

    if quote.flow_id is not None:
        flow = await session.get(Flow, quote.flow_id)
        if flow is not None:
            flow.ps_request_active = False
            session.add(flow)

    if by_requester:
        _bell_broadcast_admins(session, quote, "cancelled")
    else:
        _bell_for_requester(session, quote, "closed")


def _bell_for_requester(
    session: AsyncSession, quote: ProServiceQuote, new_status: str
) -> None:
    """Targeted bell — surfaces only to the requester via ``audience_user_id``."""
    session.add(
        AdminNotification(
            org_id=quote.org_id,
            category=NotificationCategory.PROFESSIONAL_SERVICES_REQUEST,
            severity=NotificationSeverity.INFO,
            title="Pro-Service request status updated",
            body_md=(
                f"Your Pro-Service request is now {new_status.replace('_', ' ')}."
            ),
            metadata_json={"quote_id": str(quote.id), "event": new_status},
            audience_user_id=quote.requester_user_id,
            # ``audience`` is required NOT NULL on the model; the bell endpoint
            # queries by ``audience_user_id`` first, so this value is ignored
            # for targeted rows.
            audience=NotificationAudience.SUPER_ADMIN,
        )
    )


def _bell_broadcast_admins(
    session: AsyncSession, quote: ProServiceQuote, event: str
) -> None:
    """Broadcast bell to both admin audiences (super-admin + platform-admin)."""
    for audience in (
        NotificationAudience.SUPER_ADMIN,
        NotificationAudience.PLATFORM_ADMIN,
    ):
        session.add(
            AdminNotification(
                org_id=quote.org_id,
                category=NotificationCategory.PROFESSIONAL_SERVICES_REQUEST,
                severity=NotificationSeverity.INFO,
                title=f"Pro-Service request {event}",
                body_md=f"{event.title()}: {quote.headline_summary}",
                metadata_json={"quote_id": str(quote.id), "event": event},
                audience=audience,
            )
        )
