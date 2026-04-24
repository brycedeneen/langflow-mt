"""SQLModel definitions for Tag and the Flow/Template tag join tables.

The underlying tables are created by Alembic revision ``a73dd31cf140``;
these models must stay shape-compatible with that migration:

* ``tag`` — functional unique index ``uq_tag_name_lower`` on ``lower(name)``
  and a ``ck_tag_color_palette`` CHECK constraint restricting ``color``
  to the 10-value palette enumerated by :class:`TagColor`.
* ``flow_tag`` / ``template_tag`` — composite PKs with ``ON DELETE CASCADE``
  on both FKs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text, func, text
from sqlmodel import Field, SQLModel

from langflow.schema.serialize import UUIDstr


class TagColor(str, Enum):
    """Allowed tag colors — must stay in sync with ``ck_tag_color_palette``."""

    SLATE = "slate"
    RED = "red"
    ORANGE = "orange"
    AMBER = "amber"
    GREEN = "green"
    TEAL = "teal"
    SKY = "sky"
    BLUE = "blue"
    VIOLET = "violet"
    PINK = "pink"


_PALETTE = tuple(c.value for c in TagColor)
_COLOR_CHECK_CLAUSE = "color IN (" + ", ".join(f"'{c}'" for c in _PALETTE) + ")"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Tag(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "tag"
    __table_args__ = (
        Index("uq_tag_name_lower", text("lower(name)"), unique=True),
        CheckConstraint(_COLOR_CHECK_CLAUSE, name="ck_tag_color_palette"),
    )

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(sa_column=Column(String(64), nullable=False))
    color: str = Field(sa_column=Column(String(32), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_by: UUIDstr | None = Field(
        default=None,
        sa_column=Column(sa.Uuid(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )


class FlowTag(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "flow_tag"
    __table_args__ = (Index("ix_flow_tag_tag_id", "tag_id"),)

    flow_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("flow.id", ondelete="CASCADE"), primary_key=True)
    )
    tag_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True)
    )


class TemplateTag(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "template_tag"
    __table_args__ = (Index("ix_template_tag_tag_id", "tag_id"),)

    template_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("template.id", ondelete="CASCADE"), primary_key=True)
    )
    tag_id: UUIDstr = Field(
        sa_column=Column(sa.Uuid(), ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True)
    )
