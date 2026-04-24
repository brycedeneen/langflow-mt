from __future__ import annotations

import datetime as dt
from datetime import timezone
from uuid import UUID

from sqlalchemy import BigInteger, DateTime
from sqlmodel import Column, Field, ForeignKey, SQLModel


class OrgUsageDaily(SQLModel, table=True):
    __tablename__ = "org_usage_daily"

    org_id: UUID = Field(
        sa_column=Column(ForeignKey("organization.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    )
    date: dt.date = Field(primary_key=True, nullable=False)
    runs: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    run_seconds: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    tokens: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    cost_cents: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    updated_at: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
