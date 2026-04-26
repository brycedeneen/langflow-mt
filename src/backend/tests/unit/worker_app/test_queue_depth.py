from __future__ import annotations
import pytest
from unittest.mock import AsyncMock

pytestmark = pytest.mark.asyncio


async def test_queue_depth_polls_each_queue_and_updates_gauge():
    from langflow.worker_app import queue_depth as qd
    from langflow.services.runs.metrics import QUEUE_DEPTH

    sizes = {
        "runs:high": 3,
        "runs:default": 7,
        "runs:low": 0,
        "webhooks": 11,
    }
    fake_redis = AsyncMock()
    fake_redis.llen = AsyncMock(side_effect=lambda name: sizes[name])

    await qd._poll_once(fake_redis)

    assert fake_redis.llen.call_count == 4

    def gauge_value(queue: str) -> float:
        for metric in QUEUE_DEPTH.collect():
            for sample in metric.samples:
                if sample.labels.get("queue") == queue:
                    return sample.value
        return -1.0

    assert gauge_value("runs:high") == 3
    assert gauge_value("runs:default") == 7
    assert gauge_value("runs:low") == 0
    assert gauge_value("webhooks") == 11


async def test_queue_depth_swallows_redis_error():
    from langflow.worker_app import queue_depth as qd

    fake_redis = AsyncMock()
    fake_redis.llen = AsyncMock(side_effect=ConnectionError("redis down"))
    # Should not raise; polling failures are recoverable.
    await qd._poll_once(fake_redis)
