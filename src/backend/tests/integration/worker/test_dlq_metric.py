from __future__ import annotations
import pytest
from uuid import uuid4

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy, RunStatus
from langflow.services.database.models.organization.model import Organization

pytestmark = pytest.mark.asyncio


async def test_retry_exhausted_counter_fires_when_retries_exhausted(worker_ctx, engine_and_factory):
    from langflow.worker_app import execute as exec_mod
    from langflow.services.runs.metrics import RUN_RETRY_EXHAUSTED_TOTAL

    _, factory = engine_and_factory

    async def failing_runner(*args, **kwargs):
        raise RuntimeError("boom")

    async with factory() as s:
        org = Organization(id=uuid4(), name="o", slug="o", runs_priority_tier="default", runs_max_concurrent=5)
        s.add(org)
        await s.commit()
        flow = Flow(id=uuid4(), name="f", data={"nodes": [], "edges": []}, organization_id=org.id, auto_retry=True, max_retries=1, timeout_seconds=600)
        s.add(flow)
        await s.commit()
        # attempt=1 == max_retries — i.e. this IS the last attempt.
        run = FlowRun(
            id=uuid4(), organization_id=org.id, flow_id=flow.id, triggered_by=TriggeredBy.API,
            status=RunStatus.QUEUED, timeout_seconds=30, auto_retry=True, max_retries=1, attempt=1,
        )
        s.add(run)
        await s.commit()
        await s.refresh(run)

    counter_label = RUN_RETRY_EXHAUSTED_TOTAL.labels(status="failed")
    before = counter_label._value.get()
    await exec_mod.execute_run(
        str(run.id),
        sessionmaker=worker_ctx["db_sessionmaker"],
        storage=worker_ctx["storage"],
        settings=worker_ctx["settings"],
        redis=worker_ctx["redis"],
        graph_runner=failing_runner,
    )
    after = counter_label._value.get()
    assert after == before + 1
