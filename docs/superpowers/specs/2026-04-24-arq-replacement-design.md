# Replace Arq with Taskiq — Design

**Status:** Draft
**Date:** 2026-04-24
**Author:** bryced
**Branch:** platform-multi-tenant

## Problem

Arq, the asyncio Redis task queue currently powering distributed flow execution, is in maintenance-only mode. Continuing to depend on it locks us out of new features, ties us to a Redis client API that has not kept pace with the broader async ecosystem, and creates a long-tail risk that any real bug we hit will require us to fork or migrate under pressure. We should migrate proactively, while there is no incident forcing the timeline.

The current arq footprint is non-trivial:

- ~10 backend files import `arq` directly (worker app, runs service, CLI, tests).
- Three priority queues (`runs:high`, `runs:default`, `runs:low`) plus a `webhooks` queue.
- Four cron jobs embedded in the worker (`reap_lost_runs`, `retention_sweep`, `audit_cleanup`, `refresh_pricing_cache`).
- KEDA `ScaledObject` keys off arq's Redis list naming (`arq:queue:*`).
- Worker DI uses arq's `ctx` dict (db sessionmaker, storage, settings, redis).

## Goals

- Replace arq with a maintained, asyncio-native task queue while preserving the existing semantics of distributed flow execution: priority tiers, per-org concurrency caps, cancellation, heartbeats, reaper, auto-retry, webhook delivery.
- Land the swap as a single coordinated change. No long-lived dual-mode flag.
- Keep Redis as the broker (we already run it for concurrency counters and cancel signals).
- Leave Postgres schema untouched — zero migrations.
- Improve maintainability where the swap naturally enables it (typed enqueue API, FastAPI-style dependency injection in tasks).

## Non-goals

- Building Taskiq middleware (retry, prometheus, result backend) in this pass — tracked as deferred follow-ups.
- Fixing the pre-existing gap where a `queued` row whose enqueue silently failed is not reaped.
- Changing the priority tier model, queue names (semantically), or the per-org concurrency cap design.
- Removing Redis from the stack.

## Decision: Taskiq

We considered Taskiq, Celery, and Dramatiq. Taskiq is the right fit because the worker codebase is asyncio in a load-bearing way: `execute_run` runs a graph runner under `asyncio.wait_for(timeout)` alongside a cancel-watcher and a heartbeat task, all sharing one event loop and cooperatively cancelling each other.

- **Celery** is sync-first. Running our async tasks would mean either `asyncio.run()` per task (loses shared async pools, pays event-loop startup cost) or experimental `celery[async]` / gevent (well-known sharp edges with httpx + async SQLAlchemy). The ecosystem advantage doesn't outweigh the per-task impedance mismatch on every change to worker code.
- **Dramatiq** has the same sync-first issue with weaker async-extension story than Celery and a smaller community.
- **Taskiq** is async-native, supports Redis as a broker, ships a scheduler for cron, and provides FastAPI-style `Depends()` in tasks — which is a strict improvement over arq's untyped `ctx` dict. Smaller ecosystem than Celery, but the ergonomic and architectural match is closer to 1:1 with what we have.

## Architecture

Three process types built from one container image:

1. **API** (`langflow run`) — unchanged responsibilities. Imports the broker registry and calls `.kicker().with_broker(...).kiq(...)` to enqueue.
2. **Worker** (`langflow worker`) — pulls tasks from one or more brokers. Multiple replicas, behind KEDA.
3. **Scheduler** (`langflow scheduler`) — **new**. Singleton (one replica). Runs `TaskiqScheduler` with `LabelScheduleSource`; pushes cron jobs into the brokers on schedule. Replaces arq's in-worker `cron_jobs` list.

The scheduler is a separate process because we run multiple worker replicas, and embedding cron in every replica would multiply cron firings. A dedicated singleton matches the standard Taskiq/Celery-beat pattern.

### Broker topology

One `ListQueueBroker` instance per priority tier — explicit and type-safe vs arq's string-based `_queue_name`:

```
broker_high     → Redis list "runs:high"
broker_default  → Redis list "runs:default"
broker_low      → Redis list "runs:low"
broker_webhooks → Redis list "webhooks"
```

Workers launch with one or more brokers mounted (default-tier pods mount `broker_default`; a high-priority pod can mount `broker_high`, etc.). The enqueuer picks a broker via the existing `org.runs_priority_tier` lookup.

### What stays untouched

- Redis URL / connection (broker, concurrency counters, and cancel signals all share it).
- Postgres schema (`flow_runs`, `flow_run_logs`).
- Priority tier → queue mapping (`_TIER_TO_PRIORITY`, `_TIER_TO_QUEUE_ATTR`).
- KEDA scale-trigger type — still a Redis list; only the `listName` value changes.
- The internal logic of every worker task (execute, webhook, reaper, retention, audit cleanup, pricing refresh).

