from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

RUNS_TOTAL = Counter(
    "langflow_runs_total",
    "Total runs by terminal status",
    ["status", "flow_id"],
)
RUN_DURATION = Histogram(
    "langflow_run_duration_seconds",
    "Run duration in seconds",
    ["status", "flow_id"],
)
QUEUE_DEPTH = Gauge(
    "langflow_queue_depth",
    "Current queue depth",
    ["queue"],
)
ACTIVE_RUNS = Gauge(
    "langflow_active_runs",
    "Currently-running runs",
    ["organization_id"],
)
WEBHOOK_DELIVERY_TOTAL = Counter(
    "langflow_webhook_delivery_total",
    "Webhook delivery attempts by outcome",
    ["event", "status"],
)
PHASE_DURATION = Histogram(
    "langflow_worker_phase_duration_seconds",
    "Per-phase latency inside execute_run",
    ["phase"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30, 60, 300),
)
RUN_RETRY_EXHAUSTED_TOTAL = Counter(
    "langflow_worker_retry_exhausted_total",
    "Runs that ran out of auto-retry attempts and finalized in a failed state",
    ["status"],
)
WORKER_METERING_FAILURES_TOTAL = Counter(
    "langflow_worker_metering_failures_total",
    "Exceptions swallowed by the metering post-commit hook",
)
WORKER_GRACEFUL_SHUTDOWN_DURATION = Histogram(
    "langflow_worker_graceful_shutdown_seconds",
    "Time spent draining in-flight execute_run tasks during shutdown",
    buckets=(0.1, 0.5, 1, 5, 10, 30, 60, 120, 300),
)
