from __future__ import annotations
import asyncio
import pytest
from uuid import uuid4

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy, RunStatus
from langflow.services.database.models.organization.model import Organization

pytestmark = pytest.mark.asyncio


async def test_run_timeout_clamped_to_global_ceiling(worker_ctx, engine_and_factory):
    """A run that requests timeout > worker_max_run_timeout_seconds is clamped."""
    from langflow.worker_app import execute as exec_mod

    settings = worker_ctx["settings"]
    settings.worker_max_run_timeout_seconds = 1  # very tight ceiling for the test

    async def slow_runner(flow, triggered_by, inputs, actor_id):
        await asyncio.sleep(5.0)
        return {"ok": True}

    _, factory = engine_and_factory
    async with factory() as s:
        org = Organization(id=uuid4(), name="o", slug="o", runs_priority_tier="default", runs_max_concurrent=5)
        s.add(org)
        flow = Flow(id=uuid4(), name="f", data={"nodes": [], "edges": []}, organization_id=org.id, timeout_seconds=600)
        s.add(flow)
        await s.commit()
        run = FlowRun(
            id=uuid4(), organization_id=org.id, flow_id=flow.id, triggered_by=TriggeredBy.API,
            status=RunStatus.QUEUED,
            timeout_seconds=300,  # tenant request — must be clamped to 1s
        )
        s.add(run)
        await s.commit()
        await s.refresh(run)

    await exec_mod.execute_run(
        str(run.id),
        sessionmaker=worker_ctx["db_sessionmaker"],
        storage=worker_ctx["storage"],
        settings=settings,
        redis=worker_ctx["redis"],
        graph_runner=slow_runner,
    )

    async with factory() as s:
        finalised = await s.get(FlowRun, run.id)
    assert finalised.status == RunStatus.TIMED_OUT, finalised.error
