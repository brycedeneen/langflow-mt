from __future__ import annotations

import asyncio

import pytest
from taskiq_redis import ListQueueBroker

from langflow.worker_app.delayed_enqueue import drain_due_kicks, schedule_delayed_kick


@pytest.mark.asyncio
async def test_delayed_kick_enqueues_after_delay(redis_service):
    broker = ListQueueBroker(url=redis_service.url, queue_name="test:delay")
    await broker.startup()

    @broker.task
    async def _noop(payload: str) -> None:
        return None

    await schedule_delayed_kick(
        redis=redis_service.client,
        task_name=_noop.task_name,
        queue_name="test:delay",
        args=["hello"],
        delay_s=0.5,
    )
    drained = await drain_due_kicks(
        redis=redis_service.client,
        brokers_by_queue={"test:delay": broker},
    )
    assert drained == 0
    await asyncio.sleep(0.6)
    drained = await drain_due_kicks(
        redis=redis_service.client,
        brokers_by_queue={"test:delay": broker},
    )
    assert drained == 1
    await broker.shutdown()
