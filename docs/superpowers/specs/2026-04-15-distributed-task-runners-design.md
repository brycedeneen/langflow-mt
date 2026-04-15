# Distributed Task Runners for Flow Execution — Design

**Status:** Draft
**Date:** 2026-04-15
**Author:** bryced

## Problem

Today, Langflow executes flows in-process inside the FastAPI server. A `POST /api/v1/run` blocks on the HTTP connection while the graph executes via asyncio. This limits throughput and multi-tenant capacity:

- A single API process serves both interactive (editor/playground) traffic and long-running automation/trigger traffic.
- No horizontal scale for flow execution independent of API.
- One tenant's heavy flow can starve others on the same process.
- No durable record of runs; nothing to poll or inspect after the fact.

There is an existing Celery scaffold (`worker.py`, `core/celery_app.py`, `CeleryBackend` in `services/task/service.py`, RabbitMQ + Redis + Flower in `deploy/docker-compose.yml`) but it is **not wired to flow execution** — only `test_celery()` and `build_vertex()` exist as tasks. The scaffold will be removed as part of this work.

## Goals

- Dispatch non-interactive flow runs (webhook, schedule, MCP) to a worker queue so they execute out-of-process.
- Horizontally scale workers independent of the API.
- Enforce per-tenant fairness (concurrency caps, priority tiers) to prevent noisy-neighbor issues.
- Durable run state that clients can poll and/or receive webhooks for.
- Same container image, separate entrypoints for API and worker. Runs on both docker-compose and Kubernetes (KEDA-based autoscaling).

## Non-goals (v1)

- Streaming tokens over queued runs (final-result-only for v1).
- Dedicated per-tenant worker pools (enterprise tier). The design leaves room for this as a future extension.
- OpenTelemetry tracing.
- UI for failed webhook deliveries (data is captured on the run row; no dedicated dashboard).
- Object-storage-backed logs (logs live in Postgres in v1).
- Migrating the existing `/api/v1/run` editor/playground endpoint. That stays in-process.

## Architecture Overview

Two process types built from one image:

- **API** (`langflow run`) — serves HTTP, authenticates, validates, enqueues jobs, exposes the runs API, delivers webhooks.
- **Worker** (`langflow worker`) — pulls from Arq/Redis, loads flow + tenant context, executes the graph, writes terminal state to Postgres, publishes events. Also runs the reaper cron internally.

