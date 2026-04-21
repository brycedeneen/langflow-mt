"""category and template rework

Revision ID: e0a0990b26b1
Revises: bb45fc63cdcd
Create Date: 2026-04-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e0a0990b26b1"
down_revision: str | None = "bb45fc63cdcd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. category table
    op.create_table(
        "category",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("icon", sa.String(length=64), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=False),
        sa.Column("description", sa.String(length=256), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_category_name_lower",
        "category",
        [sa.text("LOWER(name)")],
        unique=True,
    )

    # 2. template_category join table
    op.create_table(
        "template_category",
        sa.Column("template_id", sa.Uuid(), sa.ForeignKey("template.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("category.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("ix_template_category_category_id", "template_category", ["category_id"])

    # 3. template.archived_at + partial index
    op.add_column("template", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_template_active",
        "template",
        ["id"],
        postgresql_where=sa.text("archived_at IS NULL"),
        sqlite_where=sa.text("archived_at IS NULL"),
    )

    # 4. template.created_by → nullable
    with op.batch_alter_table("template") as batch:
        batch.alter_column("created_by", existing_type=sa.Uuid(), nullable=True)

    # 5. Replace global name uniqueness with per-scope uniqueness.
    # op.f() marks names as "already convention-applied" so naming_convention doesn't
    # double-prefix them.
    with op.batch_alter_table("template") as batch:
        batch.drop_constraint(op.f("uq_template_name"), type_="unique")
    # Expression index: use raw SQL for cross-dialect compatibility.
    # SQLite supports COALESCE() in index expressions (verified); IF NOT EXISTS is
    # defensive against partial re-runs.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_template_name_per_scope "
        "ON template (COALESCE(org_id, '00000000-0000-0000-0000-000000000000'), LOWER(name))"
    )

    # 6. Rewrite scope coherence constraint to allow 'org' scope.
    # Note: bb45fc63cdcd already uses the broader constraint text, so this is a
    # semantic no-op for existing data, but ensures the constraint is present under
    # the right name in the new schema.
    with op.batch_alter_table("template") as batch:
        batch.drop_constraint(op.f("ck_template_scope_org_coherence"), type_="check")
        batch.create_check_constraint(
            op.f("ck_template_scope_org_coherence"),
            "(scope = 'platform' AND org_id IS NULL) OR (scope = 'org' AND org_id IS NOT NULL)",
        )


def downgrade() -> None:
    # Restore scope coherence constraint (same text as bb45fc63cdcd had)
    with op.batch_alter_table("template") as batch:
        batch.drop_constraint(op.f("ck_template_scope_org_coherence"), type_="check")
        batch.create_check_constraint(
            op.f("ck_template_scope_org_coherence"),
            "(scope = 'platform' AND org_id IS NULL) OR (scope = 'org' AND org_id IS NOT NULL)",
        )

    op.execute("DROP INDEX IF EXISTS uq_template_name_per_scope")
    with op.batch_alter_table("template") as batch:
        batch.create_unique_constraint(op.f("uq_template_name"), ["name"])

    with op.batch_alter_table("template") as batch:
        batch.alter_column("created_by", existing_type=sa.Uuid(), nullable=False)

    op.drop_index("ix_template_active", table_name="template")
    op.drop_column("template", "archived_at")

    op.drop_index("ix_template_category_category_id", table_name="template_category")
    op.drop_table("template_category")

    op.drop_index("uq_category_name_lower", table_name="category")
    op.drop_table("category")
