"""Drop flow_usage_daily.flow_id foreign key (retain rows on flow delete)

Revision ID: 3ce76c394183
Revises: 74b14a2dee5b
Create Date: 2026-04-28 12:00:00.000000

The original migration ``0acebda9c705`` created ``flow_usage_daily`` with a
``flow_id`` foreign key to ``flow.id`` using ``ondelete="CASCADE"``. On
Postgres, that means deleting a flow auto-drops the daily usage rows — which
silently violates the billing/audit retention semantics already encoded by
the ``cascade_delete_flows`` helper (which deliberately does NOT delete from
``flow_usage_daily``). SQLite doesn't enforce FK cascades by default, so the
divergence only shows up on Postgres.

This migration drops the FK so the column becomes a plain ``UUID`` primary
key column with no referential action. Historical ``flow_id`` values are
preserved forever — exactly what billing/audit wants. ``ON DELETE SET NULL``
isn't an option because ``flow_id`` is part of the composite PK and
``nullable=False``.

For SQLite this is effectively a no-op (FKs aren't enforced anyway, and a
batch ALTER would force a destructive table rebuild for zero behavioral
gain). The model-side FK is also being removed, so autogenerate stays clean.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3ce76c394183"
down_revision: str | None = "74b14a2dee5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _get_flow_id_fk_name(conn) -> str | None:
    """Look up the FK constraint name on ``flow_usage_daily.flow_id``.

    The original migration created the constraint without an explicit name,
    so the actual name depends on the SQLAlchemy naming convention applied
    at DDL-emit time. Inspecting at runtime avoids hard-coding a name that
    could differ between databases.
    """
    inspector = sa.inspect(conn)
    if "flow_usage_daily" not in inspector.get_table_names():
        return None
    for fk in inspector.get_foreign_keys("flow_usage_daily"):
        if "flow_id" in fk.get("constrained_columns", []):
            return fk.get("name")
    return None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    # SQLite doesn't enforce FK cascades by default and doesn't support
    # ALTER TABLE DROP CONSTRAINT. A batch_alter_table rebuild would be
    # destructive overkill for a constraint that's already a no-op on this
    # backend, so skip it. The model-level FK removal keeps autogenerate
    # in sync.
    if dialect == "sqlite":
        return

    fk_name = _get_flow_id_fk_name(conn)
    if fk_name is None:
        # Already dropped (e.g. a Postgres environment that drifted ahead of
        # alembic_version). Nothing to do.
        return

    op.drop_constraint(fk_name, "flow_usage_daily", type_="foreignkey")


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "sqlite":
        return

    # Recreate the FK with the same ondelete behavior the original
    # migration (0acebda9c705) used.
    op.create_foreign_key(
        "fk_flow_usage_daily_flow_id_flow",
        "flow_usage_daily",
        "flow",
        ["flow_id"],
        ["id"],
        ondelete="CASCADE",
    )
