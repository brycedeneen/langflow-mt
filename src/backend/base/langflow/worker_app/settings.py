from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from lfx.log.logger import logger

from langflow.services.settings.base import Settings
from langflow.worker_app.audit_cleanup import audit_cleanup
from langflow.worker_app.execute import WORKER_ID, execute_run
from langflow.worker_app.reaper import reap_lost_runs
from langflow.worker_app.retention import retention_sweep
from langflow.worker_app.webhook import deliver_webhook

_settings = Settings(_env_file=None)


async def _on_startup(ctx) -> None:
    from langflow.services.deps import get_db_service, get_settings_service, get_storage_service
    from langflow.services.utils import initialize_services

    await initialize_services()

    settings_service = get_settings_service()
    db_service = get_db_service()

    ctx["settings"] = settings_service.settings
    ctx["db_sessionmaker"] = db_service.async_session_maker
    ctx["storage"] = get_storage_service()
    # arq's worker already sets ctx['redis'] to the ArqRedis pool; reuse it for enqueueing.
    ctx["arq"] = ctx["redis"]
    logger.info(
        f"Langflow worker started: worker_id={WORKER_ID} "
        f"queue={WorkerSettings.queue_name} max_jobs={WorkerSettings.max_jobs}"
    )


async def _on_shutdown(ctx) -> None:
    from langflow.services.runs.deps import close_arq_pool

    logger.info(f"Langflow worker shutting down: worker_id={WORKER_ID}")
    await close_arq_pool()


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    functions = [execute_run, deliver_webhook]
    cron_jobs = [
        cron(reap_lost_runs, name="reap_lost_runs", second={0, 30}),
        cron(retention_sweep, name="retention_sweep", minute=0),
        cron(audit_cleanup, name="audit_cleanup", hour=3, minute=0),  # daily 03:00 UTC
    ]
    queue_name = _settings.arq_default_queue
    max_jobs = _settings.worker_concurrency
    on_startup = _on_startup
    on_shutdown = _on_shutdown
