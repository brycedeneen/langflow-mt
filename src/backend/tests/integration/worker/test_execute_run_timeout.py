"""Integration test: execute_run times out and records the correct terminal state."""
from __future__ import annotations
import asyncio
import pytest
from uuid import uuid4


@pytest.fixture
def timeout_ctx(worker_ctx):
    async def slow_runner(flow_data, flow_id, inputs):
        await asyncio.sleep(5)
        return {"nope": True}

    worker_ctx["graph_runner"] = slow_runner
    return worker_ctx


@pytest.fixture
async def seeded_short_timeout(engine_and_factory):
    """Like `seeded` but with timeout_seconds=1 on the FlowRun."""
    from langflow.services.database.models.organization.model import Organization
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy, RunStatus

    _, factory = engine_and_factory
    async with factory() as s:
        org = Organization(
            id=uuid4(),
            name="o-timeout",
            slug="o-timeout",
            runs_priority_tier="default",
            runs_max_concurrent=5,
        )
        s.add(org)
        await s.commit()

        flow = Flow(
            id=uuid4(),
            name="f-timeout",
            data={"nodes": [], "edges": []},
            organization_id=org.id,
            auto_retry=False,
            max_retries=3,
            timeout_seconds=600,
        )
        s.add(flow)
        await s.commit()

        run = FlowRun(
            id=uuid4(),
            organization_id=org.id,
            flow_id=flow.id,
            triggered_by=TriggeredBy.API,
            status=RunStatus.QUEUED,
            timeout_seconds=1,  # very short timeout
        )
        s.add(run)
        await s.commit()

        for r in (org, flow, run):
            await s.refresh(r)

    return {"org": org, "flow": flow, "run": run}


async def test_execute_run_times_out(engine_and_factory, seeded_short_timeout, timeout_ctx):
    from langflow.worker_app.execute import execute_run
    from langflow.services.database.models.flow_run.model import FlowRun

    await execute_run(timeout_ctx, str(seeded_short_timeout["run"].id))

    _, factory = engine_and_factory
    async with factory() as s:
        row = await s.get(FlowRun, seeded_short_timeout["run"].id)

    status = row.status.value if hasattr(row.status, "value") else row.status
    assert status == "timed_out"
    assert row.error is not None
    assert row.error.get("type") == "timeout"
    assert row.finished_at is not None
