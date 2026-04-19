"""Tests for DatabaseService.init_alembic dispatch on Postgres-style first boots.

Background: when langflow first boots against a fresh Postgres DB, the existing
``create_db_and_tables`` step (SQLModel.create_all) creates the full schema
*before* alembic gets a chance to run. The pre-fix init_alembic would then call
``command.upgrade(head)`` from base, which tried to recreate every existing
table and failed silently (errors swallowed by the outer ``initialize_database``
try/except). The DB was left with an empty ``alembic_version`` table and no
future migrations would ever apply.

The fix: when the schema already exists at init time, call
``command.stamp(head)`` instead of ``command.upgrade(head)``. Stamp marks the
DB as fully migrated without re-running migrations against an already-populated
schema. The subsequent ``command.check(alembic_cfg)`` will catch any genuine
schema drift and raise loudly — strictly better than today's silent failure.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from langflow.services.database.service import DatabaseService


def test_init_alembic_stamps_at_head_when_schema_pre_exists():
    """SQLModel.create_all already built the schema → stamp, don't upgrade.

    Upgrading from base would try to CREATE TABLE for every existing table
    and silently fail (errors swallowed by initialize_database's outer
    "already exists" filter), leaving alembic_version empty forever.
    """
    cfg = MagicMock()
    with patch("langflow.services.database.service.command") as mock_cmd:
        DatabaseService.init_alembic(cfg, schema_pre_exists=True)

    mock_cmd.ensure_version.assert_called_once_with(cfg)
    mock_cmd.stamp.assert_called_once_with(cfg, "head")
    mock_cmd.upgrade.assert_not_called()


def test_init_alembic_upgrades_from_base_for_truly_fresh_db():
    """No schema, no alembic_version → run migrations from base to build it."""
    cfg = MagicMock()
    with patch("langflow.services.database.service.command") as mock_cmd:
        DatabaseService.init_alembic(cfg, schema_pre_exists=False)

    mock_cmd.ensure_version.assert_called_once_with(cfg)
    mock_cmd.upgrade.assert_called_once_with(cfg, "head")
    mock_cmd.stamp.assert_not_called()


def test_init_alembic_default_preserves_legacy_upgrade_behavior():
    """Default (no kwarg) → upgrade-from-base. Backward-compatible with
    callers that haven't been updated to pass schema_pre_exists.
    """
    cfg = MagicMock()
    with patch("langflow.services.database.service.command") as mock_cmd:
        DatabaseService.init_alembic(cfg)

    mock_cmd.ensure_version.assert_called_once_with(cfg)
    mock_cmd.upgrade.assert_called_once_with(cfg, "head")
    mock_cmd.stamp.assert_not_called()
