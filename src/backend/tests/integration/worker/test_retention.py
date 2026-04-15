import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4


@pytest.fixture
async def very_old_finished_run(engine_and_factory):
    from langflow.services.database.models.organization.model import Organization
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy, RunStatus

    _, factory = engine_and_factory
    async with factory() as s:
        org = Organization(id=uuid4(), name="o", slug="o", runs_priority_tier="default", runs_max_concurrent=5)
        s.add(org); await s.commit()
        flow = Flow(id=uuid4(), name="f", data={}, organization_id=org.id)
        s.add(flow); await s.commit()
        # settings.run_retention_hours defaults to 24 — put finished_at 48h ago
        old = datetime.now(timezone.utc) - timedelta(hours=48)
        run = FlowRun(
            id=uuid4(), organization_id=org.id, flow_id=flow.id,
            triggered_by=TriggeredBy.API, status=RunStatus.SUCCEEDED,
            started_at=old - timedelta(minutes=1), finished_at=old,
        )
        s.add(run); await s.commit()
        await s.refresh(run)
    return run


@pytest.fixture
async def recent_finished_run(engine_and_factory):
    from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy, RunStatus
    from langflow.services.database.models.organization.model import Organization
    from langflow.services.database.models.flow.model import Flow

    _, factory = engine_and_factory
    async with factory() as s:
        # Reuse or create another org/flow
        org = Organization(id=uuid4(), name="o2", slug="o2", runs_priority_tier="default", runs_max_concurrent=5)
        s.add(org); await s.commit()
        flow = Flow(id=uuid4(), name="f2", data={}, organization_id=org.id)
        s.add(flow); await s.commit()
        recent = datetime.now(timezone.utc) - timedelta(minutes=10)
        run = FlowRun(
            id=uuid4(), organization_id=org.id, flow_id=flow.id,
            triggered_by=TriggeredBy.API, status=RunStatus.SUCCEEDED,
            started_at=recent - timedelta(seconds=5), finished_at=recent,
        )
        s.add(run); await s.commit()
        await s.refresh(run)
    return run


@pytest.mark.asyncio
async def test_retention_deletes_old_runs(engine_and_factory, worker_ctx, very_old_finished_run, recent_finished_run):
    from langflow.worker_app.retention import retention_sweep
    from langflow.services.database.models.flow_run.model import FlowRun

    await retention_sweep(worker_ctx)

    _, factory = engine_and_factory
    async with factory() as s:
        old_row = await s.get(FlowRun, very_old_finished_run.id)
        recent_row = await s.get(FlowRun, recent_finished_run.id)
    assert old_row is None
    assert recent_row is not None
