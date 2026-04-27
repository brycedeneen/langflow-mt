"""add partial_success runstatus

Revision ID: 60d7508ccfed
Revises: 8f44547cdf82
Create Date: 2026-04-27 10:46:20.223099
"""
from alembic import op
import sqlalchemy as sa


revision = "60d7508ccfed"
down_revision = "8f44547cdf82"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # FlowRun.status is stored as VARCHAR(16), not a Postgres enum type.
    # No DDL is required to allow the new value — application-layer enum extension is enough.
    # This migration is intentionally a no-op DDL but is preserved as a marker so the
    # head moves and any future DDL on flow_run can rebase on top of it.
    pass


def downgrade() -> None:
    pass
