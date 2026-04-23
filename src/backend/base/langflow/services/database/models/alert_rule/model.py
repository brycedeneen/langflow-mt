from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime
from sqlmodel import Column, Field, ForeignKey, SQLModel


class AlertRuleType(str, Enum):
    CONSECUTIVE_FAILURES = "consecutive_failures"
    ERROR_RATE = "error_rate"
    SLA_DURATION = "sla_duration"


class AlertRule(SQLModel, table=True):
    __tablename__ = "alert_rule"

    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)
    org_id: UUID = Field(
        sa_column=Column(ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
    )
    flow_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("flow.id", ondelete="CASCADE"), nullable=True),
    )
    rule_type: AlertRuleType = Field(max_length=32, nullable=False)
    config: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False),
    )
    is_active: bool = Field(default=True, nullable=False)
    last_fired_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    cooldown_seconds: int = Field(default=900, nullable=False)
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
