from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from langflow.services.database.models.pro_service_quote.model import (
    ProServiceQuoteStatus,
)


class ComponentBreakdownItem(BaseModel):
    type: str
    minutes_low: int
    minutes_high: int


class PreviewResponse(BaseModel):
    minutes_low: int
    minutes_high: int
    rate_low_per_hour: Decimal | None
    rate_high_per_hour: Decimal | None
    cost_low: Decimal | None
    cost_high: Decimal | None
    headline_summary: str
    narrative: str
    conversation_summary: str | None
    component_breakdown: list[ComponentBreakdownItem]


class QuoteSubmitRequest(BaseModel):
    minutes_low: int
    minutes_high: int
    rate_low_per_hour: Decimal | None
    rate_high_per_hour: Decimal | None
    headline_summary: str = Field(max_length=240)
    narrative: str
    conversation_summary: str | None
    org_notes: str | None


class QuoteUpdateRequest(BaseModel):
    org_notes: str | None = None
    admin_notes: str | None = None
    status: ProServiceQuoteStatus | None = None
    assigned_admin_user_id: UUID | None = None


class QuoteRead(BaseModel):
    id: UUID
    org_id: UUID
    org_name: str | None  # denormalized at read time for list/detail
    flow_id: UUID | None
    flow_name: str | None  # denormalized at read time; None when flow was deleted
    requester_user_id: UUID
    requester_email: str | None
    status: ProServiceQuoteStatus
    assigned_admin_user_id: UUID | None
    estimated_minutes_low: int
    estimated_minutes_high: int
    rate_low_per_hour: Decimal | None
    rate_high_per_hour: Decimal | None
    headline_summary: str
    narrative: str
    conversation_summary: str | None
    org_notes: str | None
    admin_notes: str | None
    created_at: datetime
    submitted_at: datetime
    in_progress_at: datetime | None
    closed_at: datetime | None
    closed_by_user_id: UUID | None

    model_config = {"from_attributes": True}


def quote_to_read(quote, org, flow, requester) -> "QuoteRead":
    """Build a QuoteRead with denormalized org_name/flow_name/requester_email.
    Each related entity may be None (e.g., flow deleted)."""
    return QuoteRead(
        id=quote.id,
        org_id=quote.org_id,
        org_name=org.name if org else None,
        flow_id=quote.flow_id,
        flow_name=flow.name if flow else None,
        requester_user_id=quote.requester_user_id,
        requester_email=requester.email if requester else None,
        status=quote.status,
        assigned_admin_user_id=quote.assigned_admin_user_id,
        estimated_minutes_low=quote.estimated_minutes_low,
        estimated_minutes_high=quote.estimated_minutes_high,
        rate_low_per_hour=quote.rate_low_per_hour,
        rate_high_per_hour=quote.rate_high_per_hour,
        headline_summary=quote.headline_summary,
        narrative=quote.narrative,
        conversation_summary=quote.conversation_summary,
        org_notes=quote.org_notes,
        admin_notes=quote.admin_notes,
        created_at=quote.created_at,
        submitted_at=quote.submitted_at,
        in_progress_at=quote.in_progress_at,
        closed_at=quote.closed_at,
        closed_by_user_id=quote.closed_by_user_id,
    )


class QuoteListResponse(BaseModel):
    items: list[QuoteRead]
    total: int
