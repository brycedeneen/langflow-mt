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


def upgrade() -> None:
    with op.batch_alter_table("template") as batch:
        batch.alter_column("updated_by", existing_type=sa.Uuid(), nullable=True)

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
    with op.batch_alter_table("membership") as batch:
        batch.drop_constraint("fk_membership_user_id_user", type_="foreignkey")
        batch.create_foreign_key(
            "fk_membership_user_id_user",
            "user",
            ["user_id"],
            ["id"],
        )

    with op.batch_alter_table("template") as batch:
        batch.alter_column("updated_by", existing_type=sa.Uuid(), nullable=False)
