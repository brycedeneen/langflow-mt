"""catch-up: bigint widen, enum-to-string, index drift

Revision ID: 67630b517fbb
Revises: 716496e07616
Create Date: 2026-04-25

A handful of model edits between the metering / cost / audit_log migrations
and the present day were never accompanied by alembic migrations:

  * `org_usage_daily.{runs,run_seconds,tokens,cost_cents}`,
    `flow_usage_daily.{runs,run_seconds,tokens,cost_cents}`, and
    `org_usage_threshold.threshold_value` widened from INTEGER → BigInteger.
  * `admin_notification.{category,severity,audience}`, `alert_rule.rule_type`,
    and `org_usage_threshold.{metric,period}` switched from Postgres ENUM types
    to plain VARCHAR columns (Python-side `Enum` classes still validate at the
    SQLModel layer).
  * `admin_notification.body_md` widened VARCHAR → TEXT.
  * Several composite indexes added for hot lookup paths
    (`ix_admin_notification_audience_read_created`,
    `ix_alert_rule_org_active`, `ix_alert_rule_org_flow_active`,
    `ix_flow_usage_daily_org_date`, `ix_org_usage_threshold_org_active`).
  * `ix_org_usage_threshold_org_id` replaced by the new `_org_active` index.

Fresh DBs built via `SQLModel.create_all` already match the current models, so
each operation is guarded by an inspector check and is a no-op when the schema
already matches. After the type swaps the now-orphaned Postgres ENUM types are
dropped via `DROP TYPE IF EXISTS`.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "67630b517fbb"
down_revision: str | None = "716496e07616"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_INT_WIDENS: tuple[tuple[str, str], ...] = (
    ("flow_usage_daily", "runs"),
    ("flow_usage_daily", "run_seconds"),
    ("flow_usage_daily", "tokens"),
    ("flow_usage_daily", "cost_cents"),
    ("org_usage_daily", "runs"),
    ("org_usage_daily", "run_seconds"),
    ("org_usage_daily", "tokens"),
    ("org_usage_daily", "cost_cents"),
    ("org_usage_threshold", "threshold_value"),
)


_ENUM_TO_STRING: tuple[tuple[str, str, int, str], ...] = (
    # (table, column, varchar_length, orphaned_postgres_enum_type_name)
    ("admin_notification", "category", 32, "notificationcategory"),
    ("admin_notification", "severity", 16, "notificationseverity"),
    ("admin_notification", "audience", 32, "notificationaudience"),
    ("alert_rule", "rule_type", 32, "alertruletype"),
    ("org_usage_threshold", "metric", 32, "usagemetric"),
    ("org_usage_threshold", "period", 16, "usageperiod"),
)


_INDEX_ADDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "admin_notification",
        "ix_admin_notification_audience_read_created",
        ("audience", "read_at", "created_at"),
    ),
    ("alert_rule", "ix_alert_rule_org_active", ("org_id", "is_active")),
    (
        "alert_rule",
        "ix_alert_rule_org_flow_active",
        ("org_id", "flow_id", "is_active"),
    ),
    ("flow_usage_daily", "ix_flow_usage_daily_org_date", ("org_id", "date")),
    (
        "org_usage_threshold",
        "ix_org_usage_threshold_org_active",
        ("org_id", "is_active"),
    ),
)


_INDEX_DROPS: tuple[tuple[str, str], ...] = (
    ("org_usage_threshold", "ix_org_usage_threshold_org_id"),
)


def _column_python_type(inspector, table: str, column: str):
    for col in inspector.get_columns(table):
        if col["name"] == column:
            return col["type"]
    return None


def _has_index(inspector, table: str, name: str) -> bool:
    return any(idx["name"] == name for idx in inspector.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    inspector = sa.inspect(bind)

    # --- 1. INTEGER → BigInteger widenings --------------------------------
    for table, column in _INT_WIDENS:
        col_type = _column_python_type(inspector, table, column)
        if col_type is None:
            continue
        # Already BigInteger? skip.
        if isinstance(col_type, sa.BigInteger):
            continue
        # Some dialects report Integer subclasses; check the explicit class.
        if type(col_type).__name__ == "BIGINT":
            continue
        op.alter_column(
            table,
            column,
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=False,
        )

    # --- 2. ENUM → String column-type swaps (+ drop orphan enum types) ----
    for table, column, length, enum_name in _ENUM_TO_STRING:
        col_type = _column_python_type(inspector, table, column)
        if col_type is None:
            continue
        # Already a string-ish type? skip.
        if isinstance(col_type, sa.String) and not isinstance(col_type, sa.Enum):
            continue
        kwargs: dict = {
            "existing_nullable": False,
            "type_": sa.String(length=length),
        }
        if is_postgres:
            kwargs["postgresql_using"] = f"{column}::text"
        op.alter_column(table, column, **kwargs)
        if is_postgres:
            op.execute(sa.text(f'DROP TYPE IF EXISTS "{enum_name}"'))

    # --- 3. admin_notification.body_md VARCHAR → TEXT ---------------------
    body_md_type = _column_python_type(inspector, "admin_notification", "body_md")
    if body_md_type is not None and not isinstance(body_md_type, sa.Text):
        op.alter_column(
            "admin_notification",
            "body_md",
            existing_type=sa.VARCHAR(),
            type_=sa.Text(),
            existing_nullable=False,
        )

    # --- 4. Index drops ---------------------------------------------------
    # Re-inspect so we see post-2 column-type changes if the dialect cached.
    inspector = sa.inspect(bind)
    for table, name in _INDEX_DROPS:
        if _has_index(inspector, table, name):
            op.drop_index(name, table_name=table)

    # --- 5. Index adds ----------------------------------------------------
    for table, name, columns in _INDEX_ADDS:
        if not _has_index(inspector, table, name):
            op.create_index(name, table, list(columns), unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    inspector = sa.inspect(bind)

    # Drop the indexes we added.
    for table, name, _columns in _INDEX_ADDS:
        if _has_index(inspector, table, name):
            op.drop_index(name, table_name=table)

    # Recreate the index we dropped.
    for table, name in _INDEX_DROPS:
        if not _has_index(inspector, table, name):
            op.create_index(name, table, ["org_id"], unique=False)

    # body_md TEXT → VARCHAR
    op.alter_column(
        "admin_notification",
        "body_md",
        existing_type=sa.Text(),
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )

    # String → ENUM. We have to recreate the ENUM types on Postgres first.
    if is_postgres:
        enum_value_map = {
            "notificationcategory": ("USAGE_THRESHOLD", "ALERT_RULE", "SYSTEM"),
            "notificationseverity": ("INFO", "WARNING", "CRITICAL"),
            "notificationaudience": ("SUPER_ADMIN",),
            "alertruletype": ("CONSECUTIVE_FAILURES", "ERROR_RATE", "SLA_DURATION"),
            "usagemetric": ("RUNS", "RUN_SECONDS", "TOKENS"),
            "usageperiod": ("DAILY", "MONTHLY"),
        }
        for enum_name, values in enum_value_map.items():
            values_sql = ", ".join(f"'{v}'" for v in values)
            op.execute(
                sa.text(
                    f'CREATE TYPE "{enum_name}" AS ENUM ({values_sql})'
                )
            )

    for table, column, _length, enum_name in _ENUM_TO_STRING:
        kwargs: dict = {"existing_nullable": False}
        if is_postgres:
            kwargs["postgresql_using"] = f'{column}::"{enum_name}"'
            kwargs["type_"] = sa.dialects.postgresql.ENUM(name=enum_name, create_type=False)
        else:
            # SQLite never had native ENUMs; just leave as String.
            continue
        op.alter_column(table, column, **kwargs)

    # BigInteger → INTEGER
    for table, column in _INT_WIDENS:
        op.alter_column(
            table,
            column,
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=False,
        )
