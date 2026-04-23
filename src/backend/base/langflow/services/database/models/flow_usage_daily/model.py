from __future__ import annotations

import datetime as dt
from datetime import timezone
from uuid import UUID

from sqlalchemy import DateTime
from sqlmodel import Column, Field, ForeignKey, SQLModel


class FlowUsageDaily(SQLModel, table=True):
    __tablename__ = "flow_usage_daily"

    flow_id: UUID = Field(
        sa_column=Column(ForeignKey("flow.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    date: dt.date = Field(primary_key=True, nullable=False)
    org_id: UUID = Field(
        sa_column=Column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
    )
    runs: int = Field(default=0, nullable=False)
    run_seconds: int = Field(default=0, nullable=False)
    tokens: int = Field(default=0, nullable=False)
    cost_cents: int = Field(default=0, nullable=False)
    updated_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
