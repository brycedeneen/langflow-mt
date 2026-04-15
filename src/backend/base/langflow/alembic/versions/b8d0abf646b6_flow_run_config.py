"""flow run config

Revision ID: b8d0abf646b6
Revises: 26b3d04efba1
Create Date: 2026-04-15 15:24:51.007077

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = 'b8d0abf646b6'
down_revision: Union[str, None] = '26b3d04efba1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("flow") as batch_op:
        batch_op.add_column(sa.Column("webhook_url", sa.String(length=2048), nullable=True))
        batch_op.add_column(sa.Column("webhook_secret", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("auto_retry", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"))
        batch_op.add_column(sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="600"))


def downgrade() -> None:
    with op.batch_alter_table("flow") as batch_op:
        for col in ("timeout_seconds", "max_retries", "auto_retry", "webhook_secret", "webhook_url"):
            batch_op.drop_column(col)
