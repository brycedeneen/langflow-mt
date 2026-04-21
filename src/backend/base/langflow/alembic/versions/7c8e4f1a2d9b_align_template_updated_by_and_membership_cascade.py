"""align template.updated_by nullability and membership.user_id cascade

Revision ID: 7c8e4f1a2d9b
Revises: e0a0990b26b1
Create Date: 2026-04-21

Fills two gaps left by prior migrations:
1. `template.updated_by` — model is nullable, DB was still NOT NULL.
2. `membership.user_id` FK — model declares ON DELETE CASCADE, original
   multi-tenant foundation migration omitted it.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c8e4f1a2d9b"
down_revision: str | None = "e0a0990b26b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_PER_SCOPE_INDEX_SQL = (
    "CREATE UNIQUE INDEX uq_template_name_per_scope "
    "ON template (COALESCE(org_id, '00000000-0000-0000-0000-000000000000'), LOWER(name))"
)


def upgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"

    # On SQLite, batch_alter_table rebuilds the table and silently drops expression
    # indexes it can't reflect (see e0a0990b26b1 for the same landmine). On Postgres,
    # batch_alter_table emits plain ALTER TABLE and the index survives — so the
    # drop/recreate dance is SQLite-only.
    if is_sqlite:
        op.execute("DROP INDEX IF EXISTS uq_template_name_per_scope")
    with op.batch_alter_table("template") as batch:
        batch.alter_column("updated_by", existing_type=sa.Uuid(), nullable=True)
    if is_sqlite:
        op.execute(_PER_SCOPE_INDEX_SQL)

    with op.batch_alter_table("membership") as batch:
        batch.drop_constraint("fk_membership_user_id_user", type_="foreignkey")
        batch.create_foreign_key(
            "fk_membership_user_id_user",
            "user",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"

    with op.batch_alter_table("membership") as batch:
        batch.drop_constraint("fk_membership_user_id_user", type_="foreignkey")
        batch.create_foreign_key(
            "fk_membership_user_id_user",
            "user",
            ["user_id"],
            ["id"],
        )

    if is_sqlite:
        op.execute("DROP INDEX IF EXISTS uq_template_name_per_scope")
    with op.batch_alter_table("template") as batch:
        batch.alter_column("updated_by", existing_type=sa.Uuid(), nullable=False)
    if is_sqlite:
        op.execute(_PER_SCOPE_INDEX_SQL)
