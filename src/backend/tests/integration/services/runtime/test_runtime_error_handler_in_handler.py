"""Cycle guard: exceptions inside ErrorHandler itself must NOT recurse via the
error-edge mechanism — the run falls through to FAILED.
"""
import pytest


@pytest.mark.asyncio
async def test_handler_invocation_raises_fails_the_run(graph_build_helper, monkeypatch):
    """Invocation guard: if _invoke_error_handler raises (e.g. something beyond
    its own internal try/except, or an edge case in a future refactor), the
    _try_handle_via_error_edge method must catch it, log it, and return None so
    the original exception is re-raised by the caller — run goes FAILED.

    Without this guard the exception from _invoke_error_handler would propagate
    through the except-block in astep and replace the original exception with a
    confusing 'handler exploded' error rather than the original component error.
    The guard ensures the run fails cleanly with the ORIGINAL error.
    """
    flaky = graph_build_helper.add_flaky_component(
        name="Flaky", fail_count=99, error_output_enabled=True
    )
    handler = graph_build_helper.add_error_handler(max_attempts=0, alert_mode="Ignore")
    graph_build_helper.connect(flaky, "error", handler, "error_input")
    sink_gave_up = graph_build_helper.add_text_capture()
    graph_build_helper.connect(handler, "gave_up", sink_gave_up, "input")

    # Patch _invoke_error_handler to RAISE (simulating a hard failure beyond
    # what the inner try/except covers).
    async def bad_invoke(handler_vertex, handler_component, payload):
        raise RuntimeError("handler exploded during invocation")

    monkeypatch.setattr(graph_build_helper._graph, "_invoke_error_handler", bad_invoke)

    flow_run = await graph_build_helper.run()

    # Run must go FAILED regardless of what the handler raised.
    assert flow_run.status.value == "failed"


@pytest.mark.asyncio
async def test_error_handler_vertex_as_failing_vertex_does_not_self_recover(
    graph_build_helper,
):
    """Entry guard: _try_handle_via_error_edge must return None immediately when
    the failing vertex is an ErrorHandler, preventing recursive handler-handles-
    handler routing.

    We inject a fake edge from HandlerA.error → HandlerB and then directly call
    _try_handle_via_error_edge with HandlerA's vertex_id.  Without the entry guard
    the runtime would route HandlerA's "failure" to HandlerB; with the guard it
    must return None immediately.
    """
    graph = graph_build_helper._graph
    handler_a = graph_build_helper.add_error_handler(
        name="HandlerA", max_attempts=0, alert_mode="Ignore"
    )
    handler_b = graph_build_helper.add_error_handler(
        name="HandlerB", max_attempts=0, alert_mode="Ignore"
    )
    handler_a_id = handler_a._id  # "handler_HandlerA"
    handler_b_id = handler_b._id

    # Manually insert a fake edge from HandlerA's "error" output to HandlerB so
    # that _find_error_edge() would find a routing target — without the entry
    # guard the runtime would proceed to invoke HandlerB.
    import dataclasses

    class _FakeHandle:
        def __init__(self, name: str):
            self.name = name

    @dataclasses.dataclass
    class _FakeEdge:
        source_id: str
        target_id: str
        source_handle: object

    fake_edge = _FakeEdge(
        source_id=handler_a_id,
        target_id=handler_b_id,
        source_handle=_FakeHandle("error"),
    )
    graph.edges.append(fake_edge)  # type: ignore[attr-defined]

    # Directly invoke _try_handle_via_error_edge with HandlerA's vertex_id,
    # simulating HandlerA being the "failing" vertex.
    sentinel_exc = RuntimeError("HandlerA blew up")
    result = await graph._try_handle_via_error_edge(handler_a_id, sentinel_exc)

    # Entry guard must return None — do NOT route to HandlerB.
    assert result is None, (
        f"Expected None (entry guard triggered) but got {result!r}; "
        "ErrorHandler failures must not be re-routed to another error edge."
    )
