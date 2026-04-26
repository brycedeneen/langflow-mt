from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuote,
    ProServiceQuoteStatus,
)


def test_pro_service_quote_default_status():
    quote = ProServiceQuote(
        org_id=uuid4(),
        flow_id=uuid4(),
        requester_user_id=uuid4(),
        estimated_minutes_low=15,
        estimated_minutes_high=60,
        rate_low_per_hour=Decimal("200.00"),
        rate_high_per_hour=Decimal("200.00"),
        headline_summary="Wire up Slack notifications.",
        narrative="The user wants to push build events to Slack.",
        submitted_at=datetime.now(timezone.utc),
    )
    assert quote.status == ProServiceQuoteStatus.OPEN
    assert quote.id is not None
    assert quote.created_at is not None


def test_pro_service_quote_status_enum_values():
    assert ProServiceQuoteStatus.OPEN.value == "open"
    assert ProServiceQuoteStatus.IN_PROGRESS.value == "in_progress"
    assert ProServiceQuoteStatus.CLOSED.value == "closed"
