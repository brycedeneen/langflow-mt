# Arq → Taskiq Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Note on commits:** The repo owner requires explicit per-commit permission. Plan steps include commit instructions, but the executor MUST pause and ask before each `git commit`. See memory entry "No git commits without permission".

**Goal:** Replace `arq` (in maintenance-only mode) with `taskiq` for all distributed flow execution, preserving every behavioral semantic of the current queue (priority tiers, per-org concurrency, cancellation, heartbeats, reaper, auto-retry, webhook delivery).

**Architecture:** One `ListQueueBroker` per priority tier (high/default/low/webhooks) wired through `TaskiqDepends` for DI. A new singleton `langflow scheduler` process runs cron jobs (via `LabelScheduleSource`) and drains a Redis-ZSET-backed delayed-enqueue queue (replaces arq's `_defer_by`). API + worker pods unchanged in shape; KEDA `listName` updated.

**Tech Stack:** Python 3.11+, FastAPI, Redis, taskiq + taskiq-redis, asyncio. Tests use pytest + `InMemoryBroker` (unit) and real Redis container + `ListQueueBroker` (integration).

**Spec:** `docs/superpowers/specs/2026-04-24-arq-replacement-design.md`

---

## Working Conventions

- All `pytest` invocations run from `src/backend` unless noted.
- Worker integration tests already exist under `src/backend/tests/integration/worker/`; this plan adapts them rather than creating new ones.
- Branch is `platform-multi-tenant`; commits land directly on it (no parent merge target).
- Permission rule: pause before every `git commit` and ask the user.

---

## Task 1: Add Taskiq dependency (keep arq for now)

**Files:**
- Modify: `src/backend/base/pyproject.toml` (~line 91)
- Generated: `uv.lock`, `src/backend/base/uv.lock`

We add `taskiq` and `taskiq-redis` first and leave `arq` in place until the final task. This lets each intermediate task compile and run a subset of tests.

- [ ] **Step 1: Add taskiq deps to pyproject.toml**

In `src/backend/base/pyproject.toml`, in the `dependencies` array near the existing `arq` entry, add:

```toml
"taskiq>=0.11.0,<0.12",
"taskiq-redis>=1.0,<2",
```

Keep `"arq>=0.28,<0.29"` for now. (Pin both to the current stable line; the implementer should bump to the latest stable patch at execution time and run `uv lock`.)

- [ ] **Step 2: Refresh lockfiles**

Run from repo root:
```bash
uv lock
```
Expected: lockfiles updated, no errors. If a Python-version conflict arises, taskiq supports 3.10+; our floor is 3.11 (per project memory), so this should be fine.

- [ ] **Step 3: Verify taskiq is importable**

Run from `src/backend`:
```bash
uv run python -c "import taskiq, taskiq_redis; print(taskiq.__version__, taskiq_redis.__version__)"
```
Expected: prints both versions, exit 0.

- [ ] **Step 4: Commit (ASK FIRST)**

```bash
git add src/backend/base/pyproject.toml uv.lock src/backend/base/uv.lock
git commit -m "chore(deps): add taskiq + taskiq-redis (arq replacement)"
```

---

## Task 2: Create broker registry

**Files:**
- Create: `src/backend/base/langflow/worker_app/brokers.py`
- Create: `src/backend/tests/unit/worker_app/__init__.py` (if missing)
- Create: `src/backend/tests/unit/worker_app/test_brokers.py`

The registry is the single import point for all broker instances. The enqueuer, worker tasks, and scheduler all reach into this module.

- [ ] **Step 1: Write the failing unit test**

`src/backend/tests/unit/worker_app/test_brokers.py`:

```python
from __future__ import annotations

import pytest


def test_registry_exposes_four_brokers():
    from langflow.worker_app import brokers

    assert brokers.broker_high.queue_name == "runs:high"
    assert brokers.broker_default.queue_name == "runs:default"
    assert brokers.broker_low.queue_name == "runs:low"
    assert brokers.broker_webhooks.queue_name == "webhooks"


def test_tier_to_broker_map():
    from langflow.worker_app import brokers

    assert brokers.TIER_TO_BROKER["high"] is brokers.broker_high
    assert brokers.TIER_TO_BROKER["default"] is brokers.broker_default
    assert brokers.TIER_TO_BROKER["low"] is brokers.broker_low


def test_all_brokers_includes_webhooks():
    from langflow.worker_app import brokers

    assert brokers.broker_webhooks in brokers.ALL_BROKERS
    assert len(brokers.ALL_BROKERS) == 4
```

- [ ] **Step 2: Run the failing test**

```bash
cd src/backend && uv run pytest tests/unit/worker_app/test_brokers.py -v
```
Expected: ImportError or `AttributeError` because `brokers` module doesn't exist yet.

- [ ] **Step 3: Implement the broker registry**

`src/backend/base/langflow/worker_app/brokers.py`:

```python
"""Central registry of Taskiq brokers for distributed flow execution.

One ListQueueBroker per priority tier — explicit and type-safe vs arq's
string-based `_queue_name`. The enqueuer picks a broker via `TIER_TO_BROKER`;
workers mount one or more brokers at startup.

A single shared RedisAsyncResultBackend is attached to every broker. Results
are not currently consumed (DB row is the source of truth) but having the
backend in place makes the deferred follow-up (broker-side job-status
polling) a config flip.
"""
from __future__ import annotations

from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from lfx.services.settings.base import Settings


_settings = Settings(_env_file=None)
_redis_url = _settings.redis_url

result_backend = RedisAsyncResultBackend(redis_url=_redis_url)

broker_high = ListQueueBroker(
    url=_redis_url, queue_name="runs:high"
).with_result_backend(result_backend)

broker_default = ListQueueBroker(
    url=_redis_url, queue_name="runs:default"
).with_result_backend(result_backend)

broker_low = ListQueueBroker(
    url=_redis_url, queue_name="runs:low"
).with_result_backend(result_backend)

broker_webhooks = ListQueueBroker(
    url=_redis_url, queue_name="webhooks"
).with_result_backend(result_backend)


TIER_TO_BROKER = {
    "high": broker_high,
    "default": broker_default,
    "low": broker_low,
}

ALL_BROKERS = [broker_high, broker_default, broker_low, broker_webhooks]
```

- [ ] **Step 4: Run tests; confirm pass**

```bash
cd src/backend && uv run pytest tests/unit/worker_app/test_brokers.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit (ASK FIRST)**

```bash
git add src/backend/base/langflow/worker_app/brokers.py \
        src/backend/tests/unit/worker_app/__init__.py \
        src/backend/tests/unit/worker_app/test_brokers.py
git commit -m "feat(worker): add taskiq broker registry"
```

---

## Task 3: Rename `arq_*_queue` settings → `queue_*`

**Files:**
- Modify: `src/lfx/src/lfx/services/settings/base.py` (lines ~376-379)
- Modify: any test reading these settings (`src/backend/tests/unit/test_settings_runs.py`, conftest fixtures)
- Modify: `src/backend/tests/integration/worker/conftest.py` (line 124-127)

We rename in one shot — no alias shim, per spec.

- [ ] **Step 1: Update settings field names**

In `src/lfx/src/lfx/services/settings/base.py` replace:

```python
arq_high_queue: str = "runs:high"
arq_default_queue: str = "runs:default"
arq_low_queue: str = "runs:low"
arq_webhooks_queue: str = "webhooks"
```

with:

```python
queue_high: str = "runs:high"
queue_default: str = "runs:default"
queue_low: str = "runs:low"
queue_webhooks: str = "webhooks"
```

- [ ] **Step 2: Find all readers and update them**

```bash
cd /Users/brycedeneen/dev/langflow && grep -rn "arq_high_queue\|arq_default_queue\|arq_low_queue\|arq_webhooks_queue" src/ --include="*.py"
```

For each match, rename the attribute access. Expected matches as of writing:
- `src/backend/base/langflow/services/runs/enqueue.py:_TIER_TO_QUEUE_ATTR` (will be replaced in Task 5; for now just rename strings)
- `src/backend/base/langflow/worker_app/execute.py:_TIER_TO_QUEUE_ATTR` and `_emit_webhook` body
- `src/backend/base/langflow/worker_app/reaper.py` body
- `src/backend/base/langflow/worker_app/webhook.py` body
- `src/backend/tests/unit/test_settings_runs.py`
- `src/backend/tests/integration/worker/conftest.py:124-127`
- `src/backend/tests/unit/services/runs/test_enqueue.py`

After this task, the codebase compiles but still uses arq under the hood — only the setting name is updated.

- [ ] **Step 3: Run unit tests for settings + enqueue**

```bash
cd src/backend && uv run pytest tests/unit/test_settings_runs.py tests/unit/services/runs/test_enqueue.py -v
```
Expected: pass (assuming all callsites updated).

- [ ] **Step 4: Commit (ASK FIRST)**

```bash
git commit -am "refactor(settings): rename arq_*_queue → queue_*"
```

---

## Task 4: Replace arq pool deps with broker lifespan helpers

**Files:**
- Modify: `src/backend/base/langflow/services/runs/deps.py` (rewrite)
- Search: any caller of `get_arq_pool` / `close_arq_pool`

The arq `create_pool` returned an `ArqRedis` for enqueueing. Brokers self-manage connections; we just need lifespan hooks.

- [ ] **Step 1: Rewrite `services/runs/deps.py`**

```python
"""Broker lifespan helpers for the FastAPI app.

Taskiq brokers self-manage their underlying Redis connections; the API
process only needs to call startup/shutdown to enable enqueueing.
"""
from __future__ import annotations

from langflow.worker_app.brokers import ALL_BROKERS


async def startup_brokers() -> None:
    for broker in ALL_BROKERS:
        await broker.startup()


async def shutdown_brokers() -> None:
    for broker in ALL_BROKERS:
        await broker.shutdown()
```

- [ ] **Step 2: Find old callers**

```bash
grep -rn "get_arq_pool\|close_arq_pool" src/backend src/lfx --include="*.py"
```

Replace each call:
- `await get_arq_pool()` → callers should now import the relevant broker directly from `langflow.worker_app.brokers`. (See Task 5 for the enqueuer; other callers — likely the FastAPI app lifespan — covered in Task 5.)
- `await close_arq_pool()` → `await shutdown_brokers()`.

- [ ] **Step 3: Sanity-import the new module**

```bash
cd src/backend && uv run python -c "from langflow.services.runs.deps import startup_brokers, shutdown_brokers; print('ok')"
```
Expected: prints `ok`.

- [ ] **Step 4: Commit (ASK FIRST)**

```bash
git commit -am "refactor(runs): replace arq pool deps with broker lifespan helpers"
```

---

## Task 5: Wire broker startup/shutdown into FastAPI lifespan

**Files:**
- Modify: the FastAPI app's lifespan (search for current `close_arq_pool` invocation)

Find where the API used to start/close the arq pool and replace with broker lifecycle.

- [ ] **Step 1: Locate the lifespan**

```bash
grep -rn "close_arq_pool\|get_arq_pool" src/backend --include="*.py"
```

- [ ] **Step 2: Replace shutdown call with `await shutdown_brokers()` and add `await startup_brokers()` to startup**

In whichever module owns lifespan (typically `langflow/main.py` or similar):

```python
from langflow.services.runs.deps import startup_brokers, shutdown_brokers

# in lifespan startup
await startup_brokers()

# in lifespan shutdown
await shutdown_brokers()
```

- [ ] **Step 3: Smoke-test the API boots**

```bash
cd src/backend && uv run python -c "
import asyncio
from langflow.services.runs.deps import startup_brokers, shutdown_brokers

async def main():
    await startup_brokers()
    await shutdown_brokers()

asyncio.run(main())
print('lifecycle ok')
"
```
Expected: prints `lifecycle ok` (requires Redis running locally — start one if needed: `docker run -d --rm -p 6379:6379 redis:7`).

- [ ] **Step 4: Commit (ASK FIRST)**

```bash
git commit -am "refactor(api): wire broker startup/shutdown into FastAPI lifespan"
```

---

## Task 6: Convert `services/runs/enqueue.py` to broker-based enqueueing

**Files:**
- Modify: `src/backend/base/langflow/services/runs/enqueue.py`
- Modify: `src/backend/tests/unit/services/runs/test_enqueue.py`

- [ ] **Step 1: Rewrite the failing test to use InMemoryBroker**

`src/backend/tests/unit/services/runs/test_enqueue.py`:

```python
from __future__ import annotations

import pytest
from uuid import uuid4

from taskiq import InMemoryBroker

from langflow.services.runs.enqueue import RunEnqueuer
from langflow.services.database.models.flow_run.model import TriggeredBy


@pytest.fixture
def in_memory_broker():
    return InMemoryBroker()


@pytest.mark.asyncio
async def test_enqueue_uses_high_broker_for_high_tier(seeded_db, settings, in_memory_broker_registry):
    enqueuer = RunEnqueuer(
        db=seeded_db.session,
        brokers=in_memory_broker_registry,  # dict {"high": InMemoryBroker(), ...}
        settings=settings,
    )
    run = await enqueuer.enqueue(
        org_id=seeded_db.high_tier_org.id,
        flow_id=seeded_db.flow.id,
        triggered_by=TriggeredBy.API,
        actor_id=None,
        inputs=None,
    )
    assert run.priority == 1
    # InMemoryBroker stores kicked tasks; assert one task is queued in the "high" instance
    assert in_memory_broker_registry["high"].messages_count() == 1
```

(The exact `InMemoryBroker` introspection method may differ in the installed Taskiq version — `messages_count` / `_messages` / `kicked_tasks`. Adjust at implementation time and update the test fixture.)

- [ ] **Step 2: Run the failing test**

```bash
cd src/backend && uv run pytest tests/unit/services/runs/test_enqueue.py -v
```
Expected: FAIL — `RunEnqueuer` still takes `redis: ArqRedis`.

- [ ] **Step 3: Rewrite the enqueuer**

`src/backend/base/langflow/services/runs/enqueue.py`:

```python
from __future__ import annotations

from uuid import UUID
from typing import Any, Mapping

from sqlmodel.ext.asyncio.session import AsyncSession
from taskiq import AsyncBroker

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun, RunStatus, TriggeredBy
from langflow.services.database.models.organization.model import Organization
from lfx.services.settings.base import Settings


_TIER_TO_PRIORITY = {"high": 1, "default": 5, "low": 9}


class RunEnqueuer:
    def __init__(
        self,
        *,
        db: AsyncSession,
        brokers: Mapping[str, AsyncBroker],
        settings: Settings,
    ):
        self.db = db
        self.brokers = brokers
        self.settings = settings

    async def enqueue(
        self,
        *,
        org_id: UUID,
        flow_id: UUID,
        triggered_by: TriggeredBy,
        actor_id: UUID | None,
        inputs: dict[str, Any] | None,
    ) -> FlowRun:
        from langflow.worker_app.execute import execute_run

        org = await self.db.get(Organization, org_id)
        flow = await self.db.get(Flow, flow_id)
        if org is None or flow is None or flow.organization_id != org_id:
            raise ValueError("org/flow mismatch")

        run = FlowRun(
            organization_id=org_id,
            flow_id=flow_id,
            triggered_by=triggered_by,
            actor_id=actor_id,
            status=RunStatus.QUEUED,
            priority=_TIER_TO_PRIORITY[org.runs_priority_tier],
            inputs=inputs,
            auto_retry=flow.auto_retry,
            max_retries=flow.max_retries,
            timeout_seconds=flow.timeout_seconds,
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        broker = self.brokers[org.runs_priority_tier]
        await execute_run.kicker().with_broker(broker).kiq(str(run.id))
        return run
```

- [ ] **Step 4: Update callers of `RunEnqueuer`**

```bash
grep -rn "RunEnqueuer(" src/backend --include="*.py"
```

In each callsite (likely `api/v2/runs.py` and `api/v1/endpoints.py`), replace the `redis=...` kwarg with `brokers=TIER_TO_BROKER` imported from `langflow.worker_app.brokers`. Note: `webhooks` is not in `TIER_TO_BROKER`; the enqueuer only needs the run-tier brokers.

- [ ] **Step 5: Run unit + relevant API tests**

```bash
cd src/backend && uv run pytest tests/unit/services/runs/test_enqueue.py tests/unit/api/v2/test_runs_enqueue.py -v
```
Expected: pass.

- [ ] **Step 6: Commit (ASK FIRST)**

```bash
git commit -am "refactor(runs): broker-based enqueue via Taskiq kicker"
```

---

## Task 7: Build the Redis-ZSET-backed delayed enqueue helper

**Files:**
- Create: `src/backend/base/langflow/worker_app/delayed_enqueue.py`
- Create: `src/backend/tests/integration/worker/test_delayed_enqueue.py`

`ListQueueBroker` does not natively support delayed delivery (arq's `_defer_by`). We add a small ZSET-based primitive: scheduled enqueue writes to a ZSET keyed by `delay:<queue>` with score = unix-time-to-fire; the scheduler process drains due entries every second.

- [ ] **Step 1: Write the failing integration test**

`src/backend/tests/integration/worker/test_delayed_enqueue.py`:

```python
from __future__ import annotations
import asyncio
import time
import pytest

from taskiq_redis import ListQueueBroker
from langflow.worker_app.delayed_enqueue import schedule_delayed_kick, drain_due_kicks


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
    # Not yet due
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
```

- [ ] **Step 2: Run the failing test**

```bash
cd src/backend && uv run pytest tests/integration/worker/test_delayed_enqueue.py -v
```
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement the helper**

`src/backend/base/langflow/worker_app/delayed_enqueue.py`:

```python
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
                # Drop malformed entries
                await redis.zrem(key, raw)
                continue
            task = broker.find_task(obj["task"])
            if task is None:
                # Task not registered on this broker — drop and warn
                await redis.zrem(key, raw)
                continue
            await task.kicker().with_broker(broker).kiq(*obj["args"])
            await redis.zrem(key, raw)
            total += 1
    return total
```

(`broker.find_task(name)` is the Taskiq lookup. If the installed version uses a different attribute name, adjust — likely `broker.find_task_by_name` or `broker.tasks[name]`.)

- [ ] **Step 4: Run the test**

```bash
cd src/backend && uv run pytest tests/integration/worker/test_delayed_enqueue.py -v
```
Expected: pass.

- [ ] **Step 5: Commit (ASK FIRST)**

```bash
git add src/backend/base/langflow/worker_app/delayed_enqueue.py \
        src/backend/tests/integration/worker/test_delayed_enqueue.py
git commit -m "feat(worker): Redis-ZSET delayed enqueue (replaces arq _defer_by)"
```

---

## Task 8: Convert `worker_app/execute.py` to TaskiqDepends + delayed kicker

**Files:**
- Modify: `src/backend/base/langflow/worker_app/execute.py` (rewrite signature + helpers)

The internal logic (cancel watcher, heartbeat, timeout, graph runner) does not change. Only the surrounding DI and the two enqueue helpers (`_emit_webhook`, concurrency-cap requeue, auto-retry requeue) change.

- [ ] **Step 1: Rewrite the function signature and DI**

Replace the top of `execute.py`:

```python
from __future__ import annotations
import asyncio
import os
import socket
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from taskiq import TaskiqDepends

from lfx.log.logger import logger

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun, RunStatus
from langflow.services.database.models.organization.model import Organization
from langflow.services.runs.concurrency import OrgConcurrency
from langflow.services.runs.cancel import is_cancel_requested
from langflow.services.runs.payload import PayloadOffloader
from langflow.worker_app.brokers import broker_default, broker_high, broker_low, broker_webhooks, TIER_TO_BROKER
from langflow.worker_app.delayed_enqueue import schedule_delayed_kick
from langflow.worker_app.deps import (
    get_db_sessionmaker,
    get_storage,
    get_settings,
    get_redis,
    get_graph_runner,
)
from langflow.worker_app.log_sink import RunLogSink


WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
HEARTBEAT_INTERVAL = 15.0
CANCEL_POLL_INTERVAL = 2.0
REQUEUE_DELAY = 5.0


_TIER_TO_QUEUE_NAME = {
    "high": "runs:high",
    "default": "runs:default",
    "low": "runs:low",
}
```

Note: `worker_app/deps.py` is a small new module created in Task 11 holding the dependency providers; the broker registers tasks via `@broker_default.task` (etc.), so we register `execute_run` against **all three run-tier brokers** (or pick one as the canonical and let the kicker route via `with_broker`). Easier: register against `broker_default` and use `with_broker` for routing.

- [ ] **Step 2: Re-decorate `execute_run` and replace ctx with deps**

```python
@broker_default.task(task_name="execute_run")
@broker_high.task(task_name="execute_run")
@broker_low.task(task_name="execute_run")
async def execute_run(
    run_id: str,
    *,
    sessionmaker = TaskiqDepends(get_db_sessionmaker),
    storage = TaskiqDepends(get_storage),
    settings = TaskiqDepends(get_settings),
    redis: Redis = TaskiqDepends(get_redis),
    graph_runner = TaskiqDepends(get_graph_runner),
) -> None:
    run_uuid = UUID(run_id)
    logger.info(f"[run={run_id}] worker picked up job (worker_id={WORKER_ID})")

    offloader = PayloadOffloader(storage, inline_max_bytes=settings.run_payload_inline_max_bytes)
    concurrency = OrgConcurrency(redis)

    # ... existing body unchanged through the org/flow/run lookups and concurrency check
```

(If applying the same `@task` decorator three times across brokers is awkward, register once on `broker_default` and have callers always use `with_broker` to route. Simpler. Use this approach.)

Updated registration:
```python
@broker_default.task(task_name="execute_run")
async def execute_run(...):
    ...
```

The kicker can dispatch into any broker via `execute_run.kicker().with_broker(broker_high).kiq(...)` — the broker dispatches, the worker on that broker picks up, and the worker resolves the task by name when it ran `broker_default.startup()` at init. **Critical:** for this to work, every worker must have *registered* `execute_run` against each broker it serves. The simplest route is to keep `@broker_X.task(...)` on every broker, but Taskiq supports `broker.register_task(task)` to copy a task definition. Implementer: pick whichever pattern works with the installed Taskiq version, document it in the file docstring.

- [ ] **Step 3: Replace `_emit_webhook`**

```python
async def _emit_webhook(run_id: UUID, event: str) -> None:
    await deliver_webhook.kicker().with_broker(broker_webhooks).kiq(str(run_id), event)
```

(`deliver_webhook` imported from `worker_app.webhook` — Task 9.)

- [ ] **Step 4: Replace concurrency-cap requeue**

In the body where today we have:
```python
await arq.enqueue_job("execute_run", run_id, _queue_name=queue, _defer_by=REQUEUE_DELAY)
```

Replace with:
```python
queue = _TIER_TO_QUEUE_NAME[org.runs_priority_tier]
await schedule_delayed_kick(
    redis=redis,
    task_name="execute_run",
    queue_name=queue,
    args=[run_id],
    delay_s=REQUEUE_DELAY,
)
```

- [ ] **Step 5: Replace auto-retry requeue**

In the body where today we have:
```python
queue = getattr(settings, _TIER_TO_QUEUE_ATTR[org.runs_priority_tier])
await arq.enqueue_job("execute_run", run_id, _queue_name=queue, _defer_by=backoff)
```

Replace with:
```python
queue = _TIER_TO_QUEUE_NAME[org.runs_priority_tier]
await schedule_delayed_kick(
    redis=redis,
    task_name="execute_run",
    queue_name=queue,
    args=[run_id],
    delay_s=backoff,
)
```

- [ ] **Step 6: Run the existing integration tests for execute_run**

(These will FAIL at this step because the worker isn't running with the new entrypoint yet — that lands in Task 12. Verify the file imports cleanly:)

```bash
cd src/backend && uv run python -c "from langflow.worker_app.execute import execute_run; print(execute_run.task_name)"
```
Expected: prints `execute_run`.

- [ ] **Step 7: Commit (ASK FIRST)**

```bash
git commit -am "refactor(worker): execute_run uses TaskiqDepends + delayed_enqueue"
```

---

## Task 9: Convert `worker_app/webhook.py`

**Files:**
- Modify: `src/backend/base/langflow/worker_app/webhook.py`

- [ ] **Step 1: Rewrite the signature and retry path**

Replace the top of `webhook.py`:

```python
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import httpx
from redis.asyncio import Redis
from taskiq import TaskiqDepends

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun
from langflow.services.runs.webhook_sign import sign_body
from langflow.worker_app.brokers import broker_webhooks
from langflow.worker_app.delayed_enqueue import schedule_delayed_kick
from langflow.worker_app.deps import get_db_sessionmaker, get_settings, get_redis


_BACKOFF_SCHEDULE_SEC = [10, 30, 120, 600, 1800, 3600]
_HTTP_TIMEOUT = httpx.Timeout(10.0)
```

- [ ] **Step 2: Re-decorate `deliver_webhook`**

```python
@broker_webhooks.task(task_name="deliver_webhook")
async def deliver_webhook(
    run_id: str,
    event: str,
    attempt: int = 0,
    *,
    sessionmaker = TaskiqDepends(get_db_sessionmaker),
    settings = TaskiqDepends(get_settings),
    redis: Redis = TaskiqDepends(get_redis),
) -> None:
    # ... existing body up to the retry block, with `ctx["db_sessionmaker"]` replaced by `sessionmaker`
```

- [ ] **Step 3: Replace the retry enqueue**

Today:
```python
await ctx["arq"].enqueue_job(
    "deliver_webhook", run_id, event, attempt + 1,
    _queue_name=ctx["settings"].arq_webhooks_queue, _defer_by=delay,
)
```

Replace with:
```python
await schedule_delayed_kick(
    redis=redis,
    task_name="deliver_webhook",
    queue_name="webhooks",
    args=[run_id, event, attempt + 1],
    delay_s=delay,
)
```

- [ ] **Step 4: Verify import**

```bash
cd src/backend && uv run python -c "from langflow.worker_app.webhook import deliver_webhook; print(deliver_webhook.task_name)"
```
Expected: prints `deliver_webhook`.

- [ ] **Step 5: Commit (ASK FIRST)**

```bash
git commit -am "refactor(worker): deliver_webhook uses TaskiqDepends"
```

---

## Task 10: Convert reaper, retention, audit_cleanup, pricing_refresh to scheduled tasks

**Files:**
- Modify: `src/backend/base/langflow/worker_app/reaper.py`
- Modify: `src/backend/base/langflow/worker_app/retention.py`
- Modify: `src/backend/base/langflow/worker_app/audit_cleanup.py`
- Modify: `src/backend/base/langflow/worker_app/pricing_refresh.py`

Each of these is currently an arq cron callable. Each becomes a Taskiq task with cron metadata. Reaper drops to 1-minute cadence per spec.

- [ ] **Step 1: Rewrite `reaper.py`**

```python
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
    sessionmaker = TaskiqDepends(get_db_sessionmaker),
    redis: Redis = TaskiqDepends(get_redis),
) -> None:
    from langflow.worker_app.webhook import deliver_webhook  # avoid circular

    concurrency = OrgConcurrency(redis)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=STALE_AFTER_SECONDS)

    reaped_rows = []
    async with sessionmaker() as session:
        stmt = select(FlowRun).where(
            FlowRun.status == RunStatus.RUNNING,
            FlowRun.heartbeat_at < cutoff,
        )
        rows = (await session.exec(stmt)).all()
        for row in rows:
            row.status = RunStatus.FAILED
            row.finished_at = datetime.now(timezone.utc)
            row.error = {"type": "worker_lost", "message": "no heartbeat within 60s"}
            await concurrency.release(row.organization_id)
            reaped_rows.append(row.id)
        await session.commit()

    for run_id in reaped_rows:
        await deliver_webhook.kicker().with_broker(broker_webhooks).kiq(
            str(run_id), "run.failed"
        )
