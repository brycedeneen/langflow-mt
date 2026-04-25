"""Redis-ZSET-backed delayed enqueue.

Replaces arq's `_defer_by`. Two functions:

- `schedule_delayed_kick` — write a one-shot enqueue request to a ZSET
  keyed by `delay:<queue>`, with score = unix epoch to fire.
- `drain_due_kicks` — atomically claim all due entries and dispatch them
  via `kicker().kiq(...)`. Runs in the scheduler process every ~1s.

Single-scheduler contract
-------------------------
The production design assumes exactly **one scheduler process** runs
`drain_due_kicks` at a time. The drain is hardened against accidental
concurrent invocation via a Lua script that performs ZRANGEBYSCORE +
ZREM atomically (no other drainer can observe the same member twice),
but operators should still avoid running multiple schedulers — duplicate
*kicks* would still be possible if the scheduler crashes between the
atomic claim and the broker `kiq`. That at-least-once exposure is the
broker's concern; tasks must be idempotent.

Payload uniqueness
------------------
ZSET members are unique by value. To prevent two schedules with the
same `(task_name, args)` from collapsing to a single entry, every
payload includes a UUID4 nonce. The drainer ignores the nonce when
dispatching (it only reads `task` and `args`).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Mapping

from redis.asyncio import Redis
from taskiq import AsyncBroker

logger = logging.getLogger(__name__)

DELAY_KEY_PREFIX = "delay"  # Redis ZSET key: delay:<queue_name>

# Atomic claim: read all due members and remove them in a single Redis
# round-trip. Returns the claimed payloads. After this returns, no other
# drainer can observe the same members.
#
# KEYS[1] = ZSET key
# ARGV[1] = max score (now)
_DRAIN_LUA = """
local items = redis.call('ZRANGEBYSCORE', KEYS[1], 0, ARGV[1])
if #items > 0 then
    redis.call('ZREM', KEYS[1], unpack(items))
end
return items
"""

# Cache the registered Script object per Redis client. `register_script`
# binds to the client passed to it; we lazily register on first use and
# reuse for subsequent calls with the same client.
_drain_scripts: dict[int, Any] = {}


def _get_drain_script(redis: Redis) -> Any:
    key = id(redis)
    script = _drain_scripts.get(key)
    if script is None:
        script = redis.register_script(_DRAIN_LUA)
        _drain_scripts[key] = script
    return script


async def schedule_delayed_kick(
    *,
    redis: Redis,
    task_name: str,
    queue_name: str,
    args: list[Any],
    delay_s: float,
) -> None:
    """Schedule a one-shot enqueue of `task_name` into `queue_name` after `delay_s`.

    A UUID4 nonce is included in the payload so two schedules with the
    same `(task_name, args)` do not collapse to a single ZSET member.
    """
    payload = json.dumps(
        {
            "task": task_name,
            "args": list(args),
            "nonce": uuid.uuid4().hex,
        }
    )
    score = time.time() + max(0.0, delay_s)
    await redis.zadd(f"{DELAY_KEY_PREFIX}:{queue_name}", {payload: score})


async def drain_due_kicks(
    *,
    redis: Redis,
    brokers_by_queue: Mapping[str, AsyncBroker],
) -> int:
    """Drain due entries from delay ZSETs into their target brokers.

    Atomically claims each queue's due members via a Lua script
    (ZRANGEBYSCORE + ZREM in one op), then dispatches via
    `kicker().kiq(...)`. Returns the number of entries kicked.

    Contract: exactly one scheduler process should call this. The Lua
    claim prevents the same member being seen twice, but a scheduler
    crash between claim and `kiq` would still drop the kick.
    """
    now = time.time()
    total = 0
    script = _get_drain_script(redis)
    for queue_name, broker in brokers_by_queue.items():
        key = f"{DELAY_KEY_PREFIX}:{queue_name}"
        # Atomic claim: items are removed from the ZSET inside the Lua
        # call, so concurrent drainers cannot see them.
        claimed = await script(keys=[key], args=[now])
        if not claimed:
            continue
        for raw in claimed:
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("delayed_enqueue: dropping malformed payload from %s", key)
                continue
            task_name = obj.get("task")
            task = broker.find_task(task_name) if task_name else None
            if task is None:
                logger.warning(
                    "delayed_enqueue: dropping kick for unknown task %r on queue %s",
                    task_name,
                    queue_name,
                )
                continue
            await task.kicker().with_broker(broker).kiq(*obj.get("args", []))
            total += 1
    return total
