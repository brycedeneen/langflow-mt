"""Integration test: execute_run re-enqueues when per-org concurrency cap is full."""
from __future__ import annotations
import json
import pytest
from uuid import uuid4


@pytest.fixture
async def seeded_cap_1(engine_and_factory):
    """Like `seeded` but Organization has runs_max_concurrent=1."""
    from langflow.services.database.models.organization.model import Organization
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy, RunStatus

    _, factory = engine_and_factory
    async with factory() as s:
        org = Organization(
            id=uuid4(),
            name="o-cap1",
            slug="o-cap1",
            runs_priority_tier="default",
            runs_max_concurrent=1,
        )
        s.add(org)
        await s.commit()

        flow = Flow(
            id=uuid4(),
            name="f-cap1",
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
            timeout_seconds=30,
        )
        s.add(run)
        await s.commit()

        for r in (org, flow, run):
            await s.refresh(r)

    return {"org": org, "flow": flow, "run": run}


async def test_over_cap_requeues(engine_and_factory, seeded_cap_1, worker_ctx, redis_service):
    from langflow.services.runs.concurrency import OrgConcurrency
    from langflow.services.database.models.flow_run.model import FlowRun
    from langflow.worker_app.execute import execute_run

    # ensure real redis so the concurrency Lua script sees the pre-filled slot
    worker_ctx["redis"] = redis_service.client

    # Pre-fill the org's one concurrency slot so execute_run cannot acquire
    conc = OrgConcurrency(redis_service.client)
    acquired = await conc.try_acquire(seeded_cap_1["org"].id, limit=1)
    assert acquired, "pre-fill should succeed on a fresh key"

    await execute_run(
        str(seeded_cap_1["run"].id),
        sessionmaker=worker_ctx["db_sessionmaker"],
        storage=worker_ctx["storage"],
        settings=worker_ctx["settings"],
        redis=worker_ctx["redis"],
        graph_runner=worker_ctx["graph_runner"],
    )

    _, factory = engine_and_factory
    async with factory() as s:
        row = await s.get(FlowRun, seeded_cap_1["run"].id)

    status = row.status.value if hasattr(row.status, "value") else row.status
    assert status == "queued"  # should not have transitioned to running

    # execute_run should have scheduled a delayed kick of execute_run on
    # runs:default via the delay ZSET. Payload carries a UUID4 nonce, so
    # assert on `task` and `args` shape rather than full equality.
    items = await redis_service.client.zrange("delay:runs:default", 0, -1)
    decoded = [json.loads(i) for i in items]
    matches = [
        d for d in decoded
        if d.get("task") == "execute_run"
        and d.get("args") == [str(seeded_cap_1["run"].id)]
    ]
    assert len(matches) == 1