```

- [ ] **Step 2: Rewrite `retention.py`**

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete
from taskiq import TaskiqDepends

from langflow.services.database.models.flow_run.model import FlowRun
from langflow.worker_app.brokers import broker_default
from langflow.worker_app.deps import get_db_sessionmaker, get_settings


@broker_default.task(
    task_name="retention_sweep",
    schedule=[{"cron": "0 * * * *"}],  # every hour at :00
)
async def retention_sweep(
    *,
    sessionmaker = TaskiqDepends(get_db_sessionmaker),
    settings = TaskiqDepends(get_settings),
) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.run_retention_hours)
    async with sessionmaker() as session:
        stmt = delete(FlowRun).where(
            FlowRun.finished_at.is_not(None),
            FlowRun.finished_at < cutoff,
        )
        await session.exec(stmt)
        await session.commit()
```

- [ ] **Step 3: Rewrite `audit_cleanup.py`**

```python
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete
from taskiq import TaskiqDepends

from lfx.log.logger import logger
from langflow.services.database.models.audit_log import AuditLog
from langflow.worker_app.brokers import broker_default
from langflow.worker_app.deps import get_db_sessionmaker, get_settings


@broker_default.task(
    task_name="audit_cleanup",
    schedule=[{"cron": "0 3 * * *"}],  # daily at 03:00 UTC
)
async def audit_cleanup(
    *,
    sessionmaker = TaskiqDepends(get_db_sessionmaker),
    settings = TaskiqDepends(get_settings),
) -> None:
    retention = int(getattr(settings, "audit_log_retention_days", 90))
    if retention <= 0:
        logger.info("audit_cleanup: retention disabled (audit_log_retention_days=0)")
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention)
    async with sessionmaker() as session:
        stmt = delete(AuditLog).where(AuditLog.created_at < cutoff)
        result = await session.exec(stmt)
        await session.commit()

    count = result.rowcount if hasattr(result, "rowcount") else "?"
    logger.info(f"audit_cleanup: deleted rows older than {cutoff.isoformat()} (count={count})")
```

