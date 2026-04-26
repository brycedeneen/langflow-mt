from datetime import datetime, timezone
from uuid import uuid4

from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
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


def _principal(*, user_id=None, org_id=None, is_superuser=False, is_platform_admin=False, is_org_admin=False):
    return PrincipalContext(
        user_id=user_id or uuid4(),
        org_id=org_id,
        is_superuser=is_superuser,
        is_platform_admin=is_platform_admin,
        is_org_admin=is_org_admin,
    )


def _quote(org_id, requester_id, status=ProServiceQuoteStatus.OPEN):
    return ProServiceQuote(
        org_id=org_id,
        flow_id=uuid4(),
        requester_user_id=requester_id,
        status=status,
        estimated_minutes_low=15,
        estimated_minutes_high=60,
        headline_summary="x",
        narrative="x",
        submitted_at=datetime.now(timezone.utc),
    )


def test_view_admin_sees_all():
    org_a, org_b = uuid4(), uuid4()
    quote = _quote(org_a, uuid4())
    super_admin = _principal(org_id=org_b, is_superuser=True)
    platform_admin = _principal(org_id=org_b, is_platform_admin=True)
    assert can_view_quote(quote, super_admin)
    assert can_view_quote(quote, platform_admin)


def test_view_org_member_sees_their_org_only():
    org_a, org_b = uuid4(), uuid4()
    quote = _quote(org_a, uuid4())
    org_member = _principal(org_id=org_a)
    other_org_member = _principal(org_id=org_b)
    assert can_view_quote(quote, org_member)
    assert not can_view_quote(quote, other_org_member)


def test_submit_requires_owner_or_org_admin():
    owner_id = uuid4()
    user_owner = _principal(user_id=owner_id)
    user_admin = _principal(is_org_admin=True)
    user_member = _principal()
    assert can_submit(flow_owner_id=owner_id, principal=user_owner)
    assert can_submit(flow_owner_id=uuid4(), principal=user_admin)
    assert not can_submit(flow_owner_id=uuid4(), principal=user_member)


def test_close_requester_can_self_cancel_open_only():
    org_a = uuid4()
    requester_id = uuid4()
    quote_open = _quote(org_a, requester_id, ProServiceQuoteStatus.OPEN)
    quote_in_progress = _quote(org_a, requester_id, ProServiceQuoteStatus.IN_PROGRESS)
    user = _principal(user_id=requester_id, org_id=org_a)
    assert can_close(quote_open, user)
    assert not can_close(quote_in_progress, user)


def test_mark_in_progress_admin_only_from_open():
    org_a = uuid4()
    quote_open = _quote(org_a, uuid4(), ProServiceQuoteStatus.OPEN)
    quote_closed = _quote(org_a, uuid4(), ProServiceQuoteStatus.CLOSED)
    admin = _principal(is_superuser=True)
    org_user = _principal(org_id=org_a)
    assert can_mark_in_progress(quote_open, admin)
    assert not can_mark_in_progress(quote_closed, admin)
    assert not can_mark_in_progress(quote_open, org_user)


def test_edit_admin_notes_admin_only():
    quote = _quote(uuid4(), uuid4())
    admin = _principal(is_platform_admin=True)
    org_user = _principal(org_id=quote.org_id)
    assert can_edit_admin_notes(quote, admin)
    assert not can_edit_admin_notes(quote, org_user)


def test_edit_org_notes_any_org_member():
    quote = _quote(uuid4(), uuid4())
    org_member = _principal(org_id=quote.org_id)
    other_org_member = _principal(org_id=uuid4())
    assert can_edit_org_notes(quote, org_member)
    assert not can_edit_org_notes(quote, other_org_member)
