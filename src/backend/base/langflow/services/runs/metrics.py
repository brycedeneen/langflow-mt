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
