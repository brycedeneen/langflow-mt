from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlmodel import select
from redis.asyncio import Redis
from taskiq import TaskiqDepends

from langflow.services.database.models.flow_run.model import FlowRun, RunStatus
from langflow.services.runs.concurrency import OrgConcurrency
from langflow.worker_app.brokers import broker_default, broker_webhooks
from langflow.worker_app.deps import get_db_sessionmaker, get_redis

STALE_AFTER_SECONDS = 60


@broker_default.task(
    task_name="reap_lost_runs",
    schedule=[{"cron": "* * * * *"}],  # every minute
)
async def reap_lost_runs(
    *,
    sessionmaker=TaskiqDepends(get_db_sessionmaker),
    redis: Redis = TaskiqDepends(get_redis),
) -> None:
    from langflow.worker_app.webhook import deliver_webhook  # avoid circular

    concurrency = OrgConcurrency(redis)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=STALE_AFTER_SECONDS)

    reaped_rows = []
    async with sessionmaker() as session:
        stmt = select(FlowRun).where(
            FlowRun.status == RunStatus.RUNNING,
            FlowRun.heartbeat_at < cutoff,
        )
        rows = (await session.exec(stmt)).all()
        for row in rows:
            row.status = RunStatus.FAILED
            row.finished_at = datetime.now(timezone.utc)
            row.error = {"type": "worker_lost", "message": "no heartbeat within 60s"}
            await concurrency.release(row.organization_id)
            reaped_rows.append(row.id)
        await session.commit()

    for run_id in reaped_rows:
        await deliver_webhook.kicker().with_broker(broker_webhooks).kiq(
            str(run_id), "run.failed"
        )
