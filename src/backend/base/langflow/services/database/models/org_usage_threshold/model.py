from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Index, String
from sqlmodel import Column, Field, ForeignKey, SQLModel


class UsageMetric(str, Enum):
    RUNS = "runs"
    RUN_SECONDS = "run_seconds"
    TOKENS = "tokens"


class UsagePeriod(str, Enum):
    DAILY = "daily"
    MONTHLY = "monthly"


class OrgUsageThreshold(SQLModel, table=True):
    __tablename__ = "org_usage_threshold"
    __table_args__ = (
        Index("ix_org_usage_threshold_org_active", "org_id", "is_active"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)
    org_id: UUID = Field(
        sa_column=Column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
    )
    metric: UsageMetric = Field(sa_column=Column(String(length=32), nullable=False))
    period: UsagePeriod = Field(sa_column=Column(String(length=16), nullable=False))
    threshold_value: int = Field(sa_column=Column(BigInteger, nullable=False))
    is_active: bool = Field(default=True, nullable=False)
    last_fired_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    cooldown_seconds: int = Field(default=3600, nullable=False)
    created_by_user_id: UUID = Field(
        sa_column=Column(ForeignKey("user.id"), nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
