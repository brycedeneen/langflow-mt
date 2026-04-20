"""Ensure span.trace_id and span.parent_span_id foreign keys have ondelete CASCADE

Revision ID: c8a5f32e9b74
Revises: 2998418b3bc5
Create Date: 2026-04-19 16:30:00.000000

Phase: EXPAND

The original migration (3478f0bd6ccb) created span's foreign keys without
ondelete="CASCADE". That blocks deleting a flow whenever any of its traces
still have spans: trace.flow_id cascades from flow, but span.trace_id is
NO ACTION so Postgres refuses to delete the trace row.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration

# revision identifiers, used by Alembic.
revision: str = "c8a5f32e9b74"  # pragma: allowlist secret
down_revision: str | None = "2998418b3bc5"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _get_fk_constraint_name(conn, table_name: str, column_name: str) -> str | None:
    """Find the foreign key constraint name for a given column."""
    inspector = sa.inspect(conn)
    for fk in inspector.get_foreign_keys(table_name):
        if column_name in fk["constrained_columns"]:
            return fk["name"]
    return None


def _recreate_fk_with_cascade(
    table: str,
    column: str,
    referent_table: str,
    referent_column: str,
    new_name: str,
) -> None:
    conn = op.get_bind()
    existing = _get_fk_constraint_name(conn, table, column)
    with op.batch_alter_table(table, schema=None) as batch_op:
        if existing is not None:
            batch_op.drop_constraint(existing, type_="foreignkey")
        batch_op.create_foreign_key(
            new_name,
            referent_table,
            [column],
            [referent_column],
            ondelete="CASCADE",
        )


def _recreate_fk_without_cascade(
    table: str,
    column: str,
    referent_table: str,
    referent_column: str,
) -> None:
    conn = op.get_bind()
    existing = _get_fk_constraint_name(conn, table, column)
    with op.batch_alter_table(table, schema=None) as batch_op:
        if existing is not None:
            batch_op.drop_constraint(existing, type_="foreignkey")
        batch_op.create_foreign_key(
            None,
            referent_table,
            [column],
            [referent_column],
        )


def upgrade() -> None:
    conn = op.get_bind()

    if not migration.table_exists("span", conn):
        return

    _recreate_fk_with_cascade(
        table="span",
        column="trace_id",
        referent_table="trace",
        referent_column="id",
        new_name="fk_span_trace_id_trace",
    )
    _recreate_fk_with_cascade(
        table="span",
        column="parent_span_id",
        referent_table="span",
        referent_column="id",
        new_name="fk_span_parent_span_id_span",
    )


def downgrade() -> None:
    conn = op.get_bind()

    if not migration.table_exists("span", conn):
        return

    _recreate_fk_without_cascade("span", "parent_span_id", "span", "id")
    _recreate_fk_without_cascade("span", "trace_id", "trace", "id")
