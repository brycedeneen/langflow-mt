from __future__ import annotations


def test_metrics_registered():
    from langflow.services.runs.metrics import (
        ACTIVE_RUNS,
        QUEUE_DEPTH,
        RUN_DURATION,
        RUNS_TOTAL,
        WEBHOOK_DELIVERY_TOTAL,
    )

    for m in (RUNS_TOTAL, RUN_DURATION, QUEUE_DEPTH, ACTIVE_RUNS, WEBHOOK_DELIVERY_TOTAL):
        assert m is not None


def test_runs_total_has_labels():
    from langflow.services.runs.metrics import RUNS_TOTAL

    # Should accept labels without error
    RUNS_TOTAL.labels(status="succeeded", flow_id="abc")
