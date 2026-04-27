"""SSE events fired during a retry sequence reach the run-events stream.

Tests verify that _try_handle_via_error_edge emits the three lifecycle events:
  - vertex.retrying         — before each retry attempt
  - vertex.retry_succeeded  — when a retry attempt succeeds
  - vertex.retry_exhausted  — when all retries are exhausted

Field names are exactly what Task 9 set at each call site in base.py:
  vertex.retrying        → {vertex_id, retry_number, max_retries}
  vertex.retry_succeeded → {vertex_id, succeeded_on_attempt}
  vertex.retry_exhausted → {vertex_id, total_attempts}
"""
import pytest


@pytest.mark.asyncio
async def test_retrying_event_emitted_per_attempt(graph_build_helper):
    """vertex.retrying fires once before each retry; vertex.retry_exhausted fires once."""
    flaky = graph_build_helper.add_flaky_component(
        name="Flaky", fail_count=99, error_output_enabled=True
    )
    handler = graph_build_helper.add_error_handler(max_attempts=2, alert_mode="Ignore")
    graph_build_helper.connect(flaky, "error", handler, "error_input")

    # The graph scheduler needs a reachable terminal on both normal and error branches
    # so that it schedules flaky for execution at all.
    sink_normal = graph_build_helper.add_text_capture()
    graph_build_helper.connect(flaky, "result", sink_normal, "input")
    sink_gave_up = graph_build_helper.add_text_capture()
    graph_build_helper.connect(handler, "gave_up", sink_gave_up, "input")

    events = await graph_build_helper.run_capturing_events()

    retrying = [e for e in events if e["name"] == "vertex.retrying"]
    assert len(retrying) == 2, f"Expected 2 retrying events, got {len(retrying)}: {retrying}"
    assert retrying[0]["data"]["vertex_id"] == flaky._id
    assert retrying[0]["data"]["retry_number"] == 1
    assert retrying[0]["data"]["max_retries"] == 2
    assert retrying[1]["data"]["retry_number"] == 2

    exhausted = [e for e in events if e["name"] == "vertex.retry_exhausted"]
    assert len(exhausted) == 1, f"Expected 1 exhausted event, got {len(exhausted)}: {exhausted}"
    assert exhausted[0]["data"]["vertex_id"] == flaky._id
    assert exhausted[0]["data"]["total_attempts"] == 3  # original + 2 retries


@pytest.mark.asyncio
async def test_retry_succeeded_event_on_recovery(graph_build_helper):
    """vertex.retry_succeeded fires once when a retry attempt recovers."""
    flaky = graph_build_helper.add_flaky_component(
        name="Flaky", fail_count=2, error_output_enabled=True
    )
    handler = graph_build_helper.add_error_handler(max_attempts=3)
    graph_build_helper.connect(flaky, "error", handler, "error_input")
    # Sink on normal output for graph termination after retry success.
    sink = graph_build_helper.add_text_capture()
    graph_build_helper.connect(flaky, "result", sink, "input")

    events = await graph_build_helper.run_capturing_events()

    succeeded = [e for e in events if e["name"] == "vertex.retry_succeeded"]
    assert len(succeeded) == 1, f"Expected 1 succeeded event, got {len(succeeded)}: {succeeded}"
    assert succeeded[0]["data"]["vertex_id"] == flaky._id
    # fail_count=2 → fails on attempts 1 and 2, succeeds on attempt 3
    assert succeeded[0]["data"]["succeeded_on_attempt"] == 3

    retrying = [e for e in events if e["name"] == "vertex.retrying"]
    assert len(retrying) == 2, f"Expected 2 retrying events, got {len(retrying)}: {retrying}"

    # No exhaustion event — we recovered before running out of retries.
    exhausted = [e for e in events if e["name"] == "vertex.retry_exhausted"]
    assert len(exhausted) == 0, f"Expected 0 exhausted events, got {len(exhausted)}"