- [ ] **Step 4: Rewrite `pricing_refresh.py`**

```python
from __future__ import annotations
from lfx.log.logger import logger
from langflow.worker_app.brokers import broker_default


@broker_default.task(
    task_name="refresh_pricing_cache",
    schedule=[{"cron": "0 0 * * *"}],  # daily at 00:00 UTC
)
async def refresh_pricing_cache() -> None:
    """Daily: reload litellm's model_cost map into PricingService."""
    try:
        from langflow.services.deps import get_pricing_service
        service = get_pricing_service()
        service.reload_from_litellm()
    except Exception as exc:  # noqa: BLE001
        logger.exception("refresh_pricing_cache failed: %s", exc)
```

- [ ] **Step 5: Smoke-import all four**

```bash
cd src/backend && uv run python -c "
from langflow.worker_app.reaper import reap_lost_runs
from langflow.worker_app.retention import retention_sweep
from langflow.worker_app.audit_cleanup import audit_cleanup
from langflow.worker_app.pricing_refresh import refresh_pricing_cache
print(reap_lost_runs.task_name, retention_sweep.task_name, audit_cleanup.task_name, refresh_pricing_cache.task_name)
"
```
Expected: prints all four task names.

- [ ] **Step 6: Commit (ASK FIRST)**

```bash
git commit -am "refactor(worker): cron tasks → Taskiq scheduled tasks"
```

