# src/backend/base/langflow/worker_app/audit_cleanup.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from lfx.log.logger import logger
from sqlalchemy import delete
from taskiq import TaskiqDepends

from langflow.services.database.models.audit_log import AuditLog
from langflow.worker_app.brokers import broker_default
from langflow.worker_app.deps import get_db_sessionmaker, get_settings


@broker_default.task(
    task_name="audit_cleanup",
    schedule=[{"cron": "0 3 * * *"}],  # daily at 03:00 UTC
)
async def audit_cleanup(
    *,
    sessionmaker=TaskiqDepends(get_db_sessionmaker),
    settings=TaskiqDepends(get_settings),
) -> None:
    """Delete audit_log rows older than settings.audit_log_retention_days.

    Retention of 0 disables deletion.
    """
    retention = int(getattr(settings, "audit_log_retention_days", 90))
    if retention <= 0:
        logger.info("audit_cleanup: retention disabled (audit_log_retention_days=0)")
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention)

    async with sessionmaker() as session:
        stmt = delete(AuditLog).where(AuditLog.created_at < cutoff)
        result = await session.exec(stmt)
        await session.commit()

    count = result.rowcount if hasattr(result, "rowcount") else "?"
    logger.info(f"audit_cleanup: deleted rows older than {cutoff.isoformat()} (count={count})")
