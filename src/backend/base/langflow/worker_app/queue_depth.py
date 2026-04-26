"""Periodic queue-depth poller.

Updates the QUEUE_DEPTH Prometheus gauge from Redis LLEN every minute.
Runs on broker_default only — running it on every broker would multiply
LLEN traffic without adding value.
"""
from __future__ import annotations

from redis.asyncio import Redis
from taskiq import TaskiqDepends

from lfx.log.logger import logger

from langflow.services.runs.metrics import QUEUE_DEPTH
from langflow.worker_app.brokers import broker_default
from langflow.worker_app.deps import get_redis


_QUEUES = ("runs:high", "runs:default", "runs:low", "webhooks")


async def _poll_once(redis: Redis) -> None:
    for q in _QUEUES:
        try:
            depth = await redis.llen(q)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"queue_depth: failed to LLEN {q}: {exc}")
            continue
        QUEUE_DEPTH.labels(queue=q).set(depth)


@broker_default.task(
    task_name="update_queue_depth",
    schedule=[{"cron": "* * * * *"}],  # every minute
)
async def update_queue_depth(
    *,
    redis: Redis = TaskiqDepends(get_redis),
) -> None:
    await _poll_once(redis)
