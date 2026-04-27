"""Conftest for graph-layer runtime integration tests.

These tests build Graph objects programmatically and run them via
async_start() without needing the full Langflow HTTP stack. We override
the parent-directory `_start_app` autouse fixture here (scoped to this
subdirectory only) so the `client` fixture (which spins up a full app
with a database) is NOT needed.

Putting the override in this sub-conftest (rather than the parent
services/conftest.py) ensures other tests in services/ (e.g.,
test_autosecrets_vault.py) continue to receive the real `_start_app`.
"""
from __future__ import annotations

import dataclasses
from enum import Enum
from typing import ClassVar
from uuid import uuid4

import pytest

from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.io import HandleInput, Output, StrInput


# ---------------------------------------------------------------------------
# Override the parent conftest's `_start_app` autouse fixture so that these
# tests do not require a running HTTP client or database.
# Scoped only to this subdirectory; does not affect services/ siblings.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _start_app():
    """No-op: graph runtime integration tests do not need the full app."""


# ---------------------------------------------------------------------------
# Minimal run-status enum (mirrors the Task 4 RunStatus; Task 10 will wire
# the real model).
# ---------------------------------------------------------------------------

class RunStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL_SUCCESS = "partial_success"


@dataclasses.dataclass
class FlowRunResult:
    """Thin stand-in for a FlowRun DB row, populated by graph_build_helper.run()."""

    status: RunStatus
    error: dict | None = None


# ---------------------------------------------------------------------------
# Test components
# ---------------------------------------------------------------------------

class FlakyComponent(Component):
    """Raises `RuntimeError` for the first `fail_count` invocations, then
    returns the string "ok".
    """

    display_name = "FlakyComponent"
    name = "FlakyComponent"
    error_output_enabled: ClassVar[bool] = True

    inputs = [
        StrInput(name="dummy", display_name="Dummy", value="", advanced=True),
    ]
    outputs = [
        Output(
            display_name="Result",
            name="result",
            types=["str"],
            method="run",
        ),
    ]

    # Set by the test before graph construction.
    _fail_count: int = 0
    invocation_count: int = 0
    dispatch_alert_calls: int = 0  # always 0; here for symmetry with ErrorHandlerWrapper

    def run(self) -> str:
        self.invocation_count += 1
        if self.invocation_count <= self._fail_count:
            raise RuntimeError(f"Intentional failure #{self.invocation_count}")
        return "ok"


class FlakyComponentTextOutput(Component):
    """Like FlakyComponent but output is named 'text' (not 'result').

    Used to verify that _suppress_normal_successors covers any output name,
    not just 'result'.
    """

    display_name = "FlakyComponentTextOutput"
    name = "FlakyComponentTextOutput"
    error_output_enabled: ClassVar[bool] = True

    inputs = [
        StrInput(name="dummy", display_name="Dummy", value="", advanced=True),
    ]
    outputs = [
        Output(
            display_name="Text",
            name="text",
            types=["str"],
            method="run",
        ),
    ]

    _fail_count: int = 0
    invocation_count: int = 0

    def run(self) -> str:
        self.invocation_count += 1
        if self.invocation_count <= self._fail_count:
            raise RuntimeError(f"Intentional failure #{self.invocation_count}")
        return "ok"


class TextCaptureComponent(Component):
    """Captures whatever string is routed into it, storing it in `captured`."""

    display_name = "TextCapture"
    name = "TextCapture"

    inputs = [
        HandleInput(
            name="input",
            display_name="Input",
            input_types=["str", "Message", "Text", "ErrorPayload"],
        ),
    ]
    outputs = [
        Output(
            display_name="Passthrough",
            name="passthrough",
            types=["str"],
            method="capture",
        ),
    ]

    captured: object = None

    def capture(self) -> str:
        self.captured = self.input
        return str(self.input) if self.input is not None else ""


# ---------------------------------------------------------------------------
# graph_build_helper fixture
# ---------------------------------------------------------------------------

