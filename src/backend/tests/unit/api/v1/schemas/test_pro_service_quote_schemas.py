from decimal import Decimal
from uuid import uuid4

from langflow.api.v1.schemas.pro_service_quote import (
    PreviewResponse,
    QuoteRead,
    QuoteSubmitRequest,
    QuoteUpdateRequest,
)


def test_preview_response_validates():
    resp = PreviewResponse(
        minutes_low=180, minutes_high=720,
        rate_low_per_hour=Decimal("200.00"), rate_high_per_hour=Decimal("200.00"),
        cost_low=Decimal("600.00"), cost_high=Decimal("2400.00"),
        headline_summary="x", narrative="y", conversation_summary=None,
        component_breakdown=[],
    )
    assert resp.cost_low == Decimal("600.00")


def test_submit_request_requires_text_fields():
    req = QuoteSubmitRequest(
        minutes_low=15, minutes_high=60,
        rate_low_per_hour=Decimal("200.00"), rate_high_per_hour=Decimal("200.00"),
        headline_summary="x", narrative="y", conversation_summary=None,
        org_notes=None,
    )
    assert req.minutes_low == 15


def test_update_request_all_optional():
    req = QuoteUpdateRequest()
    assert req.org_notes is None and req.admin_notes is None and req.status is None