## Component Mapping

### New module — `langflow/worker_app/brokers.py`

Central broker registry. Defines the four `ListQueueBroker` instances, a shared `RedisAsyncResultBackend`, and a `TIER_TO_BROKER` map for the enqueuer.

### `services/runs/deps.py`

Pool-management functions go away. Brokers self-manage their connections; we wire `await broker.startup()` / `await broker.shutdown()` into the FastAPI lifespan. File shrinks to a lifespan helper.

### `services/runs/enqueue.py`

- Drop the `ArqRedis` parameter; inject the broker registry instead.
- Replace `await self.redis.enqueue_job("execute_run", str(run.id), _queue_name=queue)` with `await execute_run.kicker().with_broker(TIER_TO_BROKER[tier]).kiq(str(run.id))`.

### `worker_app/execute.py`

Biggest surgery, but **structural only** — the cancel-watcher, heartbeat, timeout, and graph-runner orchestration stay identical.

- Signature changes from `async def execute_run(ctx, run_id)` to `async def execute_run(run_id, sessionmaker=TaskiqDepends(...), storage=TaskiqDepends(...), settings=TaskiqDepends(...), redis=TaskiqDepends(...))`.
- `ctx["redis"]` / `ctx["arq"]` consumers become explicit deps.
- Concurrency-cap requeue and auto-retry use `.kicker().with_labels(delay=N).kiq(...)` instead of `_defer_by=N`.

### `worker_app/webhook.py`

- Same DI pattern.
- Retry-with-backoff loop unchanged; backoff enqueue uses `.kicker().with_labels(delay=...).kiq(...)`.

### `worker_app/reaper.py`, `retention.py`, `audit_cleanup.py`, `pricing_refresh.py`

Each currently an arq cron callable. Each becomes `@broker.task(schedule=[{"cron": "..."}])`. Schedule metadata lives on the task; `LabelScheduleSource` in the scheduler reads it.

### `worker_app/settings.py`

`WorkerSettings` class goes away. Replaced by:

- A registry that imports task modules to register their decorators with the brokers.
- Startup/shutdown via `@broker.on_event(TaskiqEvents.WORKER_STARTUP / WORKER_SHUTDOWN)` (wires `initialize_services()` and tears down).

### `cli/worker_cmd.py`

Invokes Taskiq's worker runner programmatically with the broker(s) selected by CLI flag.

### `cli/scheduler_cmd.py` (new)

Runs `TaskiqScheduler(brokers=[...], sources=[LabelScheduleSource(...)])`.

### Settings — `lfx/services/settings/base.py`

- `arq_high_queue` / `arq_default_queue` / `arq_low_queue` / `arq_webhooks_queue` → renamed to `queue_high` / `queue_default` / `queue_low` / `queue_webhooks`. No alias shim — single rename, one commit.
- `worker_concurrency` stays.
- `redis_url` stays. No new connection string needed.

### Tests

- `tests/integration/worker/conftest.py` — replace `ArqRedis` fixture with a broker-per-test fixture. `InMemoryBroker` for unit-level paths; real `ListQueueBroker` against the existing Redis container for integration paths.
- `tests/unit/services/runs/test_enqueue.py`, `tests/unit/api/v2/test_runs_enqueue.py`, `tests/unit/api/v1/test_webhook_distributed.py` — adapt to `kicker()` API; `InMemoryBroker` makes this minimal.

### Deploy

- `deploy/helm/worker-starter/templates/worker-scaledobject.yaml` — `listName` changes from `arq:queue:<name>` to the new Taskiq list key (matches `queue_name` in the broker).
- New `deploy/helm/worker-starter/templates/scheduler-deployment.yaml` — singleton Deployment, `replicas: 1`, entrypoint `langflow scheduler`.
- `deploy/README.md` — document the third process type.

### Dependencies

- Drop `arq>=0.28,<0.29` from `src/backend/base/pyproject.toml`.
- Add `taskiq[redis]` plus `taskiq-redis` (pinned to current stable line at implementation time).
- Lock files refreshed via `uv lock`.

## Data Flow & Error Handling — Delta from Today

The control flow of a queued run is structurally identical to today. Only the queueing primitives change.

