"""When a flaky component eventually succeeds, the run completes normally.

The error edge does NOT fire, retries are transparent at the component layer.
"""
import pytest


@pytest.mark.asyncio
async def test_flaky_component_recovers_via_retry(graph_build_helper):
    """Component raises twice then succeeds; ErrorHandler is wired but never fires."""
    flaky = graph_build_helper.add_flaky_component(
        name="Flaky",
        fail_count=2,  # raises on attempt 1 and 2, succeeds on attempt 3
        error_output_enabled=True,
    )
    handler = graph_build_helper.add_error_handler(max_attempts=3)
    graph_build_helper.connect(flaky, "error", handler, "error_input")
    sink = graph_build_helper.add_text_capture()
    graph_build_helper.connect(flaky, "result", sink, "input")

    flow_run = await graph_build_helper.run()

    assert flow_run.status.value == "succeeded"
    assert flaky.invocation_count == 3  # original + 2 retries = 3 total
    assert handler.dispatch_alert_calls == 0
    assert sink.captured == "ok"
