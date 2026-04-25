from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlmodel import select

from langflow.services.database.models.flow_run.model import FlowRun, RunStatus
from langflow.services.runs.concurrency import OrgConcurrency

STALE_AFTER_SECONDS = 60


async def reap_lost_runs(ctx) -> None:
    session_factory = ctx["db_sessionmaker"]
    redis = ctx["redis"]
    concurrency = OrgConcurrency(redis)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=STALE_AFTER_SECONDS)

    reaped_rows = []
    async with session_factory() as session:
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
        await ctx["arq"].enqueue_job(
            "deliver_webhook", str(run_id), "run.failed",
            _queue_name=ctx["settings"].queue_webhooks,
        )
