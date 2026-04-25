"""template agent metadata + based_on_template_id

Revision ID: 716496e07616
Revises: e1f42ac1d7a9
Create Date: 2026-04-25
"""
from __future__ import annotations

import json
import logging
import pathlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

# revision identifiers
revision: str = "716496e07616"
down_revision: str | None = "e1f42ac1d7a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STARTER_FIXTURE_DIR = (
    pathlib.Path(__file__).resolve().parents[2]
    / "initial_setup"
    / "starter_projects"
)


def _backfill_template_agent_fields(conn) -> None:
    """For each *.metadata.json sibling fixture, populate the matching
    Template row's agent_summary / agent_usage_notes (only when the row
    exists and the target column is currently NULL)."""
    if not STARTER_FIXTURE_DIR.is_dir():
        return
    for path in sorted(STARTER_FIXTURE_DIR.glob("*.metadata.json")):
        template_name = path.name[: -len(".metadata.json")]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            logger.warning("Skipping malformed metadata fixture %s: %s", path.name, err)
            continue
        agent_summary = payload.get("agent_summary")
        agent_usage_notes = payload.get("agent_usage_notes")
        if agent_summary is None and agent_usage_notes is None:
            continue
        conn.execute(
            sa.text(
                "UPDATE template SET "
                "agent_summary = COALESCE(agent_summary, :s), "
                "agent_usage_notes = COALESCE(agent_usage_notes, :n) "
                "WHERE LOWER(name) = LOWER(:name)"
            ),
            {"s": agent_summary, "n": agent_usage_notes, "name": template_name},
        )


def upgrade() -> None:
    # 1. Add agent fields to template
    op.add_column("template", sa.Column("agent_summary", sa.Text(), nullable=True))
    op.add_column("template", sa.Column("agent_usage_notes", sa.Text(), nullable=True))

    # 2. Backfill from *.metadata.json fixtures
    _backfill_template_agent_fields(op.get_bind())

    # 3. Add the new flow.based_on_template_id column + FK, and drop the old
    #    based_on_template_flow_id column — both inside a single batch so that
    #    SQLite can handle the FK DDL via its copy-and-move strategy.
    with op.batch_alter_table("flow") as batch:
        batch.add_column(
            sa.Column(
                "based_on_template_id",
                sa.Uuid(),
                sa.ForeignKey("template.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch.drop_column("based_on_template_flow_id")

    # 4. Drop the orphaned template_metadata table
    op.drop_table("template_metadata")


def downgrade() -> None:
    # Recreate template_metadata (empty — no data restore).
    # Use table-level UniqueConstraint rather than column-level unique=True to
    # stay compatible with SQLite's batch-mode constraint handling.
    op.create_table(
        "template_metadata",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("flow_id", sa.Uuid(),
                  sa.ForeignKey("flow.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("agent_usage_notes", sa.Text(), nullable=True),
        sa.Column("agent_summary", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Uuid(),
                  sa.ForeignKey("user.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("flow_id", name="uq_template_metadata_flow_id"),
    )
    op.create_index("ix_template_metadata_flow_id", "template_metadata", ["flow_id"])

    # Recreate flow.based_on_template_flow_id (FK back to flow.id) and drop
    # based_on_template_id — batch mode handles FK DDL on SQLite.
    with op.batch_alter_table("flow") as batch:
        batch.add_column(
            sa.Column(
                "based_on_template_flow_id",
                sa.Uuid(),
                sa.ForeignKey("flow.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch.drop_column("based_on_template_id")

    op.drop_column("template", "agent_usage_notes")
    op.drop_column("template", "agent_summary")
