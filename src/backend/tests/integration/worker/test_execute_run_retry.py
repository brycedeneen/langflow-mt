"""Integration test: execute_run auto-retries by re-enqueuing with incremented attempt."""
from __future__ import annotations
import json
import pytest
from uuid import uuid4


@pytest.fixture
def failing_ctx(worker_ctx):
    async def bad_runner(*a, **kw):
        raise RuntimeError("boom")

    worker_ctx["graph_runner"] = bad_runner
    return worker_ctx


@pytest.fixture
async def seeded_retry(engine_and_factory):
    """Like `seeded` but FlowRun has auto_retry=True, max_retries=3, attempt=0."""
    from langflow.services.database.models.organization.model import Organization
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy, RunStatus

    _, factory = engine_and_factory
    async with factory() as s:
        org = Organization(
            id=uuid4(),
            name="o-retry",
            slug="o-retry",
            runs_priority_tier="default",
            runs_max_concurrent=5,
        )
        s.add(org)
        await s.commit()

        flow = Flow(
            id=uuid4(),
            name="f-retry",
            data={"nodes": [], "edges": []},
            organization_id=org.id,
            auto_retry=True,
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
            timeout_seconds=30,
            auto_retry=True,
            max_retries=3,
            attempt=0,
        )
        s.add(run)
        await s.commit()

        for r in (org, flow, run):
            await s.refresh(r)

    return {"org": org, "flow": flow, "run": run}


async def test_auto_retry_reenqueues(engine_and_factory, seeded_retry, failing_ctx):
    from langflow.worker_app.execute import execute_run
    from langflow.services.database.models.flow_run.model import FlowRun

    await execute_run(
        str(seeded_retry["run"].id),
        sessionmaker=failing_ctx["db_sessionmaker"],
        storage=failing_ctx["storage"],
        settings=failing_ctx["settings"],
        redis=failing_ctx["redis"],
        graph_runner=failing_ctx["graph_runner"],
    )

    _, factory = engine_and_factory
    async with factory() as s:
        row = await s.get(FlowRun, seeded_retry["run"].id)

    status = row.status.value if hasattr(row.status, "value") else row.status
    assert status == "queued"
    assert row.attempt == 1
    assert row.error is None   # reset on re-queue per execute_run logic
    assert row.result is None
    assert row.started_at is None
    assert row.finished_at is None

    # A new execute_run kick should have been scheduled in the delay ZSET
    # for queue runs:default. Payload includes a UUID4 nonce per delayed_enqueue
    # contract — assert on `task` and `args`, not full equality.
    items = await failing_ctx["redis"].zrange("delay:runs:default", 0, -1)
    decoded = [json.loads(i) for i in items]
    matches = [
        d for d in decoded
        if d.get("task") == "execute_run"
        and d.get("args") == [str(seeded_retry["run"].id)]
    ]
    assert len(matches) >= 1
