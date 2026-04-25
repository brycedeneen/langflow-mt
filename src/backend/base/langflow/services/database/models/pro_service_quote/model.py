from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlmodel import Column, Field, SQLModel


class ProServiceQuoteStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProServiceQuote(SQLModel, table=True):
    __tablename__ = "pro_service_quote"
    __table_args__ = (
        Index("ix_pro_service_quote_org_status_created", "org_id", "status", "created_at"),
        Index("ix_pro_service_quote_status_created", "status", "created_at"),
        Index("ix_pro_service_quote_flow_id", "flow_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)
    org_id: UUID = Field(
        sa_column=Column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
    )
    flow_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("flow.id", ondelete="SET NULL"), nullable=True),
    )
    requester_user_id: UUID = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="RESTRICT"), nullable=False),
    )
    status: ProServiceQuoteStatus = Field(
        default=ProServiceQuoteStatus.OPEN,
        sa_column=Column(String(length=24), nullable=False),
    )
    assigned_admin_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )

    estimated_minutes_low: int = Field(nullable=False)
    estimated_minutes_high: int = Field(nullable=False)
    rate_low_per_hour: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(10, 2), nullable=True),
    )
    rate_high_per_hour: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(10, 2), nullable=True),
    )

    headline_summary: str = Field(sa_column=Column(Text, nullable=False))
    narrative: str = Field(sa_column=Column(Text, nullable=False))
    conversation_summary: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    org_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    admin_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, onupdate=_utcnow),
    )
    submitted_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    in_progress_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    closed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    closed_by_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
