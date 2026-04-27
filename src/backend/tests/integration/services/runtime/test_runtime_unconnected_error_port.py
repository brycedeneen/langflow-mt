"""A component with error_output_enabled=True but no connected error edge
must behave exactly like today: exception kills the run.
"""
import pytest


@pytest.mark.asyncio
async def test_unconnected_error_port_falls_through_to_failed(graph_build_helper):
    boom = graph_build_helper.add_flaky_component(
        name="Boom",
        fail_count=99,
        error_output_enabled=True,
    )
    sink = graph_build_helper.add_text_capture()
    graph_build_helper.connect(boom, "result", sink, "input")
    # No error edge wired — must preserve today's behavior.

    flow_run = await graph_build_helper.run()

    assert flow_run.status.value == "failed"
    assert boom.invocation_count == 1  # no retry happened
