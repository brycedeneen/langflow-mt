from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete
from taskiq import TaskiqDepends

from langflow.services.database.models.flow_run.model import FlowRun
from langflow.worker_app.brokers import broker_default
from langflow.worker_app.deps import get_db_sessionmaker, get_settings


@broker_default.task(
    task_name="retention_sweep",
    schedule=[{"cron": "0 * * * *"}],  # every hour at :00
)
async def retention_sweep(
    *,
    sessionmaker=TaskiqDepends(get_db_sessionmaker),
    settings=TaskiqDepends(get_settings),
) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.run_retention_hours)
    async with sessionmaker() as session:
        stmt = delete(FlowRun).where(
            FlowRun.finished_at.is_not(None),
            FlowRun.finished_at < cutoff,
        )
        await session.exec(stmt)
        await session.commit()
    # flow_run_log rows cascade via FK ondelete=CASCADE.
