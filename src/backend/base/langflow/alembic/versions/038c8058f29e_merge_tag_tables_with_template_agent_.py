"""merge tag tables with template agent metadata

Revision ID: 038c8058f29e
Revises: 67630b517fbb, a73dd31cf140
Create Date: 2026-04-25 20:00:19.113584

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.engine.reflection import Inspector
from langflow.utils import migration


# revision identifiers, used by Alembic.
revision: str = '038c8058f29e'
down_revision: Union[str, None] = ('67630b517fbb', 'a73dd31cf140')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    pass


def downgrade() -> None:
    conn = op.get_bind()
    pass
