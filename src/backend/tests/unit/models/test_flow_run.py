from langflow.services.database.models.flow_run.model import FlowRun, RunStatus, TriggeredBy


def test_flow_run_status_enum():
    assert {s.value for s in RunStatus} == {
        "queued", "running", "succeeded", "failed", "cancelled", "timed_out",
        "partial_success",
    }


def test_flow_run_triggered_by_enum():
    assert {t.value for t in TriggeredBy} == {"api", "webhook", "schedule", "mcp"}


def test_flow_run_fields():
    required = {
        "id", "organization_id", "flow_id", "triggered_by", "actor_id",
        "status", "priority", "inputs", "inputs_ref", "result", "result_ref",
        "error", "auto_retry", "max_retries", "attempt", "cancel_requested",
        "timeout_seconds", "worker_id", "heartbeat_at", "queued_at",
        "started_at", "finished_at", "webhook_delivery_state",
    }
    assert required.issubset(FlowRun.model_fields)


def test_run_status_includes_partial_success():
    from langflow.services.database.models.flow_run.model import RunStatus

    assert RunStatus.PARTIAL_SUCCESS.value == "partial_success"
    # Stays within column length=16 (the schema constraint).
    assert len(RunStatus.PARTIAL_SUCCESS.value) <= 16
