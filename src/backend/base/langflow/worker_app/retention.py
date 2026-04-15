from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete

from langflow.services.database.models.flow_run.model import FlowRun


async def retention_sweep(ctx) -> None:
    settings = ctx["settings"]
    session_factory = ctx["db_sessionmaker"]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.run_retention_hours)
    async with session_factory() as session:
        stmt = delete(FlowRun).where(FlowRun.finished_at.is_not(None), FlowRun.finished_at < cutoff)
        await session.exec(stmt)
        await session.commit()
    # flow_run_log rows cascade via FK ondelete=CASCADE.
