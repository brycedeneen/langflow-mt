from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from langflow.services.settings.base import Settings
from langflow.worker_app.execute import execute_run
from langflow.worker_app.reaper import reap_lost_runs
from langflow.worker_app.retention import retention_sweep
from langflow.worker_app.webhook import deliver_webhook

_settings = Settings(_env_file=None)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    functions = [execute_run, deliver_webhook]
    cron_jobs = [
        cron(reap_lost_runs, name="reap_lost_runs", second={0, 30}),
        cron(retention_sweep, name="retention_sweep", minute=0),
    ]
    queue_name = _settings.arq_default_queue
    max_jobs = _settings.worker_concurrency
