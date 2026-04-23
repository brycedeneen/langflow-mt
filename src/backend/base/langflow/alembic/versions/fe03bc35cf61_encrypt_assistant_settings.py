"""Re-encrypt pre-existing plaintext assistant.api_key rows.

Revision ID: fe03bc35cf61
Revises: 38586f8ba8ae
Create Date: 2026-04-22

Context: Before this migration, langflow.api.v1.assistant stored the
OpenAI/Anthropic provider API key as plaintext in the Variable table
(type='assistant_setting'). As of the companion code change, writes are
Fernet-encrypted and reads decrypt; a plaintext row is now considered
unreadable. This migration re-encrypts any such row in-place. Idempotent
(skips rows whose value already begins with the Fernet 'gAAAAA' prefix).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "fe03bc35cf61"
down_revision = "38586f8ba8ae"
branch_labels = None
depends_on = None


FERNET_PREFIX = "gAAAAA"


def upgrade() -> None:
    from langflow.services.auth.utils import encrypt_api_key

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, value FROM variable "
            "WHERE name = 'assistant.api_key' "
            "AND value IS NOT NULL "
            "AND value != ''"
        )
    ).fetchall()

    for row_id, value in rows:
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        if value.startswith(FERNET_PREFIX):
            # Already encrypted, skip (idempotent re-run).
            continue
        encrypted = encrypt_api_key(value)
        bind.execute(
            sa.text("UPDATE variable SET value = :v WHERE id = :id"),
            {"v": encrypted, "id": row_id},
        )


def downgrade() -> None:
    # No-op: we cannot safely decrypt without risking exposing cleartext to
    # downgraded code that expected plaintext. Manual rollback only.
    pass
