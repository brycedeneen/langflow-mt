"""Round-trip test for the pro_service_quotes migration.

Spins up a fresh SQLite DB, runs ``alembic upgrade head``, asserts the new
schema/columns/seed row are present, downgrades one revision, and upgrades
again. Mirrors the SQLite-based pattern used by
``src/backend/tests/unit/alembic/test_migration_execution.py``.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


@pytest.fixture(autouse=True)
def _isolate_database_url(monkeypatch):
    """Prevent env.py from overriding the test's sqlite URL.

    ``src/backend/base/langflow/alembic/env.py`` reads ``LANGFLOW_DATABASE_URL``
    from the environment and overwrites the URL set on the alembic Config.
    """
    monkeypatch.delenv("LANGFLOW_DATABASE_URL", raising=False)


def _alembic_cfg_for(db_path: str) -> Config:
    cfg = Config()
    workspace_root = Path(__file__).resolve().parents[5]
    script_location = workspace_root / "src/backend/base/langflow/alembic"
    if not script_location.exists():
        pytest.fail(f"Alembic script location not found at {script_location}")
    cfg.set_main_option("script_location", str(script_location))
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    return cfg


def _temp_db_path() -> str:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        return tmp.name


@pytest.mark.integration
def test_pro_service_quotes_migration_round_trip():
    """Upgrade head, assert schema, downgrade -1, upgrade again."""
    db_path = _temp_db_path()
    try:
        cfg = _alembic_cfg_for(db_path)
        command.upgrade(cfg, "head")

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            insp = inspect(engine)

            # New tables exist
            tables = set(insp.get_table_names())
            assert "pro_service_quote" in tables
            assert "professional_services_settings" in tables

            # Flow gained ps_request_active
            flow_cols = {c["name"] for c in insp.get_columns("flow")}
            assert "ps_request_active" in flow_cols

            # Organization gained billable rate columns
            org_cols = {c["name"] for c in insp.get_columns("organization")}
            assert "billable_rate_low_per_hour" in org_cols
            assert "billable_rate_high_per_hour" in org_cols

            # component_metadata gained integration minutes columns
            cm_cols = {c["name"] for c in insp.get_columns("component_metadata")}
            assert "integration_minutes_low" in cm_cols
            assert "integration_minutes_high" in cm_cols

            # admin_notification gained audience_user_id
            an_cols = {c["name"] for c in insp.get_columns("admin_notification")}
            assert "audience_user_id" in an_cols

            # Singleton row seeded
            with engine.connect() as conn:
                row = conn.exec_driver_sql(
                    "SELECT default_hourly_rate_low, default_hourly_rate_high "
                    "FROM professional_services_settings WHERE id = 1"
                ).first()
                assert row is not None
                assert float(row[0]) == 200.00
                assert float(row[1]) == 200.00
        finally:
            engine.dispose()

        # Round-trip: down one rev, then back up to head.
        command.downgrade(cfg, "-1")
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            insp = inspect(engine)
            tables = set(insp.get_table_names())
            assert "pro_service_quote" not in tables
            assert "professional_services_settings" not in tables
        finally:
            engine.dispose()

        command.upgrade(cfg, "head")
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            insp = inspect(engine)
            tables = set(insp.get_table_names())
            assert "pro_service_quote" in tables
            assert "professional_services_settings" in tables
        finally:
            engine.dispose()
    finally:
        Path(db_path).unlink(missing_ok=True)