---

## Task 11: Replace `worker_app/settings.py` with broker startup hooks

**Files:**
- Modify: `src/backend/base/langflow/worker_app/settings.py` (delete WorkerSettings)
- Create: `src/backend/base/langflow/worker_app/deps.py` (TaskiqDepends providers)
- Create: `src/backend/base/langflow/worker_app/lifecycle.py` (startup/shutdown hooks)

`WorkerSettings` was the arq class that bundled functions, cron, queue name, hooks. Taskiq spreads these across the broker decorators (already done) and broker startup events. We need:
- `deps.py` — the dependency providers used by `TaskiqDepends`
- `lifecycle.py` — hooks registered against every broker via `@broker.on_event(...)`

- [ ] **Step 1: Create `deps.py`**

```python
"""TaskiqDepends providers for worker tasks.

These are resolved by the Taskiq DI system at task-call time, replacing
the arq `ctx` dict.
"""
from __future__ import annotations

from typing import Any

from redis.asyncio import Redis


# Module-level state populated at worker startup. The Taskiq broker
# `on_event(WORKER_STARTUP)` hook (in lifecycle.py) initialises Langflow
# services and stores references here.
_state: dict[str, Any] = {}


def _set(key: str, value: Any) -> None:
    _state[key] = value


def _clear() -> None:
    _state.clear()


def get_db_sessionmaker():
    return _state["sessionmaker"]


def get_storage():
    return _state["storage"]


def get_settings():
    return _state["settings"]


def get_redis() -> Redis:
    return _state["redis"]


def get_graph_runner():
    """Injection hook for tests; default None means use the in-process runner."""
    return _state.get("graph_runner")
```

