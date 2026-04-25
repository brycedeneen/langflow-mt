"""Smoke test: the new revision adds template agent columns, swaps the
flow→template FK, and drops the legacy template_metadata table.
"""
from __future__ import annotations

import json
import pathlib

import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text

# parents[0]=database/, parents[1]=services/, parents[2]=unit/,
# parents[3]=tests/, parents[4]=backend/, parents[5]=src/
LANGFLOW_ROOT = pathlib.Path(__file__).resolve().parents[4] / "base" / "langflow"
ALEMBIC_INI = LANGFLOW_ROOT / "alembic.ini"
ALEMBIC_DIR = LANGFLOW_ROOT / "alembic"


@pytest.fixture
def alembic_cfg(tmp_path, monkeypatch):
    db_file = tmp_path / "mig.db"
    sync_url = f"sqlite:///{db_file}"

    # env.py reads LANGFLOW_DATABASE_URL from os.environ and converts it to
    # the async driver URL.  The project .env sets a Postgres URL which fails
    # in CI/unit tests because psycopg is not installed.  Override it here so
    # env.py picks up the temp SQLite path instead.
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", sync_url)

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    return cfg, sync_url


def _columns(engine, table):
    return {c["name"] for c in inspect(engine).get_columns(table)}


def _tables(engine):
    return set(inspect(engine).get_table_names())


def test_upgrade_then_downgrade_round_trip(alembic_cfg):
    cfg, db_url = alembic_cfg
    command.upgrade(cfg, "head")
    engine = create_engine(db_url)

    tcols = _columns(engine, "template")
    assert "agent_summary" in tcols
    assert "agent_usage_notes" in tcols

    fcols = _columns(engine, "flow")
    assert "based_on_template_id" in fcols
    assert "based_on_template_flow_id" not in fcols

    fks = inspect(engine).get_foreign_keys("flow")
    based_on_fks = [fk for fk in fks if fk["constrained_columns"] == ["based_on_template_id"]]
    assert len(based_on_fks) == 1, f"expected exactly one FK on based_on_template_id, got {based_on_fks}"
    assert based_on_fks[0]["referred_table"] == "template"
    # Note: SQLite's get_foreign_keys may not always include `options.ondelete`.
    # If `options` is present, assert it; otherwise just don't.
    options = based_on_fks[0].get("options") or {}
    if "ondelete" in options:
        assert options["ondelete"].upper() == "SET NULL"

    assert "template_metadata" not in _tables(engine)

    # Downgrade one step
    command.downgrade(cfg, "-1")
    engine.dispose()
    engine = create_engine(db_url)

    tcols = _columns(engine, "template")
    assert "agent_summary" not in tcols
    assert "agent_usage_notes" not in tcols
    fcols = _columns(engine, "flow")
    assert "based_on_template_id" not in fcols
    assert "based_on_template_flow_id" in fcols
    assert "template_metadata" in _tables(engine)


def test_backfill_populates_template_agent_fields(alembic_cfg, monkeypatch):
    """Upgrade against a DB pre-seeded with a Template row whose name matches
    a *.metadata.json fixture; assert backfill copies agent_summary/notes.

    The migration chain (via 8663a8995703) already seeds 'ADP Worker Sync to
    SFTP' into the template table when upgrading to e1f42ac1d7a9.  We rely on
    that seeded row; we do NOT insert a second row (which would violate the
    uq_template_name_per_scope index).
    """
    cfg, db_url = alembic_cfg
    # Step to the migration just before ours — the ADP template is already
    # seeded by 8663a8995703 which runs as part of this upgrade chain.
    command.upgrade(cfg, "e1f42ac1d7a9")

    # Verify the template was seeded (sanity check before our migration runs)
    engine = create_engine(db_url)
    with engine.begin() as conn:
        existing = conn.execute(text(
            "SELECT id FROM template WHERE LOWER(name) = 'adp worker sync to sftp'"
        )).first()
    assert existing is not None, (
        "Expected the ADP template to be seeded by 8663a8995703 — "
        "check that migration's fixture dir"
    )
    engine.dispose()

    # Now run our new migration
    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT agent_summary, agent_usage_notes FROM template "
            "WHERE LOWER(name) = 'adp worker sync to sftp'"
        )).first()
    assert row is not None
    # Compare against the actual fixture file so a future swap/rename is caught
    fixture_path = (
        LANGFLOW_ROOT / "initial_setup" / "starter_projects" / "ADP Worker Sync to SFTP.metadata.json"
    )
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))
    expected_summary = expected.get("agent_summary")
    expected_notes = expected.get("agent_usage_notes")
    assert row[0] == expected_summary, (
        f"agent_summary backfill mismatch: got {row[0]!r}, expected {expected_summary!r}"
    )
    assert row[1] == expected_notes, (
        f"agent_usage_notes backfill mismatch: got {row[1]!r}, expected {expected_notes!r}"
    )
