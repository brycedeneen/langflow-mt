"""extend notification enums (flow_error, error)

Revision ID: 74b14a2dee5b
Revises: 60d7508ccfed
Create Date: 2026-04-27 11:07:12.836431
"""
from alembic import op


revision = "74b14a2dee5b"
down_revision = "60d7508ccfed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # AdminNotification.category and .severity are stored as VARCHAR (32 / 16);
    # enums are enforced at the application layer. No DDL needed.
    pass


def downgrade() -> None:
    pass
