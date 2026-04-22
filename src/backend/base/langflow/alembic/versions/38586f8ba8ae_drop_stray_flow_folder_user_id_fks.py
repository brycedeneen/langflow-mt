"""drop stray flow/folder user_id FKs

Revision ID: 38586f8ba8ae
Revises: 6fd608236310
Create Date: 2026-04-22 15:10:00.000000

On Postgres databases that predate the SQLAlchemy naming convention, the
`user_id` inline FK landed with Postgres's auto-generated name
(e.g. `flow_user_id_fkey`). Revision 6fd608236310 added the canonical
`fk_<table>_user_id_user` FK with ON DELETE SET NULL but only dropped the
first FK it happened to find, leaving the auto-named duplicate in place.
This revision drops any stray FK on `user_id` that isn't the canonical one,
and creates the canonical one if somehow missing.

No-op on SQLite (fresh schemas there don't accumulate the duplicate).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "38586f8ba8ae"
down_revision: Union[str, None] = "6fd608236310"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _canonical_fk(table: str) -> str:
    return f"fk_{table}_user_id_user"


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        return

    inspector = sa.inspect(conn)
    for table in ("flow", "folder"):
        fks_on_user_id = [
            fk for fk in inspector.get_foreign_keys(table)
            if fk.get("constrained_columns") == ["user_id"] and fk.get("name")
        ]
        canonical = _canonical_fk(table)
        for fk in fks_on_user_id:
            if fk["name"] != canonical:
                op.drop_constraint(fk["name"], table, type_="foreignkey")

        # If the canonical FK was somehow never created (migration skipped / manual drop),
        # create it now with the expected SET NULL cascade.
        if not any(fk["name"] == canonical for fk in fks_on_user_id):
            op.create_foreign_key(
                canonical,
                table,
                "user",
                ["user_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    # Non-destructive forward-only cleanup; nothing to reverse.
    pass