- **Enqueue (API → broker):** API resolves org → tier → broker, calls `kicker().with_broker(...).kiq(...)`. Returns a `TaskiqResult` we ignore (DB row is the source of truth). Insert-then-enqueue order unchanged.
- **Worker pickup:** Identical (dequeue → status check → org concurrency check → set running → run graph → write terminal state). Concurrency-cap requeue uses `.with_labels(delay=REQUEUE_DELAY)` in place of `_defer_by`.
- **Cancellation:** Unchanged. Cancel signals live in dedicated Redis keys, not in the broker. The cancel-watcher in `execute_run` polls Redis directly via the injected client.
- **Heartbeat / reaper:** Heartbeat unchanged. Reaper is fired by the scheduler instead of by the in-worker cron; logic identical. **Cadence change:** arq supports sub-minute cron via its `second={0, 30}` field; Taskiq's default `LabelScheduleSource` is minute-resolution. The reaper drops to once per minute. Detection latency grows from ~60s worst-case to ~120s — still well under the heartbeat thresholds it acts on (`STALE_AFTER_SECONDS = 60`, plus a generous margin in downstream timeouts). If sub-minute cadence is later required, a custom `IntervalScheduleSource` is the escape hatch.
- **Auto-retry:** Backoff calculation unchanged. Re-enqueue uses `.with_labels(delay=backoff)`.
- **Webhook delivery + retry:** `deliver_webhook` enqueued via `broker_webhooks`. Internal retry loop unchanged.

### Error handling specific to Taskiq

- **Broker startup failure** at boot — fail loudly, matching arq's behavior (without Redis you cannot enqueue).
- **Mid-run broker disconnect** — Taskiq's Redis broker auto-reconnects; the cancel-watcher's separate Redis client also reconnects. No explicit retry plumbing needed.
- **Acknowledgement model** — `ListQueueBroker` is at-least-once via BLPOP, same as arq. If a worker crashes mid-task, the message is gone, and the heartbeat-based reaper recovers any `running` rows whose workers vanish. **No semantic change** versus today.

### Pre-existing gap (out of scope)

A `flow_runs` row left in `queued` status because enqueue silently failed will not be reaped today (the reaper only inspects `running` rows). This migration does not fix that. It is tracked as a deferred follow-up below.

## Testing

Two layers, mirroring the existing unit/integration split:

- **Unit tests** — `InMemoryBroker`. `kicker().kiq(...)` enqueues into an in-memory list; tests assert on enqueued tasks directly. No Redis required. This actually *reduces* infra vs today (some unit-ish tests currently still need a real Redis to construct `ArqRedis`).
- **Integration tests** (`src/backend/tests/integration/worker/`) — keep the real Redis container. Run the actual worker via `taskiq worker` in a subprocess, mirroring today's arq-worker subprocess pattern.

### Verification checklist (must pass before claiming done)

1. All `tests/integration/worker/` tests green against real Redis.
2. End-to-end: API enqueue → worker pickup → terminal state → webhook fires → DB row consistent.
3. Cron path: scheduler fires `reap_lost_runs`, worker actually executes it.
4. Concurrency-cap requeue path (delayed re-enqueue).
5. Auto-retry with backoff.
6. KEDA scale signal: push N items to the new list key, confirm the ScaledObject's query matches.

## Rollout

**Single coordinated swap.** No phased dual-mode.

Reasons:

- Arq and Taskiq use different Redis key schemas; there is no shared queue you can dual-read.
- Workers and the API must agree on the broker library, or the worker silently drops jobs.
- A feature-flagged "both at once" path costs more in code complexity than the swap saves in safety.

### Branch / PR shape

- Single PR on `platform-multi-tenant`.
- Implementation plan sequences the work for review-friendliness (brokers module → enqueuer → worker tasks → cron tasks → CLI → tests → deploy), but it lands as one merge.

### Cutover

- **Drain first:** stop API enqueueing, let in-flight runs finish, then swap the image.
- **Scheduler must exist before workers upgrade**, otherwise cron jobs (reaper, retention, audit cleanup, pricing refresh) silently stop firing.
- Anything stuck in `arq:queue:*` at cutover is lost. The heartbeat reaper recovers any `running` rows whose workers vanish. `queued` rows that never got picked up match the pre-existing gap above.

### Backout

Pure git-revert of the single PR.

- Redis keys do not collide (new names).
- Old arq state in Redis is harmless after revert.
- Postgres untouched.
- One manual step: undeploy the scheduler Deployment.

## Deferred Follow-ups

Tracked here for future planning. Not built in this migration.

1. **Retry middleware** — promote the hand-rolled retry/backoff in `execute_run` and `deliver_webhook` into a Taskiq middleware. Most likely near-term promotion.
2. **Prometheus middleware** — Taskiq ships one; would replace some of our manual metrics emission paths.
3. **Result backend persistence** — currently unused; if we want broker-side job-status polling without a DB hit, flip it on.
4. **Task chaining / pipelines** — for multi-step orchestration if a use case ever appears.
5. **Orphaned-`queued`-row reaper** — pre-existing gap; not Taskiq-specific. The reaper today only inspects `running` rows.

## Open Questions

None at design freeze. Implementation-time decisions (exact Taskiq version pin, scheduler pod resource sizing, KEDA `listName` template) are deferred to the implementation plan.
