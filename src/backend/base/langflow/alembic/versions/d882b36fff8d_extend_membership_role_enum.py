"""extend membership role enum

Revision ID: d882b36fff8d
Revises: cc6f6cca0ead
Create Date: 2026-04-22
"""
from alembic import op

revision = "d882b36fff8d"
down_revision = "cc6f6cca0ead"
branch_labels = None
depends_on = None

NEW_VALUES = ("admin", "member", "operator", "viewer")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for value in NEW_VALUES:
            op.execute(f"ALTER TYPE membership_role_enum ADD VALUE IF NOT EXISTS '{value}'")
    # SQLite uses a CHECK constraint derived from the Python enum; no DDL needed —
    # SQLAlchemy rebuilds it on next connection.


def downgrade() -> None:
    # Postgres does not support ALTER TYPE ... DROP VALUE. Rolling back requires
    # either dropping and recreating the enum (data-destructive) or a forward-fix
    # deploy. Intentional no-op; forward-only migration.
    pass
