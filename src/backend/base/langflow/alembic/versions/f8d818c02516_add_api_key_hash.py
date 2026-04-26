"""add api_key_hash column to api_key for O(1) lookup

Adds an HMAC-SHA256 (keyed by ``SECRET_KEY``) hex digest column on ``api_key``
to replace the O(N) Fernet-decrypt scan in ``_check_key_from_db``.

Backfill: for each existing row, attempt to decrypt the stored ciphertext via
the same Fernet logic the auth service uses; if decryption fails, treat the
stored value as legacy plaintext and hash it directly. Rows that match neither
shape are logged and skipped — they require manual remediation.

The unique index is created after the backfill so duplicate-NULL handling is
not an issue (NULL is allowed; only non-NULL duplicates would conflict).

Revision ID: f8d818c02516
Revises: 4f2a9b1c7e83
Create Date: 2026-04-26
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
import random
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# revision identifiers
revision: str = "f8d818c02516"
down_revision: str | Sequence[str] | None = "4f2a9b1c7e83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_MINIMUM_KEY_LENGTH = 32


def _ensure_valid_key(raw_key: str) -> bytes:
    """Mirror of ``AuthService._ensure_valid_key`` — kept inline to avoid
    importing the live service from a migration (which would couple schema
    history to runtime initialization order).
    """
    if len(raw_key) < _MINIMUM_KEY_LENGTH:
        random.seed(raw_key)
        key = bytes(random.getrandbits(8) for _ in range(32))
        return base64.urlsafe_b64encode(key)
    padding_needed = 4 - len(raw_key) % 4
    return (raw_key + "=" * padding_needed).encode()


def _get_secret_key() -> str | None:
    """Resolve the configured SECRET_KEY without forcing the full settings
    machinery if it isn't bootstrapped. Falls back to the env var, which is
    the same source the SettingsService reads.
    """
    try:
        from langflow.services.deps import get_settings_service  # noqa: PLC0415

        settings_service = get_settings_service()
        return settings_service.auth_settings.SECRET_KEY.get_secret_value()
    except Exception:  # noqa: BLE001
        import os  # noqa: PLC0415

        return os.environ.get("LANGFLOW_SECRET_KEY") or os.environ.get("SECRET_KEY")


def _compute_hash(raw_api_key: str, secret_key: str) -> str:
    return hmac.new(secret_key.encode(), raw_api_key.encode(), hashlib.sha256).hexdigest()


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    columns = {col["name"] for col in inspector.get_columns("api_key")}
    if "api_key_hash" not in columns:
        with op.batch_alter_table("api_key", schema=None) as batch_op:
            batch_op.add_column(sa.Column("api_key_hash", sa.String(), nullable=True))

    # Backfill: compute hash for every existing row.
    secret_key = _get_secret_key()
    if not secret_key:
        logger.warning(
            "api_key_hash backfill skipped: SECRET_KEY is not configured. "
            "Existing rows will lack a hash and will fail O(1) auth lookup until "
            "rotated. Set SECRET_KEY and re-run this migration step manually."
        )
    else:
        fernet = Fernet(_ensure_valid_key(secret_key))
        rows = conn.execute(sa.text("SELECT id, api_key FROM api_key WHERE api_key_hash IS NULL")).all()

        backfilled = 0
        skipped = 0
        for row in rows:
            stored = row.api_key
            if stored is None:
                continue

            raw: str | None = None
            try:
                raw = fernet.decrypt(stored.encode()).decode()
            except (InvalidToken, ValueError, TypeError, binascii.Error, UnicodeDecodeError):
                # Treat as legacy plaintext entry — hash directly. ``sk-`` prefix
                # is a strong signal the value is plaintext (matches create path).
                if isinstance(stored, str) and stored:
                    raw = stored

            if raw is None:
                logger.warning(
                    "api_key id=%s could not be decrypted or treated as plaintext during "
                    "api_key_hash backfill; skipping. Manual remediation required.",
                    row.id,
                )
                skipped += 1
                continue

            digest = _compute_hash(raw, secret_key)
            conn.execute(
                sa.text("UPDATE api_key SET api_key_hash = :h WHERE id = :id"),
                {"h": digest, "id": row.id},
            )
            backfilled += 1

        if backfilled or skipped:
            logger.info(
                "api_key_hash backfill complete: %d hashed, %d skipped.",
                backfilled,
                skipped,
            )

    # Create the unique index after backfill so duplicates surface here, not later.
    indexes = {ix["name"] for ix in inspector.get_indexes("api_key")}
    if "ix_api_key_api_key_hash" not in indexes:
        with op.batch_alter_table("api_key", schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f("ix_api_key_api_key_hash"),
                ["api_key_hash"],
                unique=True,
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    indexes = {ix["name"] for ix in inspector.get_indexes("api_key")}
    if "ix_api_key_api_key_hash" in indexes:
        with op.batch_alter_table("api_key", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_api_key_api_key_hash"))

    columns = {col["name"] for col in inspector.get_columns("api_key")}
    if "api_key_hash" in columns:
        with op.batch_alter_table("api_key", schema=None) as batch_op:
            batch_op.drop_column("api_key_hash")
