from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Index, String
from sqlmodel import Column, Field, ForeignKey, SQLModel


class AuditTargetType(str, Enum):
    FLOW = "flow"
    TEMPLATE = "template"
    VARIABLE = "variable"
    ORGANIZATION = "organization"
    MEMBERSHIP = "membership"
    API_KEY = "api_key"
    ROLE_ASSIGNMENT = "role_assignment"


class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ARCHIVE = "archive"
    UNARCHIVE = "unarchive"
    ASSIGN_ROLE = "assign_role"


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_org_occurred", "org_id", "occurred_at"),
        Index("ix_audit_log_actor_occurred", "actor_user_id", "occurred_at"),
        Index("ix_audit_log_target", "target_type", "target_id", "occurred_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    actor_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
    actor_email: str = Field(max_length=320, nullable=False)
    actor_is_super: bool = Field(default=False, nullable=False)
    org_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("organization.id", ondelete="SET NULL"), nullable=True),
    )
    target_type: AuditTargetType = Field(
        sa_column=Column(String(32), nullable=False),
    )
    target_id: UUID = Field(nullable=False)
    action: AuditAction = Field(
        sa_column=Column(String(32), nullable=False),
    )
    diff: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False),
    )
    diff_hash: str = Field(max_length=64, nullable=False)
    request_metadata: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