class _GraphBuildHelper:
    """Thin programmatic graph builder for error-routing integration tests."""

    def __init__(self):
        self._graph = Graph()
        self._component_ids: dict[str, str] = {}  # name → vertex_id
        self._components: dict[str, object] = {}  # name → component object

    # -- component factories -------------------------------------------------

    def add_flaky_component(
        self,
        *,
        name: str,
        fail_count: int,
        error_output_enabled: bool = True,
    ) -> FlakyComponent:
        comp = FlakyComponent(_id=f"flaky_{name}")
        comp._fail_count = fail_count
        vid = self._graph.add_component(comp)
        self._component_ids[name] = vid
        self._components[name] = comp
        return comp

    def add_flaky_text_output_component(
        self,
        *,
        name: str,
        fail_count: int,
    ) -> FlakyComponentTextOutput:
        """Add a FlakyComponent variant whose normal output is named 'text'."""
        comp = FlakyComponentTextOutput(_id=f"flaky_text_{name}")
        comp._fail_count = fail_count
        vid = self._graph.add_component(comp)
        self._component_ids[name] = vid
        self._components[name] = comp
        return comp

    def add_error_handler(
        self,
        *,
        max_attempts: int = 3,
        alert_mode: str = "Ignore",
        name: str = "handler",
    ) -> "ErrorHandlerWrapper":
        from lfx.components.reliability.error_handler import ErrorHandler

        handler = ErrorHandler(
            _id=f"handler_{name}",
            max_attempts=max_attempts,
            alert_mode=alert_mode,
            backoff_strategy="None",  # no delay in tests
            base_delay_seconds=0.0,
            max_delay_seconds=0.0,
        )

        # Wrap with a spy that counts dispatch_alert calls.
        wrapper = ErrorHandlerWrapper(handler)
        vid = self._graph.add_component(handler)
        self._component_ids[name] = vid
        self._components[name] = wrapper
        return wrapper

    def add_text_capture(self, name: str | None = None) -> TextCaptureComponent:
        uid = name or f"capture_{uuid4().hex[:6]}"
        comp = TextCaptureComponent(_id=f"capture_{uid}")
        vid = self._graph.add_component(comp)
        self._component_ids[uid] = vid
        self._components[uid] = comp
        return comp

    # -- edge builder --------------------------------------------------------

    def connect(
        self,
        source: object,
        output_name: str,
        target: object,
        input_name: str,
    ) -> None:
        """Wire an output from `source` to an input on `target`."""
        source_id = source._id if hasattr(source, "_id") else source.get_id()
        if isinstance(target, ErrorHandlerWrapper):
            target_id = target._handler._id
        else:
            target_id = target._id if hasattr(target, "_id") else target.get_id()
        self._graph.add_component_edge(source_id, (output_name, input_name), target_id)

    # -- runner --------------------------------------------------------------

    async def run(self) -> FlowRunResult:
        """Run the graph and return a FlowRunResult reflecting success/failure.

        After execution, checks self._graph._handled_errors to determine whether
        the run should be SUCCEEDED or PARTIAL_SUCCESS, mirroring the worker-side
        terminal-status decision in execute.py.
        """
        try:
            results = [r async for r in self._graph.async_start()]
            last = results[-1] if results else None
            _ = last  # Finish check not needed; absence of exception means success.

            handled = list(self._graph._handled_errors)
            if handled:
                error_dict: dict | None = {"handled_errors": handled}
                return FlowRunResult(status=RunStatus.PARTIAL_SUCCESS, error=error_dict)
            return FlowRunResult(status=RunStatus.SUCCEEDED)
        except Exception as exc:  # noqa: BLE001
            return FlowRunResult(
                status=RunStatus.FAILED,
                error={"type": type(exc).__name__, "message": str(exc)},
            )


    async def run_capturing_events(self) -> list[dict]:
        """Like .run() but also returns all SSE events emitted during execution.

        Monkey-patches the Graph's _emit_sse_event to capture events into a list
        in addition to (conceptually) the real bus, then restores the original
        method whether or not the run raises.

        Returns:
            List of dicts with keys ``name`` (str) and ``data`` (dict), one
            entry per _emit_sse_event call made during the run.
        """
        captured: list[dict] = []
        original_emit = self._graph._emit_sse_event

        async def _capture(event_name: str, data: dict) -> None:
            captured.append({"name": event_name, "data": data})
            # Also call the original so real bus wiring runs in production.
            await original_emit(event_name, data)

        self._graph._emit_sse_event = _capture
        try:
            await self.run()
        finally:
            self._graph._emit_sse_event = original_emit
        return captured


class ErrorHandlerWrapper:
    """Thin spy wrapper around the real ErrorHandler component.

    Intercepts dispatch_alert to count calls without needing a notifier.
    """

    def __init__(self, handler):
        self._handler = handler
        self.dispatch_alert_calls = 0
        # Patch dispatch_alert with a spy.
        import functools

        original = handler.dispatch_alert

        @functools.wraps(original)
        async def spy_dispatch_alert(**kwargs):
            self.dispatch_alert_calls += 1
            # Don't actually dispatch — we have no notifier in tests.
            return None

        handler.dispatch_alert = spy_dispatch_alert

    @property
    def _id(self):
        return self._handler._id

    @property
    def max_attempts(self):
        return self._handler.max_attempts

    @property
    def invocation_count(self):
        # ErrorHandler itself doesn't fail; not needed but here for symmetry
        return 0


@pytest.fixture
def graph_build_helper():
    return _GraphBuildHelper()