- [ ] **Step 2: Create `lifecycle.py`**

```python
"""Worker process startup/shutdown hooks for every broker."""
from __future__ import annotations

import socket, os
from redis.asyncio import Redis
from taskiq import TaskiqEvents

from lfx.log.logger import logger
from langflow.worker_app import deps as worker_deps
from langflow.worker_app.brokers import ALL_BROKERS


WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


async def _on_startup(state: object) -> None:
    from langflow.services.deps import get_db_service, get_settings_service, get_storage_service
    from langflow.services.utils import initialize_services

    await initialize_services()

    settings_service = get_settings_service()
    db_service = get_db_service()
    settings = settings_service.settings

    worker_deps._set("settings", settings)
    worker_deps._set("sessionmaker", db_service.async_session_maker)
    worker_deps._set("storage", get_storage_service())
    worker_deps._set("redis", Redis.from_url(settings.redis_url))

    logger.info(f"Langflow worker started: worker_id={WORKER_ID}")


async def _on_shutdown(state: object) -> None:
    redis = worker_deps._state.get("redis")
    if redis is not None:
        await redis.aclose()
    worker_deps._clear()
    logger.info(f"Langflow worker shutting down: worker_id={WORKER_ID}")


def register_lifecycle() -> None:
    """Wire startup/shutdown to every broker so the active worker fires them."""
    for broker in ALL_BROKERS:
        broker.add_event_handler(TaskiqEvents.WORKER_STARTUP, _on_startup)
        broker.add_event_handler(TaskiqEvents.WORKER_SHUTDOWN, _on_shutdown)


register_lifecycle()
```

(If the Taskiq version uses `@broker.on_event` decorator semantics differently, switch to the decorator form. The shape — register-once, fire on every worker — is what matters.)

- [ ] **Step 3: Delete the old `settings.py` content**

`src/backend/base/langflow/worker_app/settings.py`:

```python
"""DEPRECATED — module retained as an import shim for the lifecycle wire-up.

The arq-era `WorkerSettings` class is replaced by:
- `langflow.worker_app.brokers` (broker registry)
- `langflow.worker_app.deps` (TaskiqDepends providers)
- `langflow.worker_app.lifecycle` (broker startup/shutdown)

Importing this module ensures lifecycle handlers are registered.
"""
from langflow.worker_app import lifecycle  # noqa: F401  (registration side-effect)
```

- [ ] **Step 4: Smoke import**

```bash
cd src/backend && uv run python -c "
from langflow.worker_app import settings, deps, lifecycle, brokers
print('all good')
"
```
Expected: prints `all good`.

- [ ] **Step 5: Commit (ASK FIRST)**

```bash
git add src/backend/base/langflow/worker_app/settings.py \
        src/backend/base/langflow/worker_app/deps.py \
        src/backend/base/langflow/worker_app/lifecycle.py
git commit -m "refactor(worker): replace arq WorkerSettings with broker lifecycle"
```

---

## Task 12: Update `cli/worker_cmd.py` to launch the Taskiq worker

**Files:**
- Modify: `src/backend/base/langflow/cli/worker_cmd.py` (rewrite)

The Taskiq CLI is `taskiq worker module:broker`. We invoke it programmatically.

- [ ] **Step 1: Rewrite `worker_cmd.py`**

