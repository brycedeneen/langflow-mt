"""Regression test: FAILED run with prior handled_errors retains them.

Fix 1 in the code-review pass changed the terminal writeback from:

    run.error = error_payload

to:

    merged = dict(run.error or {})
    merged.update(error_payload)
    run.error = merged

This ensures that if a graph run recorded handled errors (via
_record_handled_error) *before* hitting an unrecoverable exception, the
handled_errors list is preserved in the final FlowRun.error dict alongside
the terminal failure details.
"""
from __future__ import annotations

import asyncio
import pytest


async def test_failed_run_preserves_prior_handled_errors(engine_and_factory, seeded, worker_ctx):
    """A run that wrote handled_errors[] then raised a terminal exception should
    retain handled_errors in the final run.error dict."""
    from langflow.services.database.models.flow_run.model import FlowRun

    # Seed handled_errors into the DB row *before* the worker's terminal writeback
    # runs — simulating what _record_handled_error does during graph execution.
    handled_entry = {
        "component_id": "flaky_c1",
        "component_display_name": "Flaky Component",
        "error_type": "RuntimeError",
        "error_message": "Intentional failure #1",
        "stack_trace": "Traceback (most recent call last):\n  ...\nRuntimeError: Intentional failure #1",
        "attempts": 2,
        "alerted": True,
        "occurred_at": "2026-01-01T00:00:00+00:00",
    }

    _, factory = engine_and_factory
    async with factory() as s:
        run_row = await s.get(FlowRun, seeded["run"].id)
        run_row.error = {"handled_errors": [handled_entry]}
        await s.commit()

    # Graph runner that raises a terminal exception (simulates an unrecoverable
    # failure after some components already succeeded with handled errors).
    async def failing_runner(flow, triggered_by, inputs, actor_id):
        await asyncio.sleep(0.01)
        raise RuntimeError("unrecoverable downstream failure")

    worker_ctx["graph_runner"] = failing_runner

    from langflow.worker_app.execute import _execute_run_inner

    await _execute_run_inner(
        str(seeded["run"].id),
        sessionmaker=worker_ctx["db_sessionmaker"],
        storage=worker_ctx["storage"],
        settings=worker_ctx["settings"],
        redis=worker_ctx["redis"],
        graph_runner=failing_runner,
    )

    async with factory() as s:
        row = await s.get(FlowRun, seeded["run"].id)

    status = row.status.value if hasattr(row.status, "value") else row.status
    assert status == "failed"

    assert row.error is not None, "run.error must not be None for a FAILED run"

    # The terminal error fields should be present.
    assert row.error.get("type") == "RuntimeError"
    assert "unrecoverable downstream failure" in row.error.get("message", "")

    # The pre-existing handled_errors must be preserved (not overwritten).
    assert "handled_errors" in row.error, (
        "handled_errors was lost — the terminal writeback overwrote run.error instead of merging"
    )
    assert len(row.error["handled_errors"]) == 1
    assert row.error["handled_errors"][0]["component_id"] == "flaky_c1"
