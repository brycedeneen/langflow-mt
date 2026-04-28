"""Behavioral tests covering the cascade-delete extension for ``flow_tag``,
``job``, ``flow_run_log``, and the retention guarantees for ``flow_usage_daily``
and ``pro_service_quote``.

The original ``test_cascade_delete_flows.py`` behavioral suite predates these
tables joining the helper. Rather than retrofit those tests, this file builds
a richer fixture that populates rows in every flow-related child table, runs
``cascade_delete_flows``, then asserts:

* the three newly-cascaded tables (``flow_tag``, ``job``, ``flow_run_log``)
  drop to zero rows for the deleted flow,
* ``flow_run`` (already in the helper) still drops to zero, and
* the two retention tables (``flow_usage_daily`` and ``pro_service_quote``)
  keep their rows, matching the user's per-table billing/audit policy.

In-memory SQLite is reused from the existing suite. SQLite does not enforce
``ON DELETE CASCADE``/``SET NULL`` without ``PRAGMA foreign_keys=ON`` — that's
exactly the property under test, since the helper exists to compensate for
that gap on SQLite while staying correct on Postgres.
"""

from __future__ import annotations

import datetime as dt
import uuid
from uuid import uuid4

import pytest
from langflow.api.utils import cascade_delete_flows
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import FlowRun, RunStatus, TriggeredBy
from langflow.services.database.models.flow_run_log.model import FlowRunLog, LogLevel
from langflow.services.database.models.flow_usage_daily.model import FlowUsageDaily
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.database.models.pro_service_quote.model import ProServiceQuote, ProServiceQuoteStatus
from langflow.services.database.models.tag.model import FlowTag, Tag, TagColor
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, func, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #

_TEST_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000456")


