"""add tag tables

Revision ID: a73dd31cf140
Revises: 1aa93486a636
Create Date: 2026-04-23
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a73dd31cf140"
down_revision = "1aa93486a636"
branch_labels = None
depends_on = None


TAG_COLOR_VALUES = (
    "slate",
    "red",
    "orange",
    "amber",
    "green",
    "teal",
    "sky",
    "blue",
    "violet",
    "pink",
)


def upgrade() -> None:
    op.create_table(
        "tag",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # CHECK constraint: color must be in palette.
        # Inlined in CREATE TABLE so SQLite (which cannot ALTER TABLE ADD CHECK) accepts it.
        sa.CheckConstraint(
            "color IN ("
            + ", ".join(f"'{c}'" for c in TAG_COLOR_VALUES)
            + ")",
            name="ck_tag_color_palette",
        ),
    )
    # Case-insensitive uniqueness on name.
    op.create_index(
        "uq_tag_name_lower",
        "tag",
        [sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "flow_tag",
        sa.Column(
            "flow_id",
            sa.Uuid(),
            sa.ForeignKey("flow.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.Uuid(),
            sa.ForeignKey("tag.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index("ix_flow_tag_tag_id", "flow_tag", ["tag_id"])

    op.create_table(
        "template_tag",
        sa.Column(
            "template_id",
            sa.Uuid(),
            sa.ForeignKey("template.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.Uuid(),
            sa.ForeignKey("tag.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index("ix_template_tag_tag_id", "template_tag", ["tag_id"])

    # Drop the unused Flow.tags JSON column (spec B.2 / B.3 — never had rows).
    with op.batch_alter_table("flow") as batch:
        batch.drop_column("tags")


def downgrade() -> None:
    # NOTE: Using sa.JSON() instead of postgresql.JSONB here because this migration is
    # exercised against SQLite in local dev round-trip tests and JSONB does not compile
    # on SQLite. The flow.tags column is unused / never populated rows, so the JSON vs
    # JSONB distinction is irrelevant for restore-shape purposes.
    with op.batch_alter_table("flow") as batch:
        batch.add_column(sa.Column("tags", sa.JSON(), nullable=True))
    op.drop_index("ix_template_tag_tag_id", table_name="template_tag")
    op.drop_table("template_tag")
    op.drop_index("ix_flow_tag_tag_id", table_name="flow_tag")
    op.drop_table("flow_tag")
    # ck_tag_color_palette is inlined in the tag table CREATE; dropped with drop_table.
    op.drop_index("uq_tag_name_lower", table_name="tag")
    op.drop_table("tag")
