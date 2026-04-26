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

    reaped_rows: list[tuple] = []
    async with sessionmaker() as session:
        stmt = select(FlowRun).where(
            FlowRun.status == RunStatus.RUNNING,
            FlowRun.heartbeat_at < cutoff,
        )
        rows = (await session.exec(stmt)).all()
        now = datetime.now(timezone.utc)
        for row in rows:
            # TOCTOU guard: between SELECT and this point a worker may have
            # legitimately transitioned the run to a terminal status. Re-check
            # the in-memory state (refresh from DB) before mutating so we don't
            # overwrite SUCCEEDED/FAILED with a bogus worker_lost.
            await session.refresh(row)
            if row.status != RunStatus.RUNNING or row.heartbeat_at is None:
                continue
            # SQLite returns naive datetimes even when stored as UTC; normalise
            # before comparing against the tz-aware cutoff.
            heartbeat_at = row.heartbeat_at
            if heartbeat_at.tzinfo is None:
                heartbeat_at = heartbeat_at.replace(tzinfo=timezone.utc)
            if heartbeat_at >= cutoff:
                continue
            row.status = RunStatus.FAILED
            row.finished_at = now
            row.error = {"type": "worker_lost", "message": "no heartbeat within 60s"}
            reaped_rows.append((row.id, row.organization_id))
        await session.commit()

    # NOTE: the worker's own `finally` may already have called
    # `OrgConcurrency.release` for this org. `OrgConcurrency.release` is guarded
    # against under-flow (DECR only fires when current > 0), so a duplicate
    # release here is bounded — but it can still under-count if a different run
    # for the same org just acquired. We accept this minor drift for now.
    for run_id, org_id in reaped_rows:
        await concurrency.release(org_id)
        await deliver_webhook.kicker().with_broker(broker_webhooks).kiq(
            str(run_id), "run.failed"
        )
