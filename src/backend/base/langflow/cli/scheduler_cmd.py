"""`langflow scheduler` — singleton scheduler process.

Runs cron jobs (via `LabelScheduleSource`) and drains the delayed-enqueue
ZSET every second. Exactly one instance should run per deployment; the
delayed-enqueue Lua claim prevents duplicate dispatch within Redis, but
crash-between-claim-and-kiq still loses kicks if multiple drainers race.
"""
from __future__ import annotations

import asyncio
import os

import typer

from lfx.log.logger import configure


def scheduler_cmd(
    log_level: str = typer.Option(
        "info",
        "--log-level",
        envvar="LANGFLOW_LOG_LEVEL",
        help="Logging level (debug, info, warning, error, critical).",
    ),
):
    """Run the singleton Taskiq scheduler (cron jobs + delayed-enqueue drainer)."""
    os.environ["LANGFLOW_LOG_LEVEL"] = log_level
    configure(log_level=log_level)

    asyncio.run(_run())


async def _run() -> None:
    from redis.asyncio import Redis
    from taskiq import TaskiqScheduler
    from taskiq.cli.scheduler.run import SchedulerLoop
    from taskiq.schedule_sources import LabelScheduleSource

    # Side-effect imports register cron tasks on brokers.
    from langflow.worker_app import (  # noqa: F401
        audit_cleanup,
        execute,
        lifecycle,
        pricing_refresh,
        reaper,
        retention,
        webhook,
    )
    from langflow.worker_app.brokers import (
        ALL_BROKERS,
        broker_default,
        broker_high,
        broker_low,
        broker_webhooks,
    )
    from lfx.log.logger import logger
    from lfx.services.settings.base import Settings

    settings = Settings(_env_file=None)
    for broker in ALL_BROKERS:
        await broker.startup()

    scheduler = TaskiqScheduler(
        broker=broker_default,
        sources=[LabelScheduleSource(broker_default)],
    )
    scheduler.broker.is_scheduler_process = True
    for source in scheduler.sources:
        await source.startup()
    await scheduler.startup()

    redis = Redis.from_url(settings.redis_url)
    brokers_by_queue = {
        "runs:high": broker_high,
        "runs:default": broker_default,
        "runs:low": broker_low,
        "webhooks": broker_webhooks,
    }

    logger.info("scheduler started")
    drain_task = asyncio.create_task(_drain_loop(redis, brokers_by_queue))
    scheduler_loop = SchedulerLoop(scheduler)
    try:
        await scheduler_loop.run()
    except asyncio.CancelledError:
        pass
    finally:
        drain_task.cancel()
        try:
            await drain_task
        except asyncio.CancelledError:
            pass
        for source in scheduler.sources:
            await source.shutdown()
        await scheduler.shutdown()
        for broker in ALL_BROKERS:
            await broker.shutdown()
        await redis.aclose()


async def _drain_loop(redis, brokers_by_queue) -> None:
    from langflow.worker_app.delayed_enqueue import drain_due_kicks
    from lfx.log.logger import logger

    while True:
        try:
            await drain_due_kicks(redis=redis, brokers_by_queue=brokers_by_queue)
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001
            logger.exception("delayed-enqueue drain loop tick failed")
        await asyncio.sleep(1.0)
