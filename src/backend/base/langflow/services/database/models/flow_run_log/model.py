from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Column, Field, JSON, SQLModel


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class FlowRunLog(SQLModel, table=True):
    __tablename__ = "flow_run_log"

    id: int | None = Field(default=None, primary_key=True)
    run_id: UUID = Field(foreign_key="flow_run.id", index=True, nullable=False)
    ts: datetime = Field(nullable=False)
    level: LogLevel = Field(sa_column=Column(sa.String(length=8), nullable=False))
    node_id: str | None = Field(default=None)
    message: str = Field(nullable=False)
    extra: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
