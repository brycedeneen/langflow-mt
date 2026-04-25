from __future__ import annotations

from typing import Protocol
from uuid import UUID

from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)


class _UserLike(Protocol):
    id: UUID
    org_id: UUID | None
    is_super_admin: bool
    is_platform_admin: bool
    is_org_admin: bool


def _is_admin(user: _UserLike) -> bool:
    return bool(user.is_super_admin or user.is_platform_admin)


def can_view_quote(quote: ProServiceQuote, user: _UserLike) -> bool:
    if _is_admin(user):
        return True
    return user.org_id == quote.org_id


def can_submit(*, flow_owner_id: UUID, user: _UserLike) -> bool:
    return user.id == flow_owner_id or user.is_org_admin or _is_admin(user)


def can_mark_in_progress(quote: ProServiceQuote, user: _UserLike) -> bool:
    return _is_admin(user) and quote.status == ProServiceQuoteStatus.OPEN


def can_close(quote: ProServiceQuote, user: _UserLike) -> bool:
    if _is_admin(user) and quote.status != ProServiceQuoteStatus.CLOSED:
        return True
    if (
        user.id == quote.requester_user_id
        and quote.status == ProServiceQuoteStatus.OPEN
    ):
        return True
    return False


def can_edit_admin_notes(quote: ProServiceQuote, user: _UserLike) -> bool:
    return _is_admin(user)


def can_edit_org_notes(quote: ProServiceQuote, user: _UserLike) -> bool:
    return user.org_id == quote.org_id or _is_admin(user)
