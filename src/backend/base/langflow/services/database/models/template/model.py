"""Template SQLModel + Pydantic schemas for Phase 1 (save-as-template + blanking).

Phase 1 notes:
- scope is always 'platform'; org_id always NULL. Columns reserved for Phase 2.
- No versioning: every Template row represents the current content. Re-save
  with same name overwrites in place (UPSERT by name at the service layer).
- soft-delete via `deleted_at` nullable column.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, String, Text, Uuid
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Template(SQLModel, table=True):
    """Authored template (platform-scoped in Phase 1)."""

    __tablename__ = "template"
    __table_args__ = (
        CheckConstraint(
            "(scope = 'platform' AND org_id IS NULL) OR "
            "(scope = 'org' AND org_id IS NOT NULL)",
            name="ck_template_scope_org_coherence",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(
        sa_column=Column(String(255), nullable=False, unique=True, index=True),
    )
    description: str | None = Field(
        default=None, sa_column=Column(Text(), nullable=True),
    )
    icon: str | None = Field(default=None, max_length=64)
    gradient: str | None = Field(default=None, max_length=32)

    scope: str = Field(
        default="platform",
        sa_column=Column(String(16), nullable=False, default="platform"),
        description="Phase 1 is always 'platform'. 'org' reserved for Phase 2.",
    )
    org_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid(), ForeignKey("organization.id", ondelete="CASCADE"), nullable=True,
        ),
        description="Always NULL in Phase 1. Reserved for Phase 2 org-scoped templates.",
    )

    nodes: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))
    edges: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))

    created_by: UUID = Field(
        sa_column=Column(
            Uuid(), ForeignKey("user.id", ondelete="RESTRICT"), nullable=False,
        ),
    )
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utc_now),
    )
    updated_by: UUID = Field(
        sa_column=Column(
            Uuid(), ForeignKey("user.id", ondelete="RESTRICT"), nullable=False,
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=_utc_now,
            onupdate=_utc_now,
        ),
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, default=None),
    )


# ---------------------------- Pydantic schemas ----------------------------


class TemplateRead(BaseModel):
    """Slim catalog listing shape (no nodes/edges)."""

    id: UUID
    name: str
    description: str | None
    icon: str | None
    gradient: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateReadDetail(TemplateRead):
    """Full shape for template detail / clone payload."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]

    model_config = {"from_attributes": True}


class BlankedField(BaseModel):
    node_id: str
    field_name: str


class TemplateCreate(BaseModel):
    source_flow_id: UUID
    name: str = PydanticField(..., max_length=255)
    description: str | None = None
    icon: str | None = PydanticField(default=None, max_length=64)
    gradient: str | None = PydanticField(default=None, max_length=32)
    blanked_fields: list[BlankedField] = PydanticField(default_factory=list)


class TemplateUpdate(BaseModel):
    """Same shape as TemplateCreate — PUT accepts a fresh source_flow_id so content can be re-sourced from any flow on overwrite."""

    source_flow_id: UUID
    name: str = PydanticField(..., max_length=255)
    description: str | None = None
    icon: str | None = PydanticField(default=None, max_length=64)
    gradient: str | None = PydanticField(default=None, max_length=32)
    blanked_fields: list[BlankedField] = PydanticField(default_factory=list)
