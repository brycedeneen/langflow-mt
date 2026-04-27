"""Two source components both wired to one shared ErrorHandler should each
get their own retry sequence and produce their own handled_errors entry.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_fan_in_two_sources_one_handler(graph_build_helper):
    a = graph_build_helper.add_flaky_component(name="A", fail_count=99, error_output_enabled=True)
    b = graph_build_helper.add_flaky_component(name="B", fail_count=99, error_output_enabled=True)
    handler = graph_build_helper.add_error_handler(max_attempts=1, alert_mode="Ignore")
    graph_build_helper.connect(a, "error", handler, "error_input")
    graph_build_helper.connect(b, "error", handler, "error_input")

    # Each source needs a sink for its normal output for graph traversal to work.
    sink_a = graph_build_helper.add_text_capture()
    sink_b = graph_build_helper.add_text_capture()
    graph_build_helper.connect(a, "result", sink_a, "input")
    graph_build_helper.connect(b, "result", sink_b, "input")
    # And a sink for the shared handler's gave_up output.
    sink_gave_up = graph_build_helper.add_text_capture()
    graph_build_helper.connect(handler, "gave_up", sink_gave_up, "input")

    flow_run = await graph_build_helper.run()

    assert flow_run.status.value == "partial_success"
    assert a.invocation_count == 2  # original + 1 retry
    assert b.invocation_count == 2
    handled = flow_run.error["handled_errors"]
    assert len(handled) == 2
    component_ids = {h["component_id"] for h in handled}
    assert component_ids == {a._id, b._id}
