"""Template SQLModel + Pydantic schemas.

Both 'platform' and 'org' scopes are supported:
- platform-scoped templates have org_id = NULL.
- org-scoped templates have org_id = <organization.id>.
The check constraint ck_template_scope_org_coherence enforces this invariant.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text, Uuid, text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from langflow.services.database.models.category.model import Category
    from langflow.services.database.models.tag.model import Tag

from langflow.services.database.models.category.model import CategoryRead, TemplateCategory
from langflow.services.database.models.tag.model import TemplateTag
from langflow.services.database.models.tag.schema import TagRead


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Template(SQLModel, table=True):
    """Authored template (platform or org-scoped)."""

    __tablename__ = "template"
    # Match the Alembic-declared per-scope unique index (revision e0a0990b26b1):
    # case-insensitive name uniqueness scoped by org_id, with a nil-UUID sentinel
    # so platform-scoped rows (org_id IS NULL) share one namespace.
    __table_args__ = (
        Index(
            "uq_template_name_per_scope",
            text("COALESCE(org_id, '00000000-0000-0000-0000-000000000000')"),
            text("LOWER(name)"),
            unique=True,
        ),
        CheckConstraint(
            "(scope = 'platform' AND org_id IS NULL) OR "
            "(scope = 'org' AND org_id IS NOT NULL)",
            name="ck_template_scope_org_coherence",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(
        sa_column=Column(String(255), nullable=False, index=True),
    )
    description: str | None = Field(
        default=None, sa_column=Column(Text(), nullable=True),
    )
    icon: str | None = Field(default=None, max_length=64)
    gradient: str | None = Field(default=None, max_length=32)
    agent_summary: str | None = Field(
        default=None, sa_column=Column(Text(), nullable=True),
    )
    agent_usage_notes: str | None = Field(
        default=None, sa_column=Column(Text(), nullable=True),
    )

    scope: str = Field(
        default="platform",
        sa_column=Column(String(16), nullable=False, default="platform"),
    )
    org_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid(), ForeignKey("organization.id", ondelete="CASCADE"), nullable=True,
        ),
    )

    nodes: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))
    edges: list[dict[str, Any]] = Field(sa_column=Column(JSON, nullable=False))

    created_by: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid(), ForeignKey("user.id", ondelete="RESTRICT"), nullable=True,
        ),
    )
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utc_now),
    )
    updated_by: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid(), ForeignKey("user.id", ondelete="RESTRICT"), nullable=True,
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
    archived_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, default=None),
    )

    categories: list["Category"] = Relationship(
        back_populates="templates", link_model=TemplateCategory
    )
    tags: list["Tag"] = Relationship(back_populates="templates", link_model=TemplateTag)


# ---------------------------- Pydantic schemas ----------------------------


class TemplateRead(BaseModel):
    """Slim catalog listing shape (no nodes/edges)."""

    id: UUID
    name: str
    description: str | None
    icon: str | None
    gradient: str | None
    archived_at: datetime | None
    categories: list[CategoryRead]
    tags: list[TagRead] = PydanticField(
        default_factory=list,
        description="Tags assigned to this template via template_tag",
    )
    created_at: datetime
    updated_at: datetime
    agent_summary: str | None = None
    agent_usage_notes: str | None = None

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
    scope: Literal["platform", "org"] = "platform"
    org_id: UUID | None = None
    category_ids: list[UUID] = PydanticField(default_factory=list)


class TemplateUpdate(BaseModel):
    """Same shape as TemplateCreate — PUT accepts a fresh source_flow_id so content can be re-sourced from any flow on overwrite."""

    source_flow_id: UUID
    name: str = PydanticField(..., max_length=255)
    description: str | None = None
    icon: str | None = PydanticField(default=None, max_length=64)
    gradient: str | None = PydanticField(default=None, max_length=32)
    blanked_fields: list[BlankedField] = PydanticField(default_factory=list)
    category_ids: list[UUID] | None = None


class TemplatePatch(BaseModel):
    """Partial update body for PATCH /templates/{id}.

    Field semantics — driven by ``model_fields_set``:
    - field absent from request body  -> leave current value untouched
    - field present and set to ``null`` -> clear the column
    - field present and set to a value -> overwrite

    For ``category_ids``: an empty list clears tags; the field key being
    absent leaves tags unchanged (mirrors the column-level rule).
    """

    name: str | None = PydanticField(default=None, max_length=255)
    description: str | None = None
    icon: str | None = PydanticField(default=None, max_length=64)
    gradient: str | None = PydanticField(default=None, max_length=32)
    category_ids: list[UUID] | None = None
    agent_summary: str | None = None
    agent_usage_notes: str | None = None
