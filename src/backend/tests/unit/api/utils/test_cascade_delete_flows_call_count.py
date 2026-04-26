"""Synthetic call-count benchmark for the batched cascade-delete helper.

This is the substitute for the wall-clock perf capture originally listed as
Task 6 of the cascade-delete batching plan. The original task required a
running server with a populated dev Postgres, which can't be driven from the
CLI. Instead, we count ``session.exec`` invocations for the legacy
per-flow loop pattern versus the new batched helper across a handful of N's
and assert the round-trip count drops from ``O(N)`` to ``O(chunks)``.

The recording fake returns *no rows* on the trace SELECT (see
``_RecordingSession`` below) — that mirrors the typical production case
where most flows are never traced, so the conditional span DELETE inside
``_cascade_delete_flow_chunk`` is skipped. Result: a constant 7 statements
per chunk (4 child DELETEs + trace SELECT + trace DELETE + flow DELETE).

The helper imports here are the same surface ``cascade_delete_flow`` /
``cascade_delete_flows`` covered by the behavioral suite next door
(``test_cascade_delete_flows.py``); the fake-session pattern is also taken
from that file's ``test_chunking_at_batch_boundary`` test. We re-define a
small local copy rather than refactor a cross-test import — fakes are
test-local in this repo.
"""

from __future__ import annotations

import uuid
from typing import Sequence

import pytest

from langflow.api.utils import cascade_delete_flow, cascade_delete_flows


# --------------------------------------------------------------------------- #
# Recording fake session                                                      #
# --------------------------------------------------------------------------- #
#
# Mirrors the helper inside test_cascade_delete_flows.py::
# test_chunking_at_batch_boundary. The trace SELECT returns no rows so the
# helper's optional span DELETE is skipped — giving the documented 7-call
# count per chunk.


class _FakeResult:
    def __init__(self, rows: Sequence = ()):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)

    def scalars(self):
        return self


class _RecordingSession:
    """AsyncSession-shaped fake that records every ``exec`` invocation.

    Returns an empty ``_FakeResult`` for every statement, including the
    helper's trace-id SELECT — so the conditional span DELETE inside
    ``_cascade_delete_flow_chunk`` does not fire.
    """

    def __init__(self) -> None:
        self.exec_calls: list[str] = []

    async def exec(self, statement):
        self.exec_calls.append(str(statement))
        return _FakeResult([])

    async def commit(self):  # pragma: no cover - never asserted here
        return None

    async def rollback(self):  # pragma: no cover - never asserted here
        return None

    @property
    def call_count(self) -> int:
        return len(self.exec_calls)


# --------------------------------------------------------------------------- #
# Benchmark                                                                   #
# --------------------------------------------------------------------------- #


# Per chunk (<= _CASCADE_DELETE_BATCH_SIZE=500 ids) with no traces:
#   1. DELETE FROM message    WHERE flow_id IN (...)
#   2. DELETE FROM transaction WHERE flow_id IN (...)
#   3. DELETE FROM vertex_build WHERE flow_id IN (...)
#   4. DELETE FROM flow_version WHERE flow_id IN (...)
#   5. SELECT trace.id FROM trace WHERE flow_id IN (...)   (returns empty)
#   6. DELETE FROM trace      WHERE flow_id IN (...)
#   7. DELETE FROM flow       WHERE id      IN (...)
# = 7 statements per chunk.
_CALLS_PER_CHUNK_NO_TRACES = 7


@pytest.mark.parametrize("n_flows", [1, 10, 50, 100])
async def test_call_count_loop_vs_batched(n_flows: int, capsys: pytest.CaptureFixture) -> None:
    """Synthetic substitute for the wall-clock perf capture in the plan.

    Counts ``session.exec`` invocations for both the legacy per-flow loop
    pattern and the new batched ``cascade_delete_flows``. The batched call
    should issue a constant 7 statements per <=500-id chunk, regardless of N.
    """
    flow_ids = [uuid.uuid4() for _ in range(n_flows)]

    # Loop pattern: how every caller used to invoke cascade-delete prior to
    # T2 — once per flow. Under the post-T2 shim this still does N rounds of
    # the chunked helper, each with a 1-element id list, which is exactly the
    # pre-batching round-trip count.
    loop_session = _RecordingSession()
    for fid in flow_ids:
        await cascade_delete_flow(loop_session, fid)
    loop_call_count = loop_session.call_count

    # Batched pattern: single call with the full id list. With n_flows <= 500
    # and no traces this is exactly one chunk = 7 statements.
    batched_session = _RecordingSession()
    await cascade_delete_flows(batched_session, flow_ids)
    batched_call_count = batched_session.call_count

    expected_batched = _CALLS_PER_CHUNK_NO_TRACES
    assert batched_call_count == expected_batched, (
        f"batched: {batched_call_count} != {expected_batched}\n"
        f"calls:\n  - " + "\n  - ".join(batched_session.exec_calls)
    )

    expected_loop = n_flows * _CALLS_PER_CHUNK_NO_TRACES
    assert loop_call_count == expected_loop, (
        f"loop: {loop_call_count} != {expected_loop}"
    )

    # Surfaced via -s for the markdown notes capture.
    speedup = loop_call_count / batched_call_count
    print(
        f"\nn_flows={n_flows}: loop={loop_call_count} "
        f"batched={batched_call_count} speedup={speedup:.1f}x"
    )
