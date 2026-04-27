"""When all retries fail, ErrorHandler.dispatch_alert is called exactly once,
gave_up fires, and the run completes without raising (error was handled).
"""
import pytest


@pytest.mark.asyncio
async def test_retries_exhaust_fires_error_edge(graph_build_helper):
    flaky = graph_build_helper.add_flaky_component(
        name="Flaky",
        fail_count=99,  # always fails
        error_output_enabled=True,
    )
    handler = graph_build_helper.add_error_handler(max_attempts=2, alert_mode="Ignore")
    graph_build_helper.connect(flaky, "error", handler, "error_input")
    sink_normal = graph_build_helper.add_text_capture()
    graph_build_helper.connect(flaky, "result", sink_normal, "input")
    sink_gave_up = graph_build_helper.add_text_capture()
    graph_build_helper.connect(handler, "gave_up", sink_gave_up, "input")

    flow_run = await graph_build_helper.run()

    assert flaky.invocation_count == 3  # original + 2 retries
    assert handler.dispatch_alert_calls == 1
    assert sink_normal.captured is None  # normal output suppressed
    # gave_up fires; sink_gave_up receives the ErrorPayload
    assert sink_gave_up.captured is not None
