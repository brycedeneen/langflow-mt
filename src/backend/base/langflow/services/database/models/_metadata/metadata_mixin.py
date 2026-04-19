"""Shared columns for template_metadata and component_metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentMetadataMixin(SQLModel):
    """Mixin providing the shared columns for agent-facing metadata rows.

    Uses ``sa_type=Text`` rather than ``sa_column=Column(Text)`` because
    SQLModel mixins cannot share a single Column instance across multiple
    concrete tables — each subclass needs its own column, but the type is
    safe to share.
    """

    agent_usage_notes: str | None = Field(default=None, sa_type=Text)
    agent_summary: str | None = Field(default=None, sa_type=Text)
    updated_by: UUID | None = Field(default=None, foreign_key="user.id", nullable=True)
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column_kwargs={"onupdate": _utcnow},
    )