@pytest.fixture
async def async_session():
    """Per-test in-memory SQLite ``AsyncSession``.

    Mirrors the fixture in ``test_cascade_delete_flows.py``. We deliberately do
    not enable ``PRAGMA foreign_keys=ON`` — the helper must explicitly delete
    children regardless of FK enforcement.
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


async def _make_flow(session: AsyncSession, *, name: str = "f") -> Flow:
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


async def _make_tag(session: AsyncSession, *, name: str) -> Tag:
    tag = Tag(name=name, color=TagColor.BLUE.value)
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return tag


async def _attach_extended_children(session: AsyncSession, flow_id: uuid.UUID) -> dict:
    """Attach one row in every extended child table for ``flow_id``.

    Covers all five tables called out in the cascade-delete gap analysis,
    regardless of whether they are slated for cascade or retention:

    * cascade: ``flow_tag``, ``job``, ``flow_run`` → ``flow_run_log``
    * retain: ``flow_usage_daily``, ``pro_service_quote``
    """
    # flow_tag (composite PK: flow_id + tag_id) — first attach a tag.
    tag = await _make_tag(session, name=f"t-{uuid4().hex[:6]}")
    flow_tag = FlowTag(flow_id=flow_id, tag_id=tag.id)
    session.add(flow_tag)

    # job — singular table name, indexed flow_id with no FK.
    job = Job(
        job_id=uuid4(),
        flow_id=flow_id,
        organization_id=_TEST_ORG_ID,
        status=JobStatus.QUEUED,
        type=JobType.WORKFLOW,
    )
    session.add(job)

    # flow_run + flow_run_log (grandchild via run_id FK).
    run = FlowRun(
        organization_id=_TEST_ORG_ID,
        flow_id=flow_id,
        triggered_by=TriggeredBy.API,
        status=RunStatus.SUCCEEDED,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    log = FlowRunLog(
        run_id=run.id,
        ts=dt.datetime.now(dt.timezone.utc),
        level=LogLevel.INFO,
        message="hello",
    )
    session.add(log)

    # flow_usage_daily (retention).
    usage = FlowUsageDaily(
        flow_id=flow_id,
        date=dt.date.today(),
        org_id=_TEST_ORG_ID,
        runs=1,
        run_seconds=10,
        tokens=100,
        cost_cents=5,
    )
    session.add(usage)

    # pro_service_quote (retention). Needs a synthetic requester user_id —
    # SQLite will not enforce the FK so a random UUID is fine.
    quote = ProServiceQuote(
        org_id=_TEST_ORG_ID,
        flow_id=flow_id,
        requester_user_id=uuid4(),
        status=ProServiceQuoteStatus.OPEN,
        estimated_minutes_low=30,
        estimated_minutes_high=60,
        headline_summary="test quote",
        narrative="test narrative",
        submitted_at=dt.datetime.now(dt.timezone.utc),
    )
    session.add(quote)

    await session.commit()
    return {
        "flow_tag": flow_tag,
        "job": job,
        "flow_run": run,
        "flow_run_log": log,
        "flow_usage_daily": usage,
        "pro_service_quote": quote,
    }


async def _count_for_flow(session: AsyncSession, model, flow_id: uuid.UUID) -> int:
    """Count rows in ``model`` whose ``flow_id`` column matches.

    For ``FlowRunLog`` (no flow_id column) the caller should use
    :func:`_count_for_run` instead.
    """
    return await session.scalar(
        select(func.count()).select_from(model).where(model.flow_id == flow_id)
    )


async def _count_for_run(session: AsyncSession, run_id: uuid.UUID) -> int:
    return await session.scalar(
        select(func.count()).select_from(FlowRunLog).where(FlowRunLog.run_id == run_id)
    )


# --------------------------------------------------------------------------- #
# Test                                                                        #
# --------------------------------------------------------------------------- #


async def test_cascade_handles_flow_tag_job_flow_run_log_and_retains_billing(
    async_session: AsyncSession,
):
    """Single-flow cascade closes the gap on flow_tag/job/flow_run_log; preserves billing rows."""
    flow = await _make_flow(async_session, name="ext")
    children = await _attach_extended_children(async_session, flow.id)
    run_id = children["flow_run"].id

    # Sanity: every child row was inserted.
    assert await _count_for_flow(async_session, FlowTag, flow.id) == 1
    assert await _count_for_flow(async_session, Job, flow.id) == 1
    assert await _count_for_flow(async_session, FlowRun, flow.id) == 1
    assert await _count_for_run(async_session, run_id) == 1
    assert await _count_for_flow(async_session, FlowUsageDaily, flow.id) == 1
    assert await _count_for_flow(async_session, ProServiceQuote, flow.id) == 1

    await cascade_delete_flows(async_session, [flow.id])

    # The flow itself is gone.
    assert (
        await async_session.scalar(
            select(func.count()).select_from(Flow).where(Flow.id == flow.id)
        )
        == 0
    )

    # Cascade tables: zero rows for the deleted flow.
    assert await _count_for_flow(async_session, FlowTag, flow.id) == 0, (
        "flow_tag rows must be removed by cascade_delete_flows"
    )
    assert await _count_for_flow(async_session, Job, flow.id) == 0, (
        "job rows must be removed by cascade_delete_flows"
    )
    assert await _count_for_flow(async_session, FlowRun, flow.id) == 0, (
        "flow_run rows must be removed by cascade_delete_flows"
    )
    assert await _count_for_run(async_session, run_id) == 0, (
        "flow_run_log rows must be removed (grandchild via run_id) by cascade_delete_flows"
    )

    # Retention tables: rows must survive.
    assert await _count_for_flow(async_session, FlowUsageDaily, flow.id) == 1, (
        "flow_usage_daily rows must be retained for billing/audit"
    )
    assert await _count_for_flow(async_session, ProServiceQuote, flow.id) == 1, (
        "pro_service_quote rows must be retained for financial-record retention"
    )


async def test_cascade_does_not_touch_other_flows_extended_tables(async_session: AsyncSession):
    """Deleting flow A leaves flow B's flow_tag/job/flow_run_log rows intact.

    Locks in chunked-IN behavior across the three new tables: only the rows
    whose flow_id matches the input list (or whose run_id descends from such
    a flow_run) should be affected.
    """
    flow_a = await _make_flow(async_session, name="iso-a")
    flow_b = await _make_flow(async_session, name="iso-b")
    a_children = await _attach_extended_children(async_session, flow_a.id)
    b_children = await _attach_extended_children(async_session, flow_b.id)

    await cascade_delete_flows(async_session, [flow_a.id])

    # A's extended-cascade children are gone.
    assert await _count_for_flow(async_session, FlowTag, flow_a.id) == 0
    assert await _count_for_flow(async_session, Job, flow_a.id) == 0
    assert await _count_for_flow(async_session, FlowRun, flow_a.id) == 0
    assert await _count_for_run(async_session, a_children["flow_run"].id) == 0

    # B is untouched.
    assert await _count_for_flow(async_session, FlowTag, flow_b.id) == 1
    assert await _count_for_flow(async_session, Job, flow_b.id) == 1
    assert await _count_for_flow(async_session, FlowRun, flow_b.id) == 1
    assert await _count_for_run(async_session, b_children["flow_run"].id) == 1
