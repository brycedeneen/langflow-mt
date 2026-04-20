"""Add template table (Phase 1 backend-only, additive).

Revision ID: bb45fc63cdcd
Revises: c8a5f32e9b74
Create Date: 2026-04-20 18:00:00.000000

Phase 1 (backend-only) — additive-only migration. Creates the `template`
table used by the `/api/v1/templates` CRUD endpoints. Does NOT touch
starter-project Flow rows, does NOT retarget any existing foreign keys,
does NOT delete the Starter Projects folder. Phase 2 will handle the
data migration when the two catalogs are consolidated.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bb45fc63cdcd"
down_revision: str | None = "c8a5f32e9b74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "template",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(length=64), nullable=True),
        sa.Column("gradient", sa.String(length=32), nullable=True),
        sa.Column(
            "scope",
            sa.String(length=16),
            nullable=False,
            server_default="platform",
        ),
        sa.Column(
            "org_id",
            sa.Uuid(),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("nodes", sa.JSON(), nullable=False),
        sa.Column("edges", sa.JSON(), nullable=False),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_by",
            sa.Uuid(),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("name", name="uq_template_name"),
        sa.CheckConstraint(
            "(scope = 'platform' AND org_id IS NULL) OR "
            "(scope = 'org' AND org_id IS NOT NULL)",
            name="ck_template_scope_org_coherence",
        ),
    )
    op.create_index("ix_template_name", "template", ["name"])


def downgrade() -> None:
    op.drop_index("ix_template_name", table_name="template")
    op.drop_table("template")
