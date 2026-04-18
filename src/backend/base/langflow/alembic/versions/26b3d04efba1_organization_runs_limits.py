"""organization runs limits

Revision ID: 26b3d04efba1
Revises: 88d7df14514c
Create Date: 2026-04-15 15:22:21.550154

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = '26b3d04efba1'
down_revision: Union[str, None] = '88d7df14514c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing_cols = {c["name"] for c in insp.get_columns("organization")}
    need_concurrent = "runs_max_concurrent" not in existing_cols
    need_priority = "runs_priority_tier" not in existing_cols
    if need_concurrent or need_priority:
        with op.batch_alter_table("organization") as batch_op:
            if need_concurrent:
                batch_op.add_column(sa.Column("runs_max_concurrent", sa.Integer(), nullable=False, server_default="5"))
            if need_priority:
                batch_op.add_column(sa.Column("runs_priority_tier", sa.String(length=16), nullable=False, server_default="default"))


def downgrade() -> None:
    with op.batch_alter_table("organization") as batch_op:
        batch_op.drop_column("runs_priority_tier")
        batch_op.drop_column("runs_max_concurrent")