```python
from __future__ import annotations

import os
import sys

import typer

from lfx.log.logger import configure


def worker_cmd(
    queue: list[str] = typer.Option(
        None,
        "--queue",
        "-q",
        help=(
            "Queue to consume (one of: runs:high, runs:default, runs:low, webhooks). "
            "Repeat -q to consume multiple. Defaults to runs:default."
        ),
    ),
    concurrency: int | None = typer.Option(
        None,
        "--concurrency",
        help="Max in-flight jobs per worker process.",
    ),
    log_level: str = typer.Option(
        "info",
        "--log-level",
        envvar="LANGFLOW_LOG_LEVEL",
        help="Logging level (debug, info, warning, error, critical).",
    ),
):
    """Run a distributed flow-execution worker."""
    os.environ["LANGFLOW_LOG_LEVEL"] = log_level
    configure(log_level=log_level)

    # Import worker tasks (decorator side-effect registers them on brokers)
    from langflow.worker_app import settings as _wire  # noqa: F401  (lifecycle hooks)
    from langflow.worker_app import execute as _e  # noqa: F401
    from langflow.worker_app import webhook as _w  # noqa: F401
    from langflow.worker_app import reaper as _r  # noqa: F401
    from langflow.worker_app import retention as _ret  # noqa: F401
    from langflow.worker_app import audit_cleanup as _a  # noqa: F401
    from langflow.worker_app import pricing_refresh as _p  # noqa: F401

    queues = queue or ["runs:default"]
    name_to_module = {
        "runs:high": "langflow.worker_app.brokers:broker_high",
        "runs:default": "langflow.worker_app.brokers:broker_default",
        "runs:low": "langflow.worker_app.brokers:broker_low",
        "webhooks": "langflow.worker_app.brokers:broker_webhooks",
    }

    argv = ["taskiq", "worker"]
    for q in queues:
        if q not in name_to_module:
            raise typer.BadParameter(f"unknown queue: {q}")
        argv.append(name_to_module[q])
    if concurrency is not None:
        argv += ["--workers", str(concurrency)]

    # Hand off to Taskiq's CLI runner
    from taskiq.cli.worker.cmd import WorkerCMD
    sys.argv = argv
    WorkerCMD().run()
```

