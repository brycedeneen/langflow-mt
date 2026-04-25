"""Redis-ZSET-backed delayed enqueue.

Replaces arq's `_defer_by`. Two functions:

- `schedule_delayed_kick` — write a one-shot enqueue request to a ZSET
  keyed by `delay:<queue>`, with score = unix epoch to fire.
- `drain_due_kicks` — move all due entries into their target brokers via
  `kicker().kiq(...)`. Runs in the scheduler process every ~1s.
"""

from __future__ import annotations

import json
import time
from typing import Any, Mapping

from taskiq import AsyncBroker

DELAY_KEY_PREFIX = "delay"  # Redis ZSET key: delay:<queue_name>


async def schedule_delayed_kick(
    *,
    redis,
    task_name: str,
    queue_name: str,
    args: list[Any],
    delay_s: float,
) -> None:
    """Schedule a one-shot enqueue of `task_name` into `queue_name` after `delay_s`."""
    payload = json.dumps({"task": task_name, "args": list(args)})
    score = time.time() + max(0.0, delay_s)
    await redis.zadd(f"{DELAY_KEY_PREFIX}:{queue_name}", {payload: score})


async def drain_due_kicks(
    *,
    redis,
    brokers_by_queue: Mapping[str, AsyncBroker],
) -> int:
    """Drain due entries from delay ZSETs into their target brokers.

    Returns the number of entries kicked.
    """
    now = time.time()
    total = 0
    for queue_name, broker in brokers_by_queue.items():
        key = f"{DELAY_KEY_PREFIX}:{queue_name}"
        due = await redis.zrangebyscore(key, 0, now)
        if not due:
            continue
        for raw in due:
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                await redis.zrem(key, raw)
                continue
            task = broker.find_task(obj["task"])
            if task is None:
                await redis.zrem(key, raw)
                continue
            await task.kicker().with_broker(broker).kiq(*obj["args"])
            await redis.zrem(key, raw)
            total += 1
    return total
