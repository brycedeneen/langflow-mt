"""merge perf-bundle alembic heads

Revision ID: 8f44547cdf82
Revises: 3bc69b462cd0, f8d818c02516
Create Date: 2026-04-27 09:33:49.072370

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = '8f44547cdf82'
down_revision: Union[str, None] = ('3bc69b462cd0', 'f8d818c02516')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    pass


def downgrade() -> None:
    conn = op.get_bind()
    pass