**Queue technology:** [Arq](https://arq-docs.helpmanual.io/) (asyncio-native Redis queue). The existing Celery scaffold is removed. `arq` replaces `celery` in `pyproject.toml`.

**Infra:**
- Redis — Arq broker + per-tenant concurrency counters + cancel signals.
- Postgres — `flow_runs` and `flow_run_logs` tables (existing DB).
- Existing app DB for flows, tenants, secrets.

**Flow of a queued run:**

1. Client `POST /api/v2/runs` → API authenticates, resolves tenant, validates flow ownership, writes `flow_runs` row `status=queued`, enqueues Arq job `{run_id}`, returns `{run_id, status, queued_at}`.
2. Worker dequeues. Checks tenant concurrency; if at cap, re-enqueues with 5s delay.
3. Otherwise marks row `running`, sets `worker_id`, emits `run.started` webhook, loads flow + tenant context, runs the graph inside `asyncio.wait_for(..., timeout_seconds)`.
4. On terminal state, writes `result`/`error` (offloading >1 MB payloads to object storage), emits webhook, decrements concurrency counter.
5. Cancellation: `POST /runs/{id}/cancel` sets `cancel_requested=true` (in DB and pushed via Redis); worker's cancel-watcher task hard-cancels the execution task (no rollback).
6. Worker crash: reaper finds `running` rows with stale `heartbeat_at`, marks them `failed` with `error.type=worker_lost`, decrements counter, fires webhook, re-enqueues if `auto_retry=true`.

## Data Model

### `flow_runs`

| column | type | notes |
|---|---|---|
| `id` | UUID PK | run_id |
| `tenant_id` | UUID FK | tenant-scoped |
| `flow_id` | UUID FK | |
| `triggered_by` | enum | `api`, `webhook`, `schedule`, `mcp` |
| `actor_id` | UUID nullable | user id or api-key id |
| `status` | enum | `queued`, `running`, `succeeded`, `failed`, `cancelled`, `timed_out` |
| `priority` | smallint | derived from tenant tier |
| `inputs` | JSONB nullable | inlined when ≤1 MB |
| `inputs_ref` | text nullable | object-storage URI when offloaded |
| `result` | JSONB nullable | inlined when ≤1 MB |
| `result_ref` | text nullable | object-storage URI when offloaded |
| `error` | JSONB nullable | `{type, message, traceback?}` |
| `auto_retry` | bool | copied from flow at enqueue |
| `max_retries` | smallint | copied from flow at enqueue |
| `attempt` | smallint | retry attempt count (0-indexed) |
| `cancel_requested` | bool default false | |
| `timeout_seconds` | int | copied from flow |
| `worker_id` | text nullable | set when picked up |
| `heartbeat_at` | timestamptz nullable | updated ~every 15s while running |
| `queued_at` | timestamptz not null | |
| `started_at` | timestamptz nullable | |
| `finished_at` | timestamptz nullable | |
| `webhook_delivery_state` | JSONB | per-event: `{event: {status, last_attempt_at, attempts, last_response?}}` |

**Indexes:**
- `(tenant_id, status, queued_at)` — list/poll
- `(flow_id, queued_at DESC)` — per-flow history
- `(status, heartbeat_at)` — reaper scan
- `(status, finished_at)` — retention sweep

**Status transitions:** `queued → running → {succeeded | failed | cancelled | timed_out}`. Enforced at the application layer; backed by a CHECK constraint for known terminals.

**Size limits / payload offload:**
- `inputs` and `result` ≤ 1 MB stored inline as JSONB.
- Larger payloads written to object storage (`s3://…/runs/{run_id}/inputs.json` / `result.json`); row stores `*_ref` URI.
- Storage backend is the same one used by existing file-upload features (MinIO in compose, S3 in production).

**Retention:** hourly cron deletes runs with `finished_at < now() - 1 day` (and their associated `flow_run_logs` and object-storage artifacts). Retention window is configurable via settings.

### `flow_run_logs`

| column | type | notes |
|---|---|---|
| `id` | bigserial PK | |
| `run_id` | UUID FK → flow_runs.id ON DELETE CASCADE | |
| `ts` | timestamptz not null | |
| `level` | enum | `debug`, `info`, `warn`, `error` |
| `node_id` | text nullable | when attributable to a graph node |
| `message` | text | |
| `extra` | JSONB nullable | structured fields |

**Index:** `(run_id, ts)`.

**Log capture:** worker installs a log handler scoped to the running task that writes to `flow_run_logs` in batched inserts (e.g., every 500 ms or every 100 rows). Per-run size cap ~10 MB; overflow truncated with a marker row.

### `flows` additions

| column | type | notes |
|---|---|---|
| `webhook_url` | text nullable | |
| `webhook_secret` | text nullable | auto-generated on first URL set |
| `auto_retry` | bool default false | |
| `max_retries` | smallint default 3 | used when auto_retry is true |
| `timeout_seconds` | int default 600 | |

These may live in existing flow settings JSON instead of top-level columns — decision deferred to implementation based on current `flows` schema.

### `tenants` additions

| column | type | notes |
|---|---|---|
| `runs_max_concurrent` | smallint default 5 | per-tenant concurrency cap |
| `runs_priority_tier` | enum default `default` | `high`, `default`, `low` |

## Multi-tenancy & Fairness

**Queue layout:** three Arq queues — `runs:high`, `runs:default`, `runs:low`. Tenant tier selects the queue at enqueue time. Workers poll all three with weighted pulls (4:2:1 default, configurable) so low-tier jobs still make progress.

**Per-tenant concurrency cap:**
- Before execution, worker atomically checks & increments `tenant:running:{tenant_id}` in Redis via a Lua script against `runs_max_concurrent`.
- If at cap, worker re-enqueues the job to the back of its queue with a 5s delay, does not block.
- Decrement happens on terminal state or via reaper on worker loss.

**Tenant scoping:** workers load the flow and its dependencies (secrets, variables, files) using existing tenant-scoped queries. No new isolation primitives; correct scoping on every query is assumed from the existing multi-tenant work (`2026-04-14-multi-tenant-vertical-slice-design.md`).

**Future — dedicated pools:** a `queue_name` attribute on tenants would route enterprise tenants to `runs:tenant:{id}` with a dedicated worker Deployment listening only to that queue. Not built in v1; the queue abstraction supports it.

## API Surface

All new endpoints under `/api/v2/runs`. Tenant-scoped by auth context.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v2/runs` | Enqueue. Body: `{flow_id, inputs, tweaks?, priority_override?}`. Returns `{run_id, status, queued_at}`. |
| GET | `/api/v2/runs/{run_id}` | Fetch run. Returns full row minus internal fields. |
| GET | `/api/v2/runs` | List. Filters: `flow_id`, `status`, `since`, `until`. Cursor-paginated. |
| POST | `/api/v2/runs/{run_id}/cancel` | Idempotent. Sets `cancel_requested=true`. Returns current status. |
| GET | `/api/v2/runs/{run_id}/logs` | Paginated log fetch from `flow_run_logs`. |

**Backward compat:** `/api/v1/run` is unchanged and continues to execute in-process for the editor/playground.

## Webhooks

**Configuration:** per-flow via `webhook_url` + auto-generated `webhook_secret`. No per-request override in v1.

**Events:** `run.started`, `run.succeeded`, `run.failed`, `run.cancelled`, `run.timed_out`.

**Payload:**
```json
{
  "event": "run.succeeded",
  "run_id": "…",
  "flow_id": "…",
  "tenant_id": "…",
  "status": "succeeded",
  "inputs": {…} | null,
  "inputs_ref": "s3://…" | null,
  "result": {…} | null,
  "result_ref": "s3://…" | null,
  "error": null,
  "started_at": "…",
  "finished_at": "…",
  "attempt": 0
}
```

**Headers:**
- `X-Langflow-Signature: sha256=<hmac>` — HMAC-SHA256 of raw body, key = `webhook_secret`
- `X-Langflow-Event` — event name
- `X-Langflow-Delivery` — uuid per attempt
- `X-Langflow-Timestamp` — RFC3339

**Delivery:**
- Enqueued to a dedicated `webhooks` Arq queue, processed by the same worker fleet (separate queue binding).
- Retries: 6 attempts with exponential backoff — approximately `10s, 30s, 2m, 10m, 30m, 1h`.
- HTTP request timeout: 10s. Retries on connection errors, timeouts, and 5xx / 429 responses. 2xx is success; 4xx (non-429) is terminal failure (no retry).
- On final failure, state recorded in `flow_runs.webhook_delivery_state`; visible via `GET /runs/{id}`. No dedicated DLQ UI in v1.

## Worker Internals

**Entrypoint `langflow worker`:**
- Boots settings, opens DB and Redis pools, registers Arq functions, starts polling `runs:high`, `runs:default`, `runs:low`, `webhooks`.
- Concurrency: `LANGFLOW_WORKER_CONCURRENCY` (default 8) max in-flight jobs per process.

**Per-run task:**
1. Dequeue, load `flow_runs` row.
2. Acquire tenant concurrency slot (Lua script against Redis). If denied, re-enqueue with 5s delay and return.
3. Transition row to `running`, set `worker_id`, `started_at`, emit `run.started` webhook.
4. Start heartbeat task (updates `heartbeat_at` every 15s) and cancel-watcher task (polls `cancel_requested` every ~2s).
5. Offload `inputs` from object storage if `inputs_ref` is set, then materialize `Graph`.
6. `await asyncio.wait_for(graph.arun(...), timeout_seconds)`.
7. On success/failure/timeout/cancel: compute terminal state, offload `result` if >1 MB, write row, emit terminal webhook.
8. On `auto_retry=true` and retriable failure/timeout and `attempt < max_retries`: re-enqueue with exponential backoff (base 30s jittered), increment `attempt`, leave row at terminal state of the failed attempt (next attempt is a new row linked by `parent_run_id`? — deferred; v1 simply increments `attempt` in place on re-enqueue of the same row). *Open detail resolved in writing-plans phase.*
9. Always decrement the tenant concurrency counter in a `finally`.

**Reaper** (Arq cron, every 60s, runs inside worker process):
- Selects `flow_runs` where `status='running' AND heartbeat_at < now() - interval '60 seconds'`.
- For each: mark `failed` with `error.type='worker_lost'`, decrement tenant counter, emit webhook, re-enqueue if `auto_retry`.

**Retention** (Arq cron, hourly):
- Deletes `flow_runs` with `finished_at < now() - retention_interval` (default 1 day). `flow_run_logs` cascade. Object-storage artifacts deleted best-effort.

## Observability

**Metrics** exposed on `/metrics` (Prometheus) on both API and worker:
- `langflow_runs_total{status, tenant_id, flow_id}` — counter
- `langflow_run_duration_seconds{status, flow_id}` — histogram
- `langflow_queue_depth{queue}` — gauge (also used by KEDA)
- `langflow_active_runs{tenant_id}` — gauge
- `langflow_webhook_delivery_total{event, status}` — counter
- `langflow_worker_heartbeats_total` — counter

**Logs:** captured to `flow_run_logs` as described above.

**Tracing:** deferred.

## Deployment

**Image:** single Dockerfile, multiple CLI subcommands:
- `langflow run` — API (unchanged)
- `langflow worker` — Arq worker + internal reaper/retention crons

**docker-compose (self-hosted):**
- Services: `langflow` (API), `langflow-worker` (≥1 replicas), `postgres`, `redis`, `minio`.
- **Removed:** `rabbitmq`, `celeryworker`, `flower`.

**Kubernetes (helm):**
- New `worker` Deployment sharing the API's `ConfigMap` / `Secret`.
- `ScaledObject` (KEDA) using the Redis list-length scaler on `runs:*` queues. Bounds: `minReplicas: 1`, `maxReplicas: 10` (configurable).

## Migration & Rollout

1. **Ship dark:** merge the new `/api/v2/runs` endpoints and worker behind `LANGFLOW_DISTRIBUTED_EXECUTION=false`. No default change.
2. **Trigger wiring:** update webhook / schedule / MCP trigger paths to dispatch via `/api/v2/runs` when the flag is on; otherwise fall through to existing in-process path.
3. **Dogfood in staging** with the flag on; verify metrics, webhook delivery, cancel, timeout, reaper.
4. **Enable in production** via config flip.
5. **Follow-up PR:** remove Celery scaffold — `worker.py`, `core/celery_app.py`, `core/celeryconfig.py`, `CeleryBackend`, `celery` from `pyproject.toml`, `rabbitmq`/`celeryworker`/`flower` from compose. Keep `TaskService` abstraction if it still earns its keep with only `ArqBackend`; otherwise inline.

## Open Questions Deferred to Writing-Plans

- Whether `flows.webhook_*`, `auto_retry`, `max_retries`, `timeout_seconds` live as top-level columns or nested in an existing flow settings JSON — depends on current schema conventions.
- Retry semantics: re-enqueue same `flow_runs` row with `attempt++` vs. create a new child row per attempt linked by `parent_run_id`. Leaning toward in-place for v1 simplicity.
- Whether to keep `TaskService` abstraction once only Arq remains.

## Out of Scope / Future Work

- Streaming tokens over queued runs (Redis pubsub worker → API → client).
- Dedicated per-tenant worker pools (enterprise tier).
- OpenTelemetry tracing.
- UI for failed webhook deliveries (DLQ browser).
- Object-storage-backed logs (swap out of Postgres).
- Cross-region worker fleets.
