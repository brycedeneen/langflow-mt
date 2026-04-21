"""drop ix_template_active — a partial index keyed on the PK that helped no query

Revision ID: cc6f6cca0ead
Revises: 8663a8995703
Create Date: 2026-04-21
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cc6f6cca0ead"
down_revision: str | None = "8663a8995703"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_template_active")


def downgrade() -> None:
    op.execute(
        "CREATE INDEX ix_template_active ON template (id) WHERE archived_at IS NULL"
    )
