"""Category SQLModel + Pydantic schemas.

Category rows are the canonical tag taxonomy for Templates.
Each Template may belong to zero or more Categories via the
TemplateCategory join table.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Uuid, func, text
from sqlmodel import Field, Relationship, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TemplateCategory(SQLModel, table=True):
    """Join table linking Templates to Categories (M:N)."""

    __tablename__ = "template_category"
    __table_args__ = (
        Index("ix_template_category_category_id", "category_id"),
    )

    template_id: UUID = Field(
        sa_column=Column(Uuid(), ForeignKey("template.id", ondelete="CASCADE"), primary_key=True),
    )
    category_id: UUID = Field(
        sa_column=Column(Uuid(), ForeignKey("category.id", ondelete="CASCADE"), primary_key=True),
    )


class Category(SQLModel, table=True):
    """Taxonomy tag for grouping Templates (e.g. 'RAG', 'Agent')."""

    __tablename__ = "category"
    __table_args__ = (
        Index("uq_category_name_lower", text("LOWER(name)"), unique=True),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(
        sa_column=Column(String(64), nullable=False),
    )
    icon: str = Field(
        sa_column=Column(String(64), nullable=False),
    )
    color: str = Field(
        sa_column=Column(String(16), nullable=False),
    )
    description: str | None = Field(
        default=None, sa_column=Column(String(256), nullable=True),
    )
    created_by: UUID | None = Field(
        default=None,
        foreign_key="user.id",
        nullable=True,
    )
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utc_now),
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

    templates: list["Template"] = Relationship(
        back_populates="categories", link_model=TemplateCategory
    )


# ---------------------------- Pydantic schemas ----------------------------


class CategoryCreate(BaseModel):
    """Payload for POST /api/v1/categories."""

    name: str = PydanticField(min_length=1, max_length=64)
    icon: str = PydanticField(min_length=1, max_length=64)
    color: str = PydanticField(min_length=1, max_length=16)
    description: str | None = PydanticField(default=None, max_length=256)


class CategoryUpdate(BaseModel):
    """Payload for PATCH /api/v1/categories/{id}."""

    name: str | None = PydanticField(default=None, min_length=1, max_length=64)
    icon: str | None = PydanticField(default=None, min_length=1, max_length=64)
    color: str | None = PydanticField(default=None, min_length=1, max_length=16)
    description: str | None = PydanticField(default=None, max_length=256)


class CategoryRead(BaseModel):
    """Response shape for GET /api/v1/categories."""

    id: UUID
    name: str
    icon: str
    color: str
    description: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
