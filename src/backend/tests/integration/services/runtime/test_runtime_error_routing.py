"""End-to-end: errors handled by ErrorHandler land as PARTIAL_SUCCESS with
FlowRun.error populated (via the in-memory _handled_errors list on Graph)."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_handled_error_yields_partial_success(graph_build_helper):
    """Single flaky component wired to an ErrorHandler — run should be PARTIAL_SUCCESS
    with one handled_errors entry."""
    flaky = graph_build_helper.add_flaky_component(
        name="Flaky", fail_count=99, error_output_enabled=True
    )
    handler = graph_build_helper.add_error_handler(max_attempts=1, alert_mode="Ignore")
    graph_build_helper.connect(flaky, "error", handler, "error_input")
    sink_normal = graph_build_helper.add_text_capture()
    graph_build_helper.connect(flaky, "result", sink_normal, "input")
    sink_gave_up = graph_build_helper.add_text_capture()
    graph_build_helper.connect(handler, "gave_up", sink_gave_up, "input")

    flow_run = await graph_build_helper.run()

    assert flow_run.status.value == "partial_success", (
        f"Expected partial_success, got {flow_run.status.value}"
    )
    assert flow_run.error is not None
    assert "handled_errors" in flow_run.error
    assert len(flow_run.error["handled_errors"]) == 1

    handled = flow_run.error["handled_errors"][0]
    assert "error_type" in handled
    assert "error_message" in handled
    assert handled["component_id"] == flaky._id
    # max_attempts=1 means 1 initial attempt + 1 retry = 2 total attempts
    assert handled["attempts"] == 2


@pytest.mark.asyncio
async def test_multiple_handled_errors_appended(graph_build_helper):
    """Two flaky components both fail; each wired to its own ErrorHandler.
    Both errors are recorded in handled_errors[]."""
    a = graph_build_helper.add_flaky_component(name="A", fail_count=99, error_output_enabled=True)
    b = graph_build_helper.add_flaky_component(name="B", fail_count=99, error_output_enabled=True)
    handler_a = graph_build_helper.add_error_handler(max_attempts=0, alert_mode="Ignore", name="handler_a")
    handler_b = graph_build_helper.add_error_handler(max_attempts=0, alert_mode="Ignore", name="handler_b")
    graph_build_helper.connect(a, "error", handler_a, "error_input")
    graph_build_helper.connect(b, "error", handler_b, "error_input")
    # Provide sinks for normal outputs (suppressed on error) and gave_up outputs.
    sink_a_normal = graph_build_helper.add_text_capture(name="sink_a_normal")
    sink_b_normal = graph_build_helper.add_text_capture(name="sink_b_normal")
    graph_build_helper.connect(a, "result", sink_a_normal, "input")
    graph_build_helper.connect(b, "result", sink_b_normal, "input")
    sink_a_gave_up = graph_build_helper.add_text_capture(name="sink_a_gave_up")
    sink_b_gave_up = graph_build_helper.add_text_capture(name="sink_b_gave_up")
    graph_build_helper.connect(handler_a, "gave_up", sink_a_gave_up, "input")
    graph_build_helper.connect(handler_b, "gave_up", sink_b_gave_up, "input")

    flow_run = await graph_build_helper.run()

    assert flow_run.status.value == "partial_success"
    assert flow_run.error is not None
    assert "handled_errors" in flow_run.error
    assert len(flow_run.error["handled_errors"]) == 2

    # Both entries should have component_id set
    component_ids = {entry["component_id"] for entry in flow_run.error["handled_errors"]}
    assert a._id in component_ids
    assert b._id in component_ids
