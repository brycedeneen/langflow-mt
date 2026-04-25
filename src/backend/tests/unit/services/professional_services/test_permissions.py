from uuid import uuid4

from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)
from langflow.services.professional_services.permissions import (
    can_close,
    can_edit_admin_notes,
    can_edit_org_notes,
    can_mark_in_progress,
    can_submit,
    can_view_quote,
)


class FakeUser:
    def __init__(self, user_id, org_id, is_super_admin=False, is_platform_admin=False, is_org_admin=False):
        self.id = user_id
        self.org_id = org_id
        self.is_super_admin = is_super_admin
        self.is_platform_admin = is_platform_admin
        self.is_org_admin = is_org_admin


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
        submitted_at=__import__("datetime").datetime.utcnow(),
    )


def test_view_admin_sees_all():
    org_a, org_b = uuid4(), uuid4()
    quote = _quote(org_a, uuid4())
    super_admin = FakeUser(uuid4(), org_b, is_super_admin=True)
    platform_admin = FakeUser(uuid4(), org_b, is_platform_admin=True)
    assert can_view_quote(quote, super_admin)
    assert can_view_quote(quote, platform_admin)


def test_view_org_member_sees_their_org_only():
    org_a, org_b = uuid4(), uuid4()
    quote = _quote(org_a, uuid4())
    org_member = FakeUser(uuid4(), org_a)
    other_org_member = FakeUser(uuid4(), org_b)
    assert can_view_quote(quote, org_member)
    assert not can_view_quote(quote, other_org_member)


def test_submit_requires_owner_or_org_admin():
    user_owner = FakeUser(uuid4(), uuid4())
    user_admin = FakeUser(uuid4(), uuid4(), is_org_admin=True)
    user_member = FakeUser(uuid4(), uuid4())
    assert can_submit(flow_owner_id=user_owner.id, user=user_owner)
    assert can_submit(flow_owner_id=uuid4(), user=user_admin)
    assert not can_submit(flow_owner_id=uuid4(), user=user_member)


def test_close_requester_can_self_cancel_open_only():
    org_a = uuid4()
    requester_id = uuid4()
    quote_open = _quote(org_a, requester_id, ProServiceQuoteStatus.OPEN)
    quote_in_progress = _quote(org_a, requester_id, ProServiceQuoteStatus.IN_PROGRESS)
    user = FakeUser(requester_id, org_a)
    assert can_close(quote_open, user)
    assert not can_close(quote_in_progress, user)


def test_mark_in_progress_admin_only_from_open():
    org_a = uuid4()
    quote_open = _quote(org_a, uuid4(), ProServiceQuoteStatus.OPEN)
    quote_closed = _quote(org_a, uuid4(), ProServiceQuoteStatus.CLOSED)
    admin = FakeUser(uuid4(), uuid4(), is_super_admin=True)
    org_user = FakeUser(uuid4(), org_a)
    assert can_mark_in_progress(quote_open, admin)
    assert not can_mark_in_progress(quote_closed, admin)
    assert not can_mark_in_progress(quote_open, org_user)


def test_edit_admin_notes_admin_only():
    quote = _quote(uuid4(), uuid4())
    admin = FakeUser(uuid4(), uuid4(), is_platform_admin=True)
    org_user = FakeUser(uuid4(), quote.org_id)
    assert can_edit_admin_notes(quote, admin)
    assert not can_edit_admin_notes(quote, org_user)


def test_edit_org_notes_any_org_member():
    quote = _quote(uuid4(), uuid4())
    org_member = FakeUser(uuid4(), quote.org_id)
    other_org_member = FakeUser(uuid4(), uuid4())
    assert can_edit_org_notes(quote, org_member)
    assert not can_edit_org_notes(quote, other_org_member)
