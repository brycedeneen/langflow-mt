"""Failing TDD unit tests for the batched ``cascade_delete_flows`` helper.

These tests are written *before* the helper exists in
``langflow.api.utils.core``. They MUST fail at collection time with an
``ImportError`` until Task 2 introduces the helper. Once Task 2 lands, the
suite should turn green without modification.

Test stack:
- In-memory SQLite engine + ``AsyncSession`` (``sqlmodel.ext.asyncio.session``).
- Fixture pattern copied from
  ``src/backend/tests/unit/services/database/models/membership/test_model.py``
  and ``src/backend/tests/unit/api/test_flows_org_isolation.py``.
- ``pyproject.toml`` sets ``asyncio_mode = "auto"`` so we don't decorate every
  test.
"""

from __future__ import annotations

import uuid
from typing import Sequence
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, func, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

# IMPORTANT: this import is the whole point of Task 1 — it MUST fail at
# collection time until Task 2 introduces ``cascade_delete_flows`` and the
# corresponding shim. Do NOT swap to a try/except guard, conditional import,
# or pytest.importorskip — the failure is the test signal.
from langflow.api.utils import cascade_delete_flow, cascade_delete_flows  # type: ignore[attr-defined]
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.traces.model import SpanTable, TraceTable
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
async def async_session():
    """Per-test in-memory SQLite ``AsyncSession``.

    Mirrors the pattern in ``test_flows_org_isolation.py`` /
    ``unit/services/database/models/membership/test_model.py``. We don't enable
    ``PRAGMA foreign_keys=ON`` because the production cascade helper itself
    runs against engines (e.g. SQLite without FK enforcement) where it must
    explicitly delete child rows.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


_TEST_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000123")


async def _make_flow(session: AsyncSession, *, name: str = "f") -> Flow:
    """Insert a Flow with the minimum required columns.

    ``organization_id`` is NOT NULL in the schema; SQLite does not enforce the
    FK so a synthetic UUID is fine.
    """
    flow = Flow(
        id=uuid4(),
        name=f"{name}-{uuid4().hex[:6]}",
        data={"nodes": [], "edges": []},
        organization_id=_TEST_ORG_ID,
    )
    session.add(flow)
    await session.commit()
    await session.refresh(flow)
    return flow


async def _attach_children(
    session: AsyncSession,
    flow_id: uuid.UUID,
    *,
    with_trace: bool = True,
) -> dict:
    """Attach one row in every cascade-relevant child table for ``flow_id``."""
    msg = MessageTable(
        flow_id=flow_id,
        organization_id=_TEST_ORG_ID,
        sender="user",
        sender_name="u",
        text="hi",
        session_id="s",
        files=[],
        category="message",
    )
    txn = TransactionTable(
        flow_id=flow_id,
        organization_id=_TEST_ORG_ID,
        vertex_id="v",
        status="ok",
    )
    vb = VertexBuildTable(
        id="v",
        flow_id=flow_id,
        organization_id=_TEST_ORG_ID,
        artifacts={},
        valid=True,
    )
    fv = FlowVersion(
        flow_id=flow_id,
        organization_id=_TEST_ORG_ID,
        data={"nodes": [], "edges": []},
        version_number=1,
    )
    session.add_all([msg, txn, vb, fv])

    trace = None
    span = None
    if with_trace:
        trace = TraceTable(name="t", flow_id=flow_id)
        session.add(trace)
        await session.commit()
        await session.refresh(trace)
        span = SpanTable(name="s", trace_id=trace.id)
        session.add(span)
    await session.commit()
    return {"message": msg, "transaction": txn, "vertex_build": vb, "flow_version": fv, "trace": trace, "span": span}


async def _count(session: AsyncSession, model) -> int:
    """Return ``COUNT(*)`` for ``model``."""
    return await session.scalar(select(func.count()).select_from(model))


# --------------------------------------------------------------------------- #
# Test 1: empty input is a no-op                                              #
# --------------------------------------------------------------------------- #


async def test_empty_input_is_noop(async_session: AsyncSession, mocker):
    """Passing an empty list must NOT issue any DELETE/SELECT against children."""
    spy = mocker.spy(async_session, "exec")
    await cascade_delete_flows(async_session, [])
    assert spy.call_count == 0, (
        f"Expected zero session.exec calls for empty flow_ids, got {spy.call_count}."
    )


# --------------------------------------------------------------------------- #
# Test 2: single-flow shim delegates to the batched helper                    #
# --------------------------------------------------------------------------- #


async def test_single_flow_delegates_through_shim(async_session: AsyncSession):
    """``cascade_delete_flow(s, id)`` must produce the same observable result
    as ``cascade_delete_flows(s, [id])``.

    We verify behavioral equivalence by running each path against an isolated
    flow + children set and asserting both paths leave zero rows behind for
    every child table.
    """
    flow_a = await _make_flow(async_session, name="shim-a")
    flow_b = await _make_flow(async_session, name="shim-b")
    await _attach_children(async_session, flow_a.id)
    await _attach_children(async_session, flow_b.id)

    # Path 1: shim
    await cascade_delete_flow(async_session, flow_a.id)
    # Path 2: batched helper with single id
    await cascade_delete_flows(async_session, [flow_b.id])

    # Both flows + all of their children should be gone.
    for model in (Flow, MessageTable, TransactionTable, VertexBuildTable, FlowVersion, TraceTable, SpanTable):
        assert await _count(async_session, model) == 0, (
            f"Expected 0 rows in {model.__name__} after both delete paths"
        )


# --------------------------------------------------------------------------- #
# Test 3: batch deletes wipe all child tables across multiple flows            #
# --------------------------------------------------------------------------- #


async def test_batch_deletes_in_correct_order(async_session: AsyncSession):
    f1 = await _make_flow(async_session, name="b1")
    f2 = await _make_flow(async_session, name="b2")
    f3 = await _make_flow(async_session, name="b3")
    for flow in (f1, f2, f3):
        await _attach_children(async_session, flow.id)

    # Sanity: rows present before the cascade.
    assert await _count(async_session, Flow) == 3
    assert await _count(async_session, MessageTable) == 3
    assert await _count(async_session, TransactionTable) == 3
    assert await _count(async_session, VertexBuildTable) == 3
    assert await _count(async_session, FlowVersion) == 3
    assert await _count(async_session, TraceTable) == 3
    assert await _count(async_session, SpanTable) == 3

    await cascade_delete_flows(async_session, [f1.id, f2.id, f3.id])

    for model in (Flow, MessageTable, TransactionTable, VertexBuildTable, FlowVersion, TraceTable, SpanTable):
        assert await _count(async_session, model) == 0, (
            f"Expected 0 rows in {model.__name__} after cascade_delete_flows"
        )


# --------------------------------------------------------------------------- #
# Test 4: batch with partial traces                                            #
# --------------------------------------------------------------------------- #


async def test_batch_with_partial_traces(async_session: AsyncSession):
    """Only some flows have traces; spans for those traces must be deleted and
    traceless flows still cleaned up."""
    f_with_trace_1 = await _make_flow(async_session, name="t1")
    f_with_trace_2 = await _make_flow(async_session, name="t2")
    f_no_trace = await _make_flow(async_session, name="nt")

    await _attach_children(async_session, f_with_trace_1.id, with_trace=True)
    await _attach_children(async_session, f_with_trace_2.id, with_trace=True)
    await _attach_children(async_session, f_no_trace.id, with_trace=False)

    assert await _count(async_session, TraceTable) == 2
    assert await _count(async_session, SpanTable) == 2

    await cascade_delete_flows(
        async_session,
        [f_with_trace_1.id, f_with_trace_2.id, f_no_trace.id],
    )

    for model in (Flow, MessageTable, TransactionTable, VertexBuildTable, FlowVersion, TraceTable, SpanTable):
        assert await _count(async_session, model) == 0, (
            f"Expected 0 rows in {model.__name__} after partial-trace cascade"
        )


# --------------------------------------------------------------------------- #
# Test 5: chunking at batch boundary                                           #
# --------------------------------------------------------------------------- #


async def test_chunking_at_batch_boundary(mocker):
    """501 ids must be processed in 2 chunks.

    The expected batch size is 500 (configurable in the helper). The helper is
    free to either:
      * expose a module-level ``CASCADE_DELETE_BATCH_SIZE`` constant we can
        introspect, OR
      * just emit DELETE statements per chunk in the production order.

    Either way, with 501 ids the SELECT ``trace_ids`` query (which is
    per-chunk) MUST fire exactly twice — once per chunk. We use that as our
    chunk-count probe.
    """
    flow_ids = [uuid4() for _ in range(501)]

    # Build a fake AsyncSession that records every ``exec`` call with the
    # compiled SQL string. We don't run real SQL — the helper should still
    # iterate through chunks and call ``exec`` per statement.
    class _FakeResult:
        def __init__(self, rows: Sequence = ()):
            self._rows = list(rows)

        def all(self):
            return list(self._rows)

        def scalars(self):
            return self

    class _RecordingSession:
        def __init__(self):
            self.exec_calls = []  # list of compiled-SQL strings

        async def exec(self, statement):
            self.exec_calls.append(str(statement))
            # Return an empty result for SELECTs so the helper's
            # ``trace_ids`` lookup yields no spans-to-delete.
            return _FakeResult([])

        async def commit(self):  # pragma: no cover - never asserted
            return None

        async def rollback(self):  # pragma: no cover - never asserted
            return None

    session = _RecordingSession()
    await cascade_delete_flows(session, flow_ids)

    # Count how many of the recorded statements target the trace SELECT.
    # The helper issues one trace-id SELECT per chunk; with 501 ids and a
    # batch size of 500 this is exactly 2.
    trace_select_count = sum(
        1 for s in session.exec_calls if "FROM trace" in s and "SELECT" in s.upper()
    )
    assert trace_select_count == 2, (
        f"Expected 2 trace-id SELECTs (one per chunk of 500), got {trace_select_count}.\n"
        f"All exec calls:\n  - " + "\n  - ".join(session.exec_calls)
    )


# --------------------------------------------------------------------------- #
# Test 6: chunking preserves dependency order within and across chunks         #
# --------------------------------------------------------------------------- #


async def test_chunking_preserves_dependency_order():
    """Within a chunk, span DELETE strictly precedes trace DELETE; across
    chunks, each chunk completes its own dependency order before the next
    chunk starts."""
    flow_ids = [uuid4() for _ in range(501)]

    class _FakeResult:
        def __init__(self, rows):
            self._rows = list(rows)

        def all(self):
            return list(self._rows)

        def scalars(self):
            return self

    class _RecordingSession:
        def __init__(self):
            self.exec_calls = []

        async def exec(self, statement):
            sql = str(statement)
            self.exec_calls.append(sql)
            # Each chunk's trace-id SELECT returns one synthetic trace id so
            # the helper actually emits a span DELETE for each chunk.
            if "FROM trace" in sql and "SELECT" in sql.upper():
                return _FakeResult([uuid4()])
            return _FakeResult([])

        async def commit(self):  # pragma: no cover
            return None

        async def rollback(self):  # pragma: no cover
            return None

    session = _RecordingSession()
    await cascade_delete_flows(session, flow_ids)

    # Find the position in the call log of every span-DELETE and trace-DELETE.
    span_delete_idxs = [
        i for i, s in enumerate(session.exec_calls)
        if s.upper().startswith("DELETE") and "FROM span" in s
    ]
    trace_delete_idxs = [
        i for i, s in enumerate(session.exec_calls)
        if s.upper().startswith("DELETE") and "FROM trace " in (s + " ")
    ]

    assert span_delete_idxs, "Expected at least one span DELETE"
    assert trace_delete_idxs, "Expected at least one trace DELETE"
    assert len(span_delete_idxs) == len(trace_delete_idxs) == 2, (
        "Expected exactly one span DELETE and one trace DELETE per chunk (2 chunks).\n"
        f"span_delete_idxs={span_delete_idxs} trace_delete_idxs={trace_delete_idxs}\n"
        f"All exec calls:\n  - " + "\n  - ".join(session.exec_calls)
    )

    # Within each chunk, span DELETE precedes trace DELETE.
    for chunk_idx, (sd, td) in enumerate(zip(span_delete_idxs, trace_delete_idxs)):
        assert sd < td, (
            f"Chunk #{chunk_idx}: span DELETE at index {sd} must precede trace "
            f"DELETE at index {td}."
        )

    # Across chunks: chunk-0's trace DELETE precedes chunk-1's span DELETE.
    assert trace_delete_idxs[0] < span_delete_idxs[1], (
        "Chunk-0 must finish its trace DELETE before chunk-1 begins its span DELETE."
    )


# --------------------------------------------------------------------------- #
# Test 7: partial failure rolls back the whole batch                           #
# --------------------------------------------------------------------------- #


async def test_partial_failure_rolls_back_whole_batch(async_session: AsyncSession, mocker):
    """If a child DELETE raises mid-cascade, the flow rows must remain and the
    error must propagate (wrapped in ``RuntimeError`` per the existing helper
    contract)."""
    f1 = await _make_flow(async_session, name="rb1")
    f2 = await _make_flow(async_session, name="rb2")
    await _attach_children(async_session, f1.id, with_trace=True)
    await _attach_children(async_session, f2.id, with_trace=True)

    # Snapshot the real ``exec`` and patch it to raise the first time it is
    # asked to delete from the ``trace`` table. Earlier child deletes (message,
    # transaction, vertex_build, flow_version, span) are allowed to run; the
    # outer transaction is what matters.
    real_exec = async_session.exec
    triggered = {"raised": False}

    async def faulty_exec(statement):
        sql = str(statement)
        if (
            not triggered["raised"]
            and sql.upper().startswith("DELETE")
            and "FROM trace " in (sql + " ")
        ):
            triggered["raised"] = True
            msg = "synthetic trace-delete failure"
            raise RuntimeError(msg)
        return await real_exec(statement)

    mocker.patch.object(async_session, "exec", side_effect=faulty_exec)

    with pytest.raises(RuntimeError):
        await cascade_delete_flows(async_session, [f1.id, f2.id])

    # Restore the original exec so post-mortem assertions can run.
    mocker.stopall()
    await async_session.rollback()

    # Both flow rows must still be present (rollback must have fired before
    # the flow DELETE, since the raise happened earlier in the dependency
    # chain).
    assert await _count(async_session, Flow) == 2, (
        "Expected both flows to survive a mid-batch failure (rollback)."
    )


# --------------------------------------------------------------------------- #
# Test 8: unrelated flows are untouched                                        #
# --------------------------------------------------------------------------- #


async def test_unrelated_flows_untouched(async_session: AsyncSession):
    """Flow A is in scope, flow B is not; deleting A leaves B + B's children
    fully intact."""
    flow_in_scope = await _make_flow(async_session, name="in-scope")
    flow_out_of_scope = await _make_flow(async_session, name="out-of-scope")
    await _attach_children(async_session, flow_in_scope.id, with_trace=True)
    await _attach_children(async_session, flow_out_of_scope.id, with_trace=True)

    await cascade_delete_flows(async_session, [flow_in_scope.id])

    # Flow A (in scope) and its children — gone.
    assert (
        await async_session.scalar(
            select(func.count()).select_from(Flow).where(Flow.id == flow_in_scope.id)
        )
        == 0
    )
    assert (
        await async_session.scalar(
            select(func.count()).select_from(MessageTable).where(MessageTable.flow_id == flow_in_scope.id)
        )
        == 0
    )

    # Flow B (out of scope) and its children — still present.
    assert (
        await async_session.scalar(
            select(func.count()).select_from(Flow).where(Flow.id == flow_out_of_scope.id)
        )
        == 1
    )
    for model in (MessageTable, TransactionTable, VertexBuildTable, FlowVersion, TraceTable):
        cnt = await async_session.scalar(
            select(func.count()).select_from(model).where(model.flow_id == flow_out_of_scope.id)
        )
        assert cnt == 1, f"Expected 1 surviving {model.__name__} for out-of-scope flow"

    # SpanTable is keyed by trace_id, so we have to count spans whose trace
    # belongs to the surviving flow.
    surviving_trace_ids = (
        await async_session.exec(
            select(TraceTable.id).where(TraceTable.flow_id == flow_out_of_scope.id)
        )
    ).all()
    assert len(surviving_trace_ids) == 1
    span_cnt = await async_session.scalar(
        select(func.count()).select_from(SpanTable).where(SpanTable.trace_id == surviving_trace_ids[0])
    )
    assert span_cnt == 1, "Expected the out-of-scope flow's span to survive"
