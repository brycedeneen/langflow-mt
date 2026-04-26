# worker_app

Distributed flow-execution worker for Langflow, built on Taskiq + Redis.

Each broker maps to one Redis list queue:

| Queue            | Broker             | Workload                        |
|------------------|--------------------|---------------------------------|
| `runs:high`      | `broker_high`      | High-priority FlowRun execution |
| `runs:default`   | `broker_default`   | Default FlowRun execution + scheduled tasks (reaper, retention, queue_depth, audit_cleanup, pricing_refresh) |
| `runs:low`       | `broker_low`       | Low-priority FlowRun execution  |
| `webhooks`       | `broker_webhooks`  | Webhook delivery                |

A worker process consumes exactly one queue. Run multiple processes (`langflow worker -q runs:high` etc.) to drain several queues.

## Tunables (Settings → env)

All knobs read from `lfx.services.settings.base.Settings`. Set via `LANGFLOW_<UPPER>` env.

| Setting                              | Env                                          | Default                       | Notes |
|--------------------------------------|----------------------------------------------|-------------------------------|-------|
| `worker_heartbeat_interval_s`        | `LANGFLOW_WORKER_HEARTBEAT_INTERVAL_S`       | 15.0                          | Reaper threshold is 60s; keep <30s. |
| `worker_cancel_poll_interval_s`      | `LANGFLOW_WORKER_CANCEL_POLL_INTERVAL_S`     | 2.0                           | Lower = faster cancel, more Redis traffic. |
| `worker_requeue_delay_s`             | `LANGFLOW_WORKER_REQUEUE_DELAY_S`            | 5.0                           | Backoff when org concurrency cap hits. |
| `worker_log_flush_interval_s`        | `LANGFLOW_WORKER_LOG_FLUSH_INTERVAL_S`       | 0.5                           | RunLogSink flush cadence. |
| `worker_log_max_buffer`              | `LANGFLOW_WORKER_LOG_MAX_BUFFER`             | 100                           | RunLogSink in-memory rows. |
| `worker_max_run_timeout_seconds`     | `LANGFLOW_WORKER_MAX_RUN_TIMEOUT_SECONDS`    | 3600                          | Hard ceiling on per-run timeout. |
| `worker_retry_jitter_ratio`          | `LANGFLOW_WORKER_RETRY_JITTER_RATIO`         | 0.1                           | 0 disables jitter on retry backoff. |
| `worker_webhook_backoff_schedule_s`  | `LANGFLOW_WORKER_WEBHOOK_BACKOFF_SCHEDULE_S` | `[10,30,120,600,1800,3600]`   | Length = max delivery attempts. |
| `worker_shutdown_drain_timeout_s`    | `LANGFLOW_WORKER_SHUTDOWN_DRAIN_TIMEOUT_S`   | 30.0                          | Match k8s `terminationGracePeriodSeconds`. |

## Observability

Prometheus metrics (registered in `langflow.services.runs.metrics`):

- `langflow_runs_total{status,flow_id}` — terminal run counts.
- `langflow_run_duration_seconds{status,flow_id}` — whole-run latency.
- `langflow_active_runs{organization_id}` — currently-running gauge.
- `langflow_queue_depth{queue}` — populated every minute by `update_queue_depth` on `broker_default`.
- `langflow_worker_phase_duration_seconds{phase}` — per-phase latency inside `execute_run` (`acquire_slot`, `payload_offload_load`, `execute_flow`, `terminal_writeback`, `payload_offload_store`).
- `langflow_worker_retry_exhausted_total{status}` — runs that finalised after using their last retry attempt. Alert on this.
- `langflow_worker_metering_failures_total` — exceptions in the post-commit metering hook (previously logged-and-swallowed).
- `langflow_worker_graceful_shutdown_seconds` — drain duration on `WORKER_SHUTDOWN`.
- `langflow_webhook_delivery_total{event,status}` — webhook delivery outcomes.

## Multi-process workers

`langflow worker --concurrency N` spawns N child processes. Each child re-imports task modules (`execute`, `webhook`, `reaper`, `retention`, `audit_cleanup`, `pricing_refresh`, `queue_depth`) so `@broker.task` decorators register. Without this, child processes log `task ... is not found` for every job.

## Graceful shutdown

On `SIGTERM`, the worker waits `worker_shutdown_drain_timeout_s` for in-flight `execute_run` tasks. Tasks that complete in time write terminal state and release their org-concurrency slot. Tasks still running after the deadline are abandoned in place — the reaper picks them up within `STALE_AFTER_SECONDS` (60s, hardcoded).

## Auto-retry

Failed/timed-out runs with `auto_retry=True` and `attempt < max_retries` are requeued with exponential backoff: `min(30 * 2^(attempt-1), 1800)` seconds, multiplied by `1 + uniform(0, worker_retry_jitter_ratio)` to break thundering-herd patterns on synchronised failures. When retries are exhausted, `langflow_worker_retry_exhausted_total{status}` increments — wire your alert on that metric (no separate DLQ list; the FlowRun row is the source of truth).
