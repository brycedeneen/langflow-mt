import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4


@pytest.fixture
async def stale_running_run(engine_and_factory):
    from langflow.services.database.models.organization.model import Organization
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy, RunStatus

    _, factory = engine_and_factory
    async with factory() as s:
        org = Organization(id=uuid4(), name="o", slug="o", runs_priority_tier="default", runs_max_concurrent=5)
        s.add(org); await s.commit()
        flow = Flow(id=uuid4(), name="f", data={}, organization_id=org.id, auto_retry=False, max_retries=3, timeout_seconds=600)
        s.add(flow); await s.commit()
        old = datetime.now(timezone.utc) - timedelta(seconds=120)
        run = FlowRun(
            id=uuid4(), organization_id=org.id, flow_id=flow.id,
            triggered_by=TriggeredBy.API, status=RunStatus.RUNNING,
            started_at=old, heartbeat_at=old,
        )
        s.add(run); await s.commit()
        await s.refresh(run)
    return run


@pytest.mark.asyncio
async def test_reaper_marks_stale_running_failed(engine_and_factory, worker_ctx, stale_running_run):
    from langflow.worker_app.reaper import reap_lost_runs
    from langflow.services.database.models.flow_run.model import FlowRun

    await reap_lost_runs(worker_ctx)

    _, factory = engine_and_factory
    async with factory() as s:
        row = await s.get(FlowRun, stale_running_run.id)
    status = row.status.value if hasattr(row.status, "value") else row.status
    assert status == "failed"
    assert row.error and row.error.get("type") == "worker_lost"
    # Webhook enqueued
    calls = [c for c in worker_ctx["arq"].enqueue_job.call_args_list if c.args and c.args[0] == "deliver_webhook"]
    assert any("run.failed" in c.args for c in calls)