(The exact entry-point — `WorkerCMD().run()` vs `taskiq.cli.worker.run.run`-style — varies across Taskiq versions. Implementer: pin to whichever is documented in the installed Taskiq's README.)

- [ ] **Step 2: Smoke-test the worker boots and exits cleanly on SIGINT**

```bash
cd src/backend && timeout 5 uv run langflow worker -q runs:default -q webhooks || echo "exited with $?"
```
Expected: starts, logs "worker started", times out after 5s with non-zero exit (which is fine — we just want to confirm it boots).

- [ ] **Step 3: Commit (ASK FIRST)**

```bash
git commit -am "refactor(cli): worker_cmd launches Taskiq worker"
```

---

## Task 13: Add `langflow scheduler` CLI command

**Files:**
- Create: `src/backend/base/langflow/cli/scheduler_cmd.py`
- Modify: `src/backend/base/langflow/__main__.py` (register the new command)

The scheduler runs cron jobs (via `LabelScheduleSource`) and drains the delayed-enqueue ZSET every second.

- [ ] **Step 1: Create `scheduler_cmd.py`**

```python
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
    from taskiq.schedule_sources import LabelScheduleSource

    # Side-effect imports register cron tasks on brokers
    from langflow.worker_app import (  # noqa: F401
        execute, webhook, reaper, retention, audit_cleanup, pricing_refresh, lifecycle,
    )
    from langflow.worker_app.brokers import (
        broker_default, broker_high, broker_low, broker_webhooks, ALL_BROKERS,
    )
    from langflow.worker_app.delayed_enqueue import drain_due_kicks
    from lfx.services.settings.base import Settings

    settings = Settings(_env_file=None)
    for broker in ALL_BROKERS:
        await broker.startup()

    scheduler = TaskiqScheduler(
        broker=broker_default,
        sources=[LabelScheduleSource(broker_default)],
    )

    redis = Redis.from_url(settings.redis_url)
    brokers_by_queue = {
        "runs:high": broker_high,
        "runs:default": broker_default,
        "runs:low": broker_low,
        "webhooks": broker_webhooks,
    }

    drain_task = asyncio.create_task(_drain_loop(redis, brokers_by_queue))
    try:
        await scheduler.start()
    finally:
        drain_task.cancel()
        for broker in ALL_BROKERS:
            await broker.shutdown()
        await redis.aclose()


async def _drain_loop(redis, brokers_by_queue) -> None:
    from langflow.worker_app.delayed_enqueue import drain_due_kicks
    while True:
        try:
            await drain_due_kicks(redis=redis, brokers_by_queue=brokers_by_queue)
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001
            from lfx.log.logger import logger
            logger.exception("delayed-enqueue drain loop tick failed")
        await asyncio.sleep(1.0)
```

(The exact `TaskiqScheduler` constructor and `start()` shape may differ between Taskiq versions. Verify against the installed version's docs at execution time. The shape — one process, cron + delay drainer — is the contract.)

- [ ] **Step 2: Register the command in `__main__.py`**

In `src/backend/base/langflow/__main__.py`, near the existing worker registration (around line 62-64):

```python
from langflow.cli.scheduler_cmd import scheduler_cmd  # noqa: E402

app.command(name="scheduler", help="Run the singleton scheduler (cron + delayed enqueue)")(scheduler_cmd)
```

- [ ] **Step 3: Smoke-test**

```bash
cd src/backend && timeout 5 uv run langflow scheduler || echo "exited with $?"
```
Expected: starts, logs "scheduler started" (or equivalent), times out.

- [ ] **Step 4: Commit (ASK FIRST)**

```bash
git add src/backend/base/langflow/cli/scheduler_cmd.py src/backend/base/langflow/__main__.py
git commit -m "feat(cli): add langflow scheduler command"
```

---

## Task 14: Adapt integration test conftest for Taskiq

**Files:**
- Modify: `src/backend/tests/integration/worker/conftest.py`

Replace the `arq` AsyncMock and `_TIER_TO_QUEUE_ATTR`-shaped settings with a `brokers` mapping pointing at `InMemoryBroker` instances or real ones.

- [ ] **Step 1: Rewrite the `worker_ctx` fixture (shape change)**

The existing fixture returns a dict with keys `redis`, `db_sessionmaker`, `storage`, `settings`, `arq`, `graph_runner`. Adapter tests will keep importing this fixture, so we keep its shape but change the contents:

```python
@pytest.fixture
def worker_ctx(engine_and_factory, redis_service, mock_storage):
    from langflow.services.runs.payload import PayloadOffloader
    from langflow.worker_app import deps as worker_deps

    _, factory = engine_and_factory

    settings = Mock()
    settings.run_payload_inline_max_bytes = 10 * 1024 * 1024
    settings.queue_high = "runs:high"
    settings.queue_default = "runs:default"
    settings.queue_low = "runs:low"
    settings.queue_webhooks = "webhooks"
    settings.run_retention_hours = 24
    settings.redis_url = redis_service.url

    async def deterministic_runner(flow, triggered_by, inputs, actor_id):
        await asyncio.sleep(0.05)
        return {"ok": True, "echo": inputs}

    # Populate the worker_deps state so TaskiqDepends providers resolve
    worker_deps._set("settings", settings)
    worker_deps._set("sessionmaker", factory)
    worker_deps._set("storage", mock_storage)
    worker_deps._set("redis", redis_service.client)
    worker_deps._set("graph_runner", deterministic_runner)

    yield {
        "redis": redis_service.client,
        "db_sessionmaker": factory,
        "storage": mock_storage,
        "settings": settings,
        "graph_runner": deterministic_runner,
    }
    worker_deps._clear()
```

(The `arq` key is gone; tests that called `worker_ctx["arq"].enqueue_job.assert_called(...)` need to assert against the broker's queue or against ZSET state for delayed kicks. Task 15-16 covers this.)

- [ ] **Step 2: Verify imports**

```bash
cd src/backend && uv run pytest tests/integration/worker/conftest.py --collect-only
```
Expected: no errors collecting.

- [ ] **Step 3: Commit (ASK FIRST)**

```bash
git commit -am "test(worker): conftest uses worker_deps state instead of arq mock"
```

---

## Task 15: Adapt `test_execute_run.py`, `test_execute_run_retry.py`, `test_execute_run_concurrency.py`

**Files:**
- Modify: `src/backend/tests/integration/worker/test_execute_run.py`
- Modify: `src/backend/tests/integration/worker/test_execute_run_retry.py`
- Modify: `src/backend/tests/integration/worker/test_execute_run_concurrency.py`

These tests today call `execute_run(ctx, run_id_str)` directly. With Taskiq DI we have two options:

1. Call `execute_run` directly as a plain async function — but the function now has `TaskiqDepends` arguments. We'd need to pass those positionally or keyword.
2. Use `execute_run.kicker()` and let Taskiq resolve deps from the broker context.

Option 1 is simpler for unit-style tests because it bypasses the broker. With keyword args we can simply pass `sessionmaker=`, `storage=`, etc., directly — `TaskiqDepends(...)` defaults are only used when the caller doesn't supply the arg. So `await execute_run(run_id, sessionmaker=factory, storage=mock_storage, ...)` works.

- [ ] **Step 1: Update each test to pass deps as kwargs**

Pattern for each `await execute_run(worker_ctx, str(run.id))` callsite — change to:

```python
await execute_run(
    str(run.id),
    sessionmaker=worker_ctx["db_sessionmaker"],
    storage=worker_ctx["storage"],
    settings=worker_ctx["settings"],
    redis=worker_ctx["redis"],
    graph_runner=worker_ctx["graph_runner"],
)
```

For tests that previously asserted `worker_ctx["arq"].enqueue_job.assert_called_with(...)`:
- For **delayed kicks** (concurrency-cap requeue, auto-retry), assert via:

```python
import json
items = await worker_ctx["redis"].zrange("delay:runs:default", 0, -1)
assert any(json.loads(i)["task"] == "execute_run" for i in items)
```

- For **webhook emits** (`_emit_webhook`), the call now goes through `broker_webhooks.kicker()`. Use `InMemoryBroker.kicked_messages` or assert via the Redis list:

```python
length = await worker_ctx["redis"].llen("webhooks")
assert length == 1
```

- [ ] **Step 2: Run the three tests**

```bash
cd src/backend && uv run pytest tests/integration/worker/test_execute_run.py tests/integration/worker/test_execute_run_retry.py tests/integration/worker/test_execute_run_concurrency.py -v
```
Expected: all green. If a test asserts on `arq.enqueue_job` call args by position, rewrite it to ZSET / list inspection.

- [ ] **Step 3: Commit (ASK FIRST)**

```bash
git commit -am "test(worker): execute_run tests use kwargs DI + ZSET/list assertions"
```

---

## Task 16: Adapt `test_reaper.py` and `test_deliver_webhook.py`

**Files:**
- Modify: `src/backend/tests/integration/worker/test_reaper.py`
- Modify: `src/backend/tests/integration/worker/test_deliver_webhook.py`

Same pattern as Task 15.

- [ ] **Step 1: Update reaper test**

Replace `await reap_lost_runs(ctx)` with:

```python
await reap_lost_runs(
    sessionmaker=worker_ctx["db_sessionmaker"],
    redis=worker_ctx["redis"],
)
```

Assertions about webhook re-enqueueing become assertions about the `webhooks` Redis list length.

- [ ] **Step 2: Update webhook test**

Replace `await deliver_webhook(ctx, run_id, "run.succeeded", attempt=0)` with:

```python
await deliver_webhook(
    str(run_id),
    "run.succeeded",
    0,
    sessionmaker=worker_ctx["db_sessionmaker"],
    settings=worker_ctx["settings"],
    redis=worker_ctx["redis"],
)
```

Retry-backoff assertion: instead of asserting `worker_ctx["arq"].enqueue_job.call_args.kwargs["_defer_by"]`, assert against the `delay:webhooks` ZSET score:

```python
items_with_scores = await worker_ctx["redis"].zrange("delay:webhooks", 0, -1, withscores=True)
assert len(items_with_scores) == 1
_, score = items_with_scores[0]
expected_window = (time.time() + 9.5, time.time() + 11)  # 10s ± slack
assert expected_window[0] < score < expected_window[1]
```

- [ ] **Step 3: Run the two tests**

```bash
cd src/backend && uv run pytest tests/integration/worker/test_reaper.py tests/integration/worker/test_deliver_webhook.py -v
```
Expected: green.

- [ ] **Step 4: Commit (ASK FIRST)**

```bash
git commit -am "test(worker): reaper + webhook tests use kwargs DI + ZSET assertions"
```

---

## Task 17: Adapt remaining unit tests

**Files:**
- Modify: `src/backend/tests/unit/api/v2/test_runs_enqueue.py`
- Modify: `src/backend/tests/unit/api/v1/test_webhook_distributed.py`

These exercise the API path that lands in `RunEnqueuer`. They likely instantiate the enqueuer (or call the endpoint that does). The changes in Task 6 already updated the constructor; this task confirms the test fixtures match.

- [ ] **Step 1: Inspect for arq fixtures**

```bash
grep -n "ArqRedis\|arq_pool\|enqueue_job" src/backend/tests/unit/api/v2/test_runs_enqueue.py src/backend/tests/unit/api/v1/test_webhook_distributed.py
```

- [ ] **Step 2: Replace each `ArqRedis` mock with a `dict[tier, InMemoryBroker]` fixture**

Pattern:

```python
from taskiq import InMemoryBroker

@pytest.fixture
def brokers_registry():
    return {
        "high": InMemoryBroker(),
        "default": InMemoryBroker(),
        "low": InMemoryBroker(),
    }
```

`enqueue_job` assertions become assertions on the relevant InMemoryBroker's queued messages.

- [ ] **Step 3: Run unit tests**

```bash
cd src/backend && uv run pytest tests/unit/api/v2/test_runs_enqueue.py tests/unit/api/v1/test_webhook_distributed.py -v
```
Expected: green.

- [ ] **Step 4: Commit (ASK FIRST)**

```bash
git commit -am "test(api): runs enqueue + webhook tests use InMemoryBroker"
```

---

## Task 18: Update KEDA ScaledObject template

**Files:**
- Modify: `deploy/helm/worker-starter/templates/worker-scaledobject.yaml`
- Modify: `deploy/helm/worker-starter/values.yaml` (if it references the old key pattern)

KEDA's `listName` was `arq:queue:<name>`. Taskiq's `ListQueueBroker` stores its list under `<queue_name>` directly (e.g. `runs:default`).

- [ ] **Step 1: Update the template**

In `deploy/helm/worker-starter/templates/worker-scaledobject.yaml` line 18, change:

```yaml
listName: "arq:queue:{{ .Values.worker.autoscaling.redis.queueName }}"
```

to:

```yaml
listName: "{{ .Values.worker.autoscaling.redis.queueName }}"
```

(Verify the actual Redis key Taskiq's `ListQueueBroker` writes by checking the running worker:
```bash
redis-cli KEYS '*' | sort
```
The list key should equal the `queue_name` parameter we passed. If the installed taskiq-redis prefixes the key, adjust the template to match.)

- [ ] **Step 2: Update default `values.yaml`**

If `values.yaml` documents the queue name with a comment about arq, update.

- [ ] **Step 3: Lint the chart**

```bash
helm lint deploy/helm/worker-starter
```
Expected: no errors.

- [ ] **Step 4: Commit (ASK FIRST)**

```bash
git commit -am "chore(deploy): KEDA ScaledObject targets Taskiq list key"
```

---

## Task 19: Add scheduler Helm Deployment

**Files:**
- Create: `deploy/helm/worker-starter/templates/scheduler-deployment.yaml`
- Modify: `deploy/helm/worker-starter/values.yaml` (add `scheduler` section)

Singleton Deployment running `langflow scheduler`. **Replicas: 1**, no autoscaling.

- [ ] **Step 1: Create the Deployment template**

```yaml
{{- if .Values.scheduler.enabled }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "langflow.fullname" . }}-scheduler
  labels:
    {{- include "langflow.labels" . | nindent 4 }}
    app.kubernetes.io/component: scheduler
spec:
  replicas: 1
  strategy:
    type: Recreate  # Singleton — never run two scheduler pods simultaneously
  selector:
    matchLabels:
      {{- include "langflow.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: scheduler
  template:
    metadata:
      labels:
        {{- include "langflow.labels" . | nindent 8 }}
        app.kubernetes.io/component: scheduler
    spec:
      containers:
        - name: scheduler
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          args: ["langflow", "scheduler"]
          env:
            {{- toYaml .Values.scheduler.env | nindent 12 }}
          resources:
            {{- toYaml .Values.scheduler.resources | nindent 12 }}
{{- end }}
```

- [ ] **Step 2: Add a `scheduler` section to `values.yaml`**

```yaml
scheduler:
  enabled: true
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 200m
      memory: 256Mi
  env: []
```

- [ ] **Step 3: Lint**

```bash
helm lint deploy/helm/worker-starter
helm template deploy/helm/worker-starter | grep -A3 'kind: Deployment' | head -40
```
Expected: scheduler Deployment renders.

- [ ] **Step 4: Commit (ASK FIRST)**

```bash
git add deploy/helm/worker-starter/templates/scheduler-deployment.yaml \
        deploy/helm/worker-starter/values.yaml
git commit -m "feat(deploy): add singleton scheduler Deployment"
```

---

## Task 20: Update `deploy/README.md`

**Files:**
- Modify: `deploy/README.md`

Document the third process type and the cutover steps.

- [ ] **Step 1: Add a "Scheduler" section**

Add (and adapt to existing structure) a section describing:

- The scheduler is a **singleton** (`replicas: 1`) — never scale it up.
- Responsibilities: cron jobs (reaper, retention, audit cleanup, pricing refresh) + delayed-enqueue draining.
- Failure mode if scheduler is down: cron jobs stop firing; in-flight delayed retries (auto-retry, webhook backoff) accumulate in the `delay:*` Redis ZSETs and resume when scheduler restarts.

- [ ] **Step 2: Update queue-name documentation**

Replace any reference to `arq:queue:<name>` Redis keys with the new `<queue_name>` keys.

- [ ] **Step 3: Add cutover steps**

Note the deployment order:
1. Build new image with Taskiq.
2. Deploy scheduler **first**.
3. Upgrade worker Deployment(s).
4. Upgrade API Deployment.
5. After cutover, drain any leftover `arq:queue:*` keys (`redis-cli DEL arq:queue:runs:high arq:queue:runs:default arq:queue:runs:low arq:queue:webhooks`).

- [ ] **Step 4: Commit (ASK FIRST)**

```bash
git commit -am "docs(deploy): document scheduler process and Taskiq cutover"
```

---

## Task 21: Remove the `arq` dependency, run full suites

**Files:**
- Modify: `src/backend/base/pyproject.toml` (remove `arq`)
- Generated: `uv.lock`, `src/backend/base/uv.lock`

Last task. Drop arq, regenerate the lock, run every test that touches the queue.

- [ ] **Step 1: Remove arq from `pyproject.toml`**

Delete the `"arq>=0.28,<0.29",` line.

- [ ] **Step 2: Refresh lockfile**

```bash
uv lock
```
Expected: arq removed from lockfile.

- [ ] **Step 3: Confirm no remaining arq imports**

```bash
grep -rn "from arq\|import arq\|arq\." src/backend src/lfx --include="*.py"
```
Expected: zero hits in source code (matches in `docs/superpowers/plans/*.md` and JSON fixtures are fine — the JSON files are starter project component data, not Python).

- [ ] **Step 4: Run the full backend test suite**

```bash
cd src/backend && uv run pytest tests/unit -x -q
cd src/backend && uv run pytest tests/integration/worker -x -q
```
Expected: all green.

- [ ] **Step 5: Smoke-test the full stack locally**

In three terminals (Redis already running):
```bash
# Terminal A
uv run langflow scheduler

# Terminal B
uv run langflow worker -q runs:default -q webhooks

# Terminal C
uv run langflow run --backend-only
```

Then `curl -X POST http://localhost:7860/api/v2/runs ...` and verify the run completes (DB row terminal state, webhook event, no errors in any log).

- [ ] **Step 6: Commit (ASK FIRST)**

```bash
git commit -am "chore(deps): drop arq — Taskiq migration complete"
```

---

## Self-Review Notes

**Spec coverage check:**

- ✓ Goals: async-native (TaskiqDepends), Redis broker (ListQueueBroker), no Postgres migrations, single PR, KEDA list-trigger preserved, settings rename — all covered (Tasks 2, 3, 5, 6, 18).
- ✓ Three process types — API (Tasks 5, 6), Worker (Task 12), Scheduler (Task 13).
- ✓ Component mapping — every file in the spec's mapping section has a task.
- ✓ Data flow delta — concurrency-cap requeue (Task 8), auto-retry (Task 8), webhook retry (Task 9), reaper cadence change (Task 10).
- ✓ Testing — InMemoryBroker for unit (Task 6, 17), real Redis for integration (Tasks 14-16).
- ✓ Rollout — single PR sequencing matches the implementation order.
- ✓ Deferred follow-ups — explicitly out of scope and not added as tasks.

**Placeholder scan:** No "TBD" / "TODO" / "implement later" left. A few "verify against installed Taskiq version" notes are deliberate — Taskiq's exact API surface for `with_broker`, `find_task`, scheduler lifecycle, and CLI runner has minor variation across patch versions, and pinning the plan to one version risks rot. The implementer will confirm at execution time.

**Type consistency:** `TIER_TO_BROKER` (Task 2) is referenced by Task 6 enqueuer; `_TIER_TO_QUEUE_NAME` constant in Task 8 / Task 9 / Task 10 used consistently. `worker_deps._set/_state/_clear` (Task 11) used by Task 14 fixture. `schedule_delayed_kick` / `drain_due_kicks` signatures stable across Tasks 7 → 8 → 9 → 13.

**Known judgement calls** (left for executor):

- Whether `RedisAsyncResultBackend` is wired now or skipped — kept now as a deferred-follow-up enabler, costs near zero.
- Whether `register_lifecycle()` is called once at import time or per-broker `@broker.on_event` decorator — both work; pick whichever matches the installed Taskiq idiom.
