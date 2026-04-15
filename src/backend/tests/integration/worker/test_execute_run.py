from __future__ import annotations
import asyncio
import pytest


async def test_execute_run_happy_path(engine_and_factory, seeded, worker_ctx):
    from langflow.worker_app.execute import execute_run
    from langflow.services.database.models.flow_run.model import FlowRun

    await execute_run(worker_ctx, str(seeded["run"].id))

    _, factory = engine_and_factory
    async with factory() as s:
        row = await s.get(FlowRun, seeded["run"].id)

    assert row.started_at is not None
    assert row.finished_at is not None

    status = row.status.value if hasattr(row.status, "value") else row.status
    assert status == "succeeded"

    # Webhook enqueued for run.started and run.succeeded = at least 2 calls
    assert worker_ctx["arq"].enqueue_job.call_count >= 2

    # Verify the result was stored inline
    assert row.result is not None
    assert row.error is None
