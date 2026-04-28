"""Tests for vertex param-build parallelization.

These tests pin the contract of `Vertex._build_each_vertex_in_params_dict`:

1. Ordering invariants — keys appear in `raw_params` insertion order; intra-list
   order in `list[Vertex]` inputs is preserved; dict sub-key order preserved.
2. Concurrency witness — independent upstream `get_result` awaits run
   concurrently, so the wallclock for K slow upstreams is closer to one
   upstream's latency than to K * latency.
3. Concurrency safety — running with many independent upstreams in one bin
   produces results equivalent to the serial baseline.

The tests build minimal stand-in upstream "vertices" (objects exposing the
`get_result` coroutine) and call the real method via the unbound descriptor on
`Vertex`, so we exercise the production code path without instantiating a full
`Vertex` (which requires a graph, parsed node data, etc.).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from lfx.graph.vertex.base import Vertex


class _StubParent(Vertex):
    """Vertex subclass that bypasses `__init__` for unit-testing.

    Holds only the attributes the parameter-resolution loop reads/writes.
    Real `Vertex.__init__` requires a graph and parsed node data we don't
    need for these tests.
    """

    def __new__(cls, *_args, **_kwargs):
        return object.__new__(cls)

    def __init__(self, raw_params: dict[str, Any]) -> None:
        # Skip Vertex.__init__ entirely.
        self.raw_params = raw_params
        # Pre-seed `params` to match the production invariant: dict slots are
        # initialized to {} (the legacy `_build_dict_and_update_params` writes
        # into `self.params[key][sub_key]`); other shapes mirror raw_params.
        self.params = {
            k: ({} if isinstance(v, dict) and not _is_list_of_stubs(v) else v) for k, v in raw_params.items()
        }
        self.updated_raw_params = False
        self.display_name = "test-parent"
        # Vertex.__eq__ reads `id` and `data`; populate stable defaults so
        # `value == self` comparisons (self-reference branch) don't AttributeError.
        self.id = "stub-parent"
        self.data = {}


def _make_parent(raw_params: dict[str, Any]) -> _StubParent:
    return _StubParent(raw_params)


def _is_list_of_stubs(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, _StubVertex) for v in value)


class _StubVertex(Vertex):
    """Minimal upstream vertex stand-in for parameter resolution tests.

    The production `_is_vertex` check uses `isinstance(value, Vertex)`, so this
    stub subclasses `Vertex` (and bypasses `__init__`) to satisfy that gate
    without paying the real construction cost.
    """

    def __new__(cls, *_args, **_kwargs):
        # Skip Vertex.__init__ entirely; we only need `get_result`.
        return object.__new__(cls)

    def __init__(self, result: Any, *, sleep: float = 0.0, label: str = "") -> None:
        # Intentionally do NOT call super().__init__: that requires a graph
        # and parsed node data we don't need for these unit tests.
        self._result = result
        self._sleep = sleep
        self.label = label
        self.start_event = asyncio.Event()
        self.finish_event = asyncio.Event()
        # See _StubParent: keep `id` / `data` populated so Vertex.__eq__ works.
        self.id = label or f"stub-{id(self)}"
        self.data = {}

    async def get_result(self, requester, target_handle_name=None):  # noqa: ARG002
        self.start_event.set()
        if self._sleep:
            await asyncio.sleep(self._sleep)
        self.finish_event.set()
        return self._result


# ---------------------------------------------------------------------------
# Ordering invariants (passes against both serial and parallel implementations)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_param_keys_preserve_raw_params_order() -> None:
    """`self.params` must reflect `raw_params` insertion order after the build."""
    a = _StubVertex("A")
    b = _StubVertex("B")
    c = _StubVertex("C")
    parent = _make_parent({"alpha": a, "beta": b, "gamma": c})

    await parent._build_each_vertex_in_params_dict()

    assert list(parent.params.keys()) == ["alpha", "beta", "gamma"]
    assert parent.params == {"alpha": "A", "beta": "B", "gamma": "C"}


@pytest.mark.asyncio
async def test_list_of_vertices_preserves_intra_list_order() -> None:
    """A `list[Vertex]` input must expose its results in declaration order."""
    first = _StubVertex("first", sleep=0.05)  # slow first
    second = _StubVertex("second", sleep=0.0)  # fast second
    parent = _make_parent({"multi_input": [first, second]})

    await parent._build_each_vertex_in_params_dict()

    assert parent.params["multi_input"] == ["first", "second"]


@pytest.mark.asyncio
async def test_dict_input_preserves_subkey_order_and_passthrough() -> None:
    """Dict inputs must preserve sub-key order; non-vertex slots pass through."""
    x = _StubVertex("X")
    y = _StubVertex("Y")
    parent = _make_parent({"mapping": {"x": x, "static": "literal", "y": y}})

    await parent._build_each_vertex_in_params_dict()

    assert list(parent.params["mapping"].keys()) == ["x", "static", "y"]
    assert parent.params["mapping"] == {"x": "X", "static": "literal", "y": "Y"}


@pytest.mark.asyncio
async def test_self_reference_is_dropped_from_params() -> None:
    """A vertex referencing itself in raw_params has the key deleted."""
    parent = _make_parent({"self_ref": None, "real": _StubVertex("R")})
    parent.raw_params["self_ref"] = parent  # `value == self` branch
    parent.params["self_ref"] = parent

    await parent._build_each_vertex_in_params_dict()

    assert "self_ref" not in parent.params
    assert parent.params["real"] == "R"


@pytest.mark.asyncio
async def test_plain_value_passthrough() -> None:
    """Non-vertex / non-collection values pass through unchanged."""
    parent = _make_parent({"name": "literal", "vertex": _StubVertex(42)})
    parent.updated_raw_params = True  # force the `elif key not in params` branch

    await parent._build_each_vertex_in_params_dict()

    assert parent.params["name"] == "literal"
    assert parent.params["vertex"] == 42
    assert parent.updated_raw_params is False  # reset flag


# ---------------------------------------------------------------------------
# Concurrency witness — proves the gather actually runs upstreams in parallel.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_independent_vertex_keys_run_concurrently() -> None:
    """Five independent single-vertex keys must NOT pay K * latency wallclock.

    Each upstream sleeps 50ms inside `get_result`. Serial wallclock is ~250ms;
    a correct gather lands closer to 50ms. We assert <0.20s tolerance to allow
    for CI jitter while still failing loudly on a regression to serial awaits.
    """
    sleep_s = 0.05
    upstreams = {f"k{i}": _StubVertex(i, sleep=sleep_s, label=f"k{i}") for i in range(5)}
    parent = _make_parent(dict(upstreams))

    start = time.perf_counter()
    await parent._build_each_vertex_in_params_dict()
    elapsed = time.perf_counter() - start

    assert parent.params == {f"k{i}": i for i in range(5)}
    assert elapsed < 0.20, f"upstreams ran serially: {elapsed:.3f}s (expected <0.20s)"


@pytest.mark.asyncio
async def test_concurrent_keys_overlap_via_event_witness() -> None:
    """Stronger witness: prove task B is mid-flight while A is still blocked.

    Pattern: upstream A awaits an `asyncio.Event` that the test only sets after
    confirming upstream B has already started. If the production loop is
    serial, A blocks first and B never starts — the test times out. If the
    loop gathers, A and B start concurrently, B's start_event fires, the test
    releases A's gate, and both finish.
    """
    release_a = asyncio.Event()
    a = _StubVertex("A")
    b = _StubVertex("B")

    async def a_get_result(requester, target_handle_name=None):  # noqa: ARG001
        a.start_event.set()
        await release_a.wait()
        return a._result

    a.get_result = a_get_result  # type: ignore[method-assign]

    parent = _make_parent({"a": a, "b": b})

    async def driver() -> None:
        # Wait until B has started, which only happens if the loop didn't
        # block on A. Then release A so the build can complete.
        await asyncio.wait_for(b.start_event.wait(), timeout=1.0)
        # B started while A was still awaiting release: that IS the witness.
        assert a.start_event.is_set(), "A must have started before B"
        assert not a.finish_event.is_set(), "A must still be blocked on the gate"
        release_a.set()

    await asyncio.gather(parent._build_each_vertex_in_params_dict(), driver())

    assert parent.params == {"a": "A", "b": "B"}


# ---------------------------------------------------------------------------
# Concurrency safety — racy input under gather still equals the serial baseline.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_many_independent_upstreams_match_serial_baseline() -> None:
    """50 independent single-vertex keys produce identical results to serial.

    Each upstream's `get_result` sleeps a random small amount so completion
    order is non-deterministic; the post-merge must still walk `raw_params` in
    insertion order and produce stable output.
    """
    n = 50
    rng_sleeps = [0.001 * (i % 7) for i in range(n)]  # 0..6ms staggered
    upstreams = {f"u{i:02d}": _StubVertex(i, sleep=rng_sleeps[i]) for i in range(n)}
    parent = _make_parent(dict(upstreams))

    await parent._build_each_vertex_in_params_dict()

    expected = {f"u{i:02d}": i for i in range(n)}
    assert parent.params == expected
    assert list(parent.params.keys()) == list(expected.keys())


@pytest.mark.asyncio
async def test_func_key_promotes_coroutine_after_merge() -> None:
    """`key == "func"` must still set `params["coroutine"]` post-merge.

    This is the subtle hazard called out in the plan: if two coroutines wrote
    `self.params["coroutine"]` from inside the gather, last-writer-wins would
    introduce a race. The merge must run synchronously after gather so the
    write is deterministic.
    """

    def sample_func(x):
        return x

    func_holder = _StubVertex(sample_func)
    parent = _make_parent({"func": func_holder})

    await parent._build_each_vertex_in_params_dict()

    assert parent.params["func"] is sample_func
    assert "coroutine" in parent.params
    assert callable(parent.params["coroutine"])


@pytest.mark.asyncio
async def test_first_upstream_failure_aborts_build_fast() -> None:
    """Fail-fast semantics: any upstream raising aborts the whole build.

    Mirrors `asyncio.gather`'s default behaviour and the pre-refactor
    serial loop's behaviour. Later upstreams may be cancelled mid-flight,
    which is documented as acceptable.
    """
    boom_msg = "upstream failed"

    class _Boom(_StubVertex):
        async def get_result(self, requester, target_handle_name=None):  # noqa: ARG002
            raise RuntimeError(boom_msg)

    bad = _Boom(None, label="bad")
    good = _StubVertex("ok", sleep=0.05)
    parent = _make_parent({"bad": bad, "good": good})

    with pytest.raises(RuntimeError, match="upstream failed"):
        await parent._build_each_vertex_in_params_dict()
