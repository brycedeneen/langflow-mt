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
        headline_summary="x", narrative="y", conversation_summary=None,
        org_notes=None,
    )
    assert req.minutes_low == 15


def test_submit_request_ignores_client_supplied_rate_fields():
    """Client-supplied rate fields must be silently dropped.

    Rates are server-resolved at submit time. Pydantic's default extra-field
    handling is "ignore" — this test pins that behavior so a future schema
    change to ``extra='allow'`` (or similar) would fail loudly.
    """
    req = QuoteSubmitRequest.model_validate(
        {
            "minutes_low": 15,
            "minutes_high": 60,
            "rate_low_per_hour": "999999.99",
            "rate_high_per_hour": "999999.99",
            "headline_summary": "x",
            "narrative": "y",
            "conversation_summary": None,
            "org_notes": None,
        }
    )
    assert not hasattr(req, "rate_low_per_hour")
    assert not hasattr(req, "rate_high_per_hour")


def test_update_request_all_optional():
    req = QuoteUpdateRequest()
    assert req.org_notes is None and req.admin_notes is None and req.status is None
