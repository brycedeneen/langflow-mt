"""move flow name + endpoint_name uniqueness from per-user to per-org

Revision ID: e1f42ac1d7a9
Revises: 1aa93486a636
Create Date: 2026-04-24 12:15:00.000000

Phase 6 follow-up. The per-user unique constraints

    UNIQUE (user_id, name)
    UNIQUE (user_id, endpoint_name)

pre-date the multi-tenant transition. Under org-scoping, two users in the same
org must not both be able to claim the same endpoint_name, and the flow
resolution helpers need deterministic lookups by endpoint_name within an org.
This migration moves both constraints to:

    UNIQUE (organization_id, name)
    UNIQUE (organization_id, endpoint_name)

Any existing collisions (two rows in the same org sharing a name or
endpoint_name) are resolved in-place by appending an incrementing suffix to
all but the earliest-created row, matching the auto-rename style already used
by the /flows API.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e1f42ac1d7a9"
down_revision: Union[str, None] = "1aa93486a636"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rename_collisions(conn, column: str) -> None:
    """Append `-N` to any flow row whose (organization_id, <column>) collides.

    Keeps the earliest-created row under its original value and renames every
    later row. Retries with an incrementing suffix so we never write a value
    that already exists anywhere in the org (both inside the collision group
    and outside).
    """
    conflicts = conn.execute(
        sa.text(
            f"""
            SELECT organization_id, {column}
            FROM flow
            WHERE {column} IS NOT NULL AND organization_id IS NOT NULL
            GROUP BY organization_id, {column}
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    for org_id, value in conflicts:
        # Fetch the colliding rows oldest-first; keep index 0 as-is.
        rows = conn.execute(
            sa.text(
                f"""
                SELECT id FROM flow
                WHERE organization_id = :org_id AND {column} = :value
                ORDER BY created_at, id
                """
            ),
            {"org_id": org_id, "value": value},
        ).fetchall()
        for rank, (flow_id,) in enumerate(rows[1:], start=1):
            n = rank
            while True:
                candidate = f"{value}-{n}"
                exists = conn.execute(
                    sa.text(
                        f"""
                        SELECT 1 FROM flow
                        WHERE organization_id = :org_id AND {column} = :candidate
                        LIMIT 1
                        """
                    ),
                    {"org_id": org_id, "candidate": candidate},
                ).first()
                if exists is None:
                    break
                n += 1
            conn.execute(
                sa.text(f"UPDATE flow SET {column} = :candidate WHERE id = :flow_id"),
                {"candidate": candidate, "flow_id": flow_id},
            )


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Resolve collisions in the destination keyspace before swapping.
    _rename_collisions(conn, "name")
    _rename_collisions(conn, "endpoint_name")

    # 2. Swap both constraints. SQLite doesn't support ALTER TABLE … DROP
    #    CONSTRAINT, so use batch_alter_table for both branches.
    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.drop_constraint("unique_flow_name", type_="unique")
        batch_op.drop_constraint("unique_flow_endpoint_name", type_="unique")
        batch_op.create_unique_constraint(
            "unique_flow_name_per_org", ["organization_id", "name"]
        )
        batch_op.create_unique_constraint(
            "unique_flow_endpoint_name_per_org", ["organization_id", "endpoint_name"]
        )


def downgrade() -> None:
    # Revert to per-user uniqueness. Not symmetric with upgrade — we don't
    # attempt to undo the collision-rename, since the original values may
    # themselves collide per-user only if a single user held two rows with
    # the same name pre-migration (not possible under the old constraint).
    with op.batch_alter_table("flow", schema=None) as batch_op:
        batch_op.drop_constraint("unique_flow_endpoint_name_per_org", type_="unique")
        batch_op.drop_constraint("unique_flow_name_per_org", type_="unique")
        batch_op.create_unique_constraint("unique_flow_name", ["user_id", "name"])
        batch_op.create_unique_constraint(
            "unique_flow_endpoint_name", ["user_id", "endpoint_name"]
        )
