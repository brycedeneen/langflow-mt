"""add based_on_template_flow_id to flow

Revision ID: 6ec028483162
Revises: 93e68a94275a
Create Date: 2026-04-18 17:46:09.617341

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = '6ec028483162'
down_revision: Union[str, None] = '93e68a94275a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("based_on_template_flow_id", sa.Uuid(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_flow_based_on_template_flow_id",
            "flow",
            ["based_on_template_flow_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_flow_based_on_template_flow_id", type_="foreignkey"
        )
        batch_op.drop_column("based_on_template_flow_id")
