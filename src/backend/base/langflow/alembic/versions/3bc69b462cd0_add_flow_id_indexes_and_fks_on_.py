"""Add flow_id indexes and FKs on transaction and message tables

The ``transaction.flow_id`` and ``message.flow_id`` columns are filtered on by
the monitor endpoints but lacked both an index and a foreign-key constraint to
``flow.id``. This caused full table scans for those queries. This migration
adds the missing indexes and foreign-key constraints idempotently.

Revision ID: 3bc69b462cd0
Revises: 4f2a9b1c7e83
Create Date: 2026-04-26
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "3bc69b462cd0"
down_revision: str | Sequence[str] | None = "4f2a9b1c7e83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TRANSACTION_INDEX = "ix_transaction_flow_id"
_MESSAGE_INDEX = "ix_message_flow_id"
_TRANSACTION_FK = "fk_transaction_flow_id_flow"
_MESSAGE_FK = "fk_message_flow_id_flow"


def _existing_index_names(conn, table_name: str) -> set[str]:
    inspector = sa.inspect(conn)
    return {idx["name"] for idx in inspector.get_indexes(table_name) if idx.get("name")}


def _existing_fk_for_column(conn, table_name: str, column_name: str) -> str | None:
    inspector = sa.inspect(conn)
    for fk in inspector.get_foreign_keys(table_name):
        if column_name in fk.get("constrained_columns", []):
            return fk.get("name")
    return None


def upgrade() -> None:
    conn = op.get_bind()

    # ---------------------- transaction.flow_id ----------------------
    if migration.table_exists("transaction", conn):
        existing_indexes = _existing_index_names(conn, "transaction")
        existing_fk = _existing_fk_for_column(conn, "transaction", "flow_id")

        with op.batch_alter_table("transaction", schema=None) as batch_op:
            if _TRANSACTION_INDEX not in existing_indexes:
                batch_op.create_index(_TRANSACTION_INDEX, ["flow_id"], unique=False)
            if existing_fk is None:
                batch_op.create_foreign_key(
                    _TRANSACTION_FK,
                    "flow",
                    ["flow_id"],
                    ["id"],
                )

    # ------------------------ message.flow_id ------------------------
    if migration.table_exists("message", conn):
        existing_indexes = _existing_index_names(conn, "message")
        existing_fk = _existing_fk_for_column(conn, "message", "flow_id")

        with op.batch_alter_table("message", schema=None) as batch_op:
            if _MESSAGE_INDEX not in existing_indexes:
                batch_op.create_index(_MESSAGE_INDEX, ["flow_id"], unique=False)
            if existing_fk is None:
                batch_op.create_foreign_key(
                    _MESSAGE_FK,
                    "flow",
                    ["flow_id"],
                    ["id"],
                )


def downgrade() -> None:
    conn = op.get_bind()

    # ------------------------ message.flow_id ------------------------
    if migration.table_exists("message", conn):
        existing_indexes = _existing_index_names(conn, "message")
        existing_fk = _existing_fk_for_column(conn, "message", "flow_id")

        with op.batch_alter_table("message", schema=None) as batch_op:
            if existing_fk == _MESSAGE_FK:
                batch_op.drop_constraint(_MESSAGE_FK, type_="foreignkey")
            if _MESSAGE_INDEX in existing_indexes:
                batch_op.drop_index(_MESSAGE_INDEX)

    # ---------------------- transaction.flow_id ----------------------
    if migration.table_exists("transaction", conn):
        existing_indexes = _existing_index_names(conn, "transaction")
        existing_fk = _existing_fk_for_column(conn, "transaction", "flow_id")

        with op.batch_alter_table("transaction", schema=None) as batch_op:
            if existing_fk == _TRANSACTION_FK:
                batch_op.drop_constraint(_TRANSACTION_FK, type_="foreignkey")
            if _TRANSACTION_INDEX in existing_indexes:
                batch_op.drop_index(_TRANSACTION_INDEX)
