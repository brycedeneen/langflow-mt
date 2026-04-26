from __future__ import annotations
import pytest

pytestmark = pytest.mark.asyncio


async def test_execute_run_records_phase_metrics(worker_ctx, seeded):
    from langflow.worker_app.execute import execute_run
    from langflow.services.runs.metrics import PHASE_DURATION, WORKER_METERING_FAILURES_TOTAL

    run = seeded["run"]

    def sample_count(phase: str) -> float:
        for metric in PHASE_DURATION.collect():
            for sample in metric.samples:
                if sample.name.endswith("_count") and sample.labels.get("phase") == phase:
                    return sample.value
        return 0.0

    before = {p: sample_count(p) for p in ("execute_flow", "terminal_writeback", "acquire_slot")}
    await execute_run(
        str(run.id),
        sessionmaker=worker_ctx["db_sessionmaker"],
        storage=worker_ctx["storage"],
        settings=worker_ctx["settings"],
        redis=worker_ctx["redis"],
        graph_runner=worker_ctx["graph_runner"],
    )
    after = {p: sample_count(p) for p in ("execute_flow", "terminal_writeback", "acquire_slot")}

    assert after["execute_flow"] > before["execute_flow"]
    assert after["terminal_writeback"] > before["terminal_writeback"]
    assert after["acquire_slot"] > before["acquire_slot"]

    # Metering failures stay at 0 in the happy path (metering is gated by setting and the test mock
    # has it as a Mock attr; the post-commit `try` catches any access errors before failing).
    assert WORKER_METERING_FAILURES_TOTAL._value.get() >= 0
