from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from langflow.services.settings.base import Settings

_settings = Settings(_env_file=None)


async def execute_run(ctx, run_id: str) -> None:
    # Real body: Task 17
    raise NotImplementedError


async def deliver_webhook(ctx, run_id: str, event: str, attempt: int = 0) -> None:
    # Real body: Task 25
    raise NotImplementedError


async def reap_lost_runs(ctx) -> None:
    # Real body: Task 22
    raise NotImplementedError


async def retention_sweep(ctx) -> None:
    # Real body: Task 23
    raise NotImplementedError


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    functions = [execute_run, deliver_webhook]
    cron_jobs = [
        cron(reap_lost_runs, name="reap_lost_runs", second={0, 30}),
        cron(retention_sweep, name="retention_sweep", minute=0),
    ]
    queue_name = _settings.arq_default_queue
    max_jobs = _settings.worker_concurrency
