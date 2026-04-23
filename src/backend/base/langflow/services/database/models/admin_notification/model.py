from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime
from sqlmodel import Column, Field, ForeignKey, SQLModel


class NotificationCategory(str, Enum):
    USAGE_THRESHOLD = "usage_threshold"
    ALERT_RULE = "alert_rule"
    SYSTEM = "system"


class NotificationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class NotificationAudience(str, Enum):
    SUPER_ADMIN = "super_admin"


class AdminNotification(SQLModel, table=True):
    __tablename__ = "admin_notification"

    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)
    org_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("organization.id", ondelete="SET NULL"), nullable=True),
    )
    category: NotificationCategory = Field(max_length=32, nullable=False)
    severity: NotificationSeverity = Field(max_length=16, default=NotificationSeverity.WARNING, nullable=False)
    title: str = Field(max_length=512, nullable=False)
    body_md: str = Field(nullable=False)
    metadata_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False),
    )
    audience: NotificationAudience = Field(
        max_length=32, default=NotificationAudience.SUPER_ADMIN, nullable=False,
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    read_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    read_by_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
