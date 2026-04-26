"""merge pro_service_quotes with template agent metadata

Revision ID: d6b4990402d7
Revises: 038c8058f29e, d11ef74b2508
Create Date: 2026-04-26 08:12:51.832043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = 'd6b4990402d7'
down_revision: Union[str, None] = ('038c8058f29e', 'd11ef74b2508')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    pass


def downgrade() -> None:
    conn = op.get_bind()
    pass
