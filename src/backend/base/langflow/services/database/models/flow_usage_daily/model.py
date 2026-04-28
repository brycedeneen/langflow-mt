from __future__ import annotations

import datetime as dt
from datetime import timezone
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Index
from sqlmodel import Column, Field, ForeignKey, SQLModel


class FlowUsageDaily(SQLModel, table=True):
    __tablename__ = "flow_usage_daily"
    __table_args__ = (
        Index("ix_flow_usage_daily_org_date", "org_id", "date"),
    )

    # No FK on flow_id by design — daily usage rows are retained for billing
    # and audit after the flow is deleted. The original migration
    # (0acebda9c705) declared ondelete="CASCADE", which silently caused
    # Postgres to drop these rows on flow delete (SQLite doesn't enforce FK
    # cascades, so retention worked there). Migration 3ce76c394183 drops the
    # FK so both backends honor the retention semantic that
    # `cascade_delete_flows` already encodes by NOT deleting from this table.
    flow_id: UUID = Field(primary_key=True, nullable=False)
    date: dt.date = Field(primary_key=True, nullable=False)
    org_id: UUID = Field(
        sa_column=Column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
    )
    runs: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    run_seconds: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    tokens: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    cost_cents: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    updated_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
