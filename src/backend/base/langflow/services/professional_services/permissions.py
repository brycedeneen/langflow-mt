"""Role-scoped permission checks for Pro-Service Quotes."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)


@dataclass(frozen=True)
class PrincipalContext:
    """Pre-computed permission inputs.

    Built by route handlers from ``current_user`` + ``current_membership``.
    Keeps permission functions free of DB / Membership lookup concerns.
    """

    user_id: UUID
    org_id: UUID | None
    is_superuser: bool
    is_platform_admin: bool
    is_org_admin: bool  # owner or admin role in the current org

    @property
    def is_admin(self) -> bool:
        """Cross-tenant admin (super-admin or platform-admin)."""
        return self.is_superuser or self.is_platform_admin


def can_view_quote(quote: ProServiceQuote, principal: PrincipalContext) -> bool:
    if principal.is_admin:
        return True
    return principal.org_id == quote.org_id


def can_submit(*, flow_owner_id: UUID, principal: PrincipalContext) -> bool:
    return (
        principal.user_id == flow_owner_id
        or principal.is_org_admin
        or principal.is_admin
    )


def can_mark_in_progress(quote: ProServiceQuote, principal: PrincipalContext) -> bool:
    return principal.is_admin and quote.status == ProServiceQuoteStatus.OPEN


def can_close(quote: ProServiceQuote, principal: PrincipalContext) -> bool:
    if principal.is_admin and quote.status != ProServiceQuoteStatus.CLOSED:
        return True
    if (
        principal.user_id == quote.requester_user_id
        and quote.status == ProServiceQuoteStatus.OPEN
    ):
        return True
    return False


def can_edit_admin_notes(quote: ProServiceQuote, principal: PrincipalContext) -> bool:
    return principal.is_admin


def can_edit_org_notes(quote: ProServiceQuote, principal: PrincipalContext) -> bool:
    return principal.org_id == quote.org_id or principal.is_admin
