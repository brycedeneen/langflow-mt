# src/backend/base/langflow/worker_app/audit_cleanup.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from lfx.log.logger import logger
from sqlalchemy import delete

from langflow.services.database.models.audit_log import AuditLog


async def audit_cleanup(ctx) -> None:
    """Delete audit_log rows older than settings.audit_log_retention_days.

    Retention of 0 disables deletion.
    """
    settings = ctx["settings"]
    retention = int(getattr(settings, "audit_log_retention_days", 90))
    if retention <= 0:
        logger.info("audit_cleanup: retention disabled (audit_log_retention_days=0)")
        return

    session_factory = ctx["db_sessionmaker"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention)

    async with session_factory() as session:
        stmt = delete(AuditLog).where(AuditLog.created_at < cutoff)
        result = await session.exec(stmt)
        await session.commit()

    count = result.rowcount if hasattr(result, "rowcount") else "?"
    logger.info(f"audit_cleanup: deleted rows older than {cutoff.isoformat()} (count={count})")
