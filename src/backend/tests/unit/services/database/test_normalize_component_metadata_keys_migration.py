"""Migration: normalize component_metadata.component_name to canonical registry keys.

Verifies the alembic upgrade from d6b4990402d7 -> 4f2a9b1c7e83:
- A class-name-keyed row (e.g. ``WebhookComponent``) is renamed to its registry key (``Webhook``).
- A display-name-keyed row is renamed to its registry key.
- An unresolvable row is deleted outright.
- When two rows resolve to the same canonical key, the admin-curated row wins
  and the duplicate is dropped.
"""
from __future__ import annotations

import pathlib
import uuid
from datetime import datetime, timezone

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

LANGFLOW_ROOT = pathlib.Path(__file__).resolve().parents[4] / "base" / "langflow"
ALEMBIC_INI = LANGFLOW_ROOT / "alembic.ini"
ALEMBIC_DIR = LANGFLOW_ROOT / "alembic"

PRE_REVISION = "d6b4990402d7"
TARGET_REVISION = "4f2a9b1c7e83"


@pytest.fixture
def alembic_cfg(tmp_path, monkeypatch):
    db_file = tmp_path / "mig.db"
    sync_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", sync_url)

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    return cfg, sync_url


def _insert_row(conn, *, name: str, summary: str | None, updated_by: uuid.UUID | None) -> uuid.UUID:
    row_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO component_metadata "
            "(id, component_name, agent_summary, agent_usage_notes, updated_by, updated_at) "
            "VALUES (:id, :name, :summary, NULL, :updated_by, :updated_at)"
        ),
        {
            "id": str(row_id),
            "name": name,
            "summary": summary,
            "updated_by": str(updated_by) if updated_by else None,
            "updated_at": datetime.now(timezone.utc),
        },
    )
    return row_id


def _names(conn) -> dict[str, dict]:
    rows = conn.execute(
        text("SELECT component_name, agent_summary, updated_by FROM component_metadata")
    ).all()
    return {
        r.component_name: {"agent_summary": r.agent_summary, "updated_by": r.updated_by}
        for r in rows
    }


def test_migration_normalises_class_name_and_display_name_aliases(alembic_cfg):
    cfg, db_url = alembic_cfg

    # Stand up the schema at the previous revision.
    command.upgrade(cfg, PRE_REVISION)
    engine = create_engine(db_url)

    admin_id = uuid.uuid4()
    with engine.begin() as conn:
        # 1. Class-name-keyed row -> should rename to registry key.
        _insert_row(conn, name="WebhookComponent", summary="from class name", updated_by=None)
        # 2. Display-name-keyed row -> should rename to registry key.
        _insert_row(conn, name="ADP API Request", summary="from display name", updated_by=None)
        # 3. Truly-stale row -> should be deleted.
        _insert_row(conn, name="LongGoneToolComponent", summary="dead", updated_by=admin_id)

    # Run our migration.
    command.upgrade(cfg, TARGET_REVISION)

    with engine.begin() as conn:
        rows = _names(conn)

    # Class-name renamed to registry key.
    assert "Webhook" in rows
    assert rows["Webhook"]["agent_summary"] == "from class name"
    assert "WebhookComponent" not in rows

    # Display-name renamed to registry key.
    assert "ADPAPIRequest" in rows
    assert rows["ADPAPIRequest"]["agent_summary"] == "from display name"
    assert "ADP API Request" not in rows

    # Stale row deleted.
    assert "LongGoneToolComponent" not in rows


def test_migration_dedupes_alias_and_canonical_admin_curated_wins(alembic_cfg):
    cfg, db_url = alembic_cfg

    command.upgrade(cfg, PRE_REVISION)
    engine = create_engine(db_url)

    admin_id = uuid.uuid4()
    with engine.begin() as conn:
        # Seeded class-name row (no admin) — should lose to admin-curated canonical row.
        _insert_row(conn, name="WebhookComponent", summary="seeded", updated_by=None)
        # Admin-curated canonical row — should survive.
        _insert_row(conn, name="Webhook", summary="admin-curated", updated_by=admin_id)

    command.upgrade(cfg, TARGET_REVISION)

    with engine.begin() as conn:
        rows = _names(conn)

    assert "Webhook" in rows
    assert rows["Webhook"]["agent_summary"] == "admin-curated"
    assert "WebhookComponent" not in rows


def test_migration_dedupes_when_only_alias_row_is_admin_curated(alembic_cfg):
    cfg, db_url = alembic_cfg

    command.upgrade(cfg, PRE_REVISION)
    engine = create_engine(db_url)

    admin_id = uuid.uuid4()
    with engine.begin() as conn:
        # Class-name row was admin-edited; canonical row is just seeded.
        _insert_row(conn, name="WebhookComponent", summary="admin-curated", updated_by=admin_id)
        _insert_row(conn, name="Webhook", summary="seeded", updated_by=None)

    command.upgrade(cfg, TARGET_REVISION)

    with engine.begin() as conn:
        rows = _names(conn)

    # Canonical row exists, but seeded loses to admin-curated alias row,
    # which is then renamed onto the canonical key.
    assert "Webhook" in rows
    assert rows["Webhook"]["agent_summary"] == "admin-curated"
    assert "WebhookComponent" not in rows
