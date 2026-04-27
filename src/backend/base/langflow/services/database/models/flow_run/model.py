from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Column, Field, JSON, SQLModel


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    PARTIAL_SUCCESS = "partial_success"


class TriggeredBy(str, Enum):
    API = "api"
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    MCP = "mcp"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FlowRunBase(SQLModel):
    organization_id: UUID = Field(foreign_key="organization.id", index=True)
    flow_id: UUID = Field(foreign_key="flow.id", index=True)
    triggered_by: TriggeredBy = Field(sa_column=Column(sa.String(length=16), nullable=False))
    actor_id: UUID | None = Field(default=None)
    status: RunStatus = Field(
        default=RunStatus.QUEUED,
        sa_column=Column(sa.String(length=16), nullable=False, index=True),
    )
    priority: int = Field(default=5)
    inputs: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    inputs_ref: str | None = Field(default=None)
    result: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    result_ref: str | None = Field(default=None)
    error: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    auto_retry: bool = Field(default=False)
    max_retries: int = Field(default=3)
    attempt: int = Field(default=0)
    cancel_requested: bool = Field(default=False)
    timeout_seconds: int = Field(default=600)
    worker_id: str | None = Field(default=None)
    heartbeat_at: datetime | None = Field(default=None)
    queued_at: datetime = Field(default_factory=_utcnow, nullable=False)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    webhook_delivery_state: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default="{}"),
    )


class FlowRun(FlowRunBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "flow_run"
    __table_args__ = (
        sa.Index("ix_flow_run_org_status_queued_at", "organization_id", "status", "queued_at"),
        sa.Index("ix_flow_run_flow_queued_at_desc", "flow_id", "queued_at"),
        sa.Index("ix_flow_run_status_heartbeat", "status", "heartbeat_at"),
        sa.Index("ix_flow_run_status_finished", "status", "finished_at"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    cost_cents: int | None = Field(default=None, nullable=True)
    model_usage: dict | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )


class FlowRunCreate(FlowRunBase):
    pass


class FlowRunRead(FlowRunBase):
    id: UUID
