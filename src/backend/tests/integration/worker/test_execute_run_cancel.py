"""Integration test: execute_run honours a Redis cancel signal."""
from __future__ import annotations
import asyncio
import pytest


@pytest.fixture
def slow_worker_ctx(worker_ctx, redis_service):
    async def slow_runner(flow_data, flow_id, inputs):
        await asyncio.sleep(30)  # long enough to be cancelled
        return {"should_not_reach": True}

    worker_ctx["graph_runner"] = slow_runner
    # worker_ctx already uses redis_service.client; ensure it is the real client
    # so that request_cancel and is_cancel_requested share state.
    worker_ctx["redis"] = redis_service.client
    return worker_ctx


async def test_execute_run_honors_cancel(engine_and_factory, seeded, slow_worker_ctx, redis_service):
    from langflow.worker_app.execute import execute_run
    from langflow.services.runs.cancel import request_cancel
    from langflow.services.database.models.flow_run.model import FlowRun

    # The cancel watcher polls every CANCEL_POLL_INTERVAL (2 s).
    # Wait long enough for execute_run to enter RUNNING and the watcher to start,
    # then set the cancel flag and let the watcher detect it within one poll cycle.
    async def _cancel():
        # Give the worker time to transition to RUNNING and start the cancel watcher
        await asyncio.sleep(0.5)
        await request_cancel(redis_service.client, seeded["run"].id)

    task = asyncio.create_task(execute_run(slow_worker_ctx, str(seeded["run"].id)))
    cancel_helper = asyncio.create_task(_cancel())
    await asyncio.gather(task, cancel_helper)

    _, factory = engine_and_factory
    async with factory() as s:
        row = await s.get(FlowRun, seeded["run"].id)

    status = row.status.value if hasattr(row.status, "value") else row.status
    assert status == "cancelled"
    assert row.finished_at is not None
