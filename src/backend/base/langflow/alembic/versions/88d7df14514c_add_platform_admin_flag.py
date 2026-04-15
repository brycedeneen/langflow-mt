"""add platform admin flag

Revision ID: 88d7df14514c
Revises: 0e6138e7a0c2
Create Date: 2026-04-15 08:49:58.090998

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '88d7df14514c'
down_revision: Union[str, None] = '0e6138e7a0c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "is_platform_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute('UPDATE "user" SET is_platform_admin = TRUE WHERE is_superuser = TRUE')
    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column("is_platform_admin", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("is_platform_admin")
