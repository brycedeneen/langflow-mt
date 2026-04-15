from __future__ import annotations
import asyncio
import pytest
from contextlib import asynccontextmanager
from uuid import uuid4

from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
async def engine_and_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def factory():
        async with sm() as s:
            yield s

    yield engine, factory
    await engine.dispose()


@pytest.fixture
async def seeded_run(engine_and_factory):
    from langflow.services.database.models.organization.model import Organization
    from langflow.services.database.models.flow_run.model import FlowRun, TriggeredBy, RunStatus

    _, factory = engine_and_factory
    async with factory() as s:
        org = Organization(id=uuid4(), name="o", slug="o", runs_priority_tier="default", runs_max_concurrent=5)
        s.add(org)
        await s.commit()
        run = FlowRun(id=uuid4(), organization_id=org.id, flow_id=uuid4(), triggered_by=TriggeredBy.API, status=RunStatus.RUNNING)
        s.add(run)
        await s.commit()
        await s.refresh(run)
    return run


@pytest.mark.asyncio
async def test_log_sink_flushes(engine_and_factory, seeded_run):
    from langflow.worker_app.log_sink import RunLogSink
    from langflow.services.database.models.flow_run_log.model import FlowRunLog

    _, factory = engine_and_factory
    sink = RunLogSink(session_factory=factory, run_id=seeded_run.id, flush_interval=0.05, max_buffer=10)
    await sink.start()
    for i in range(5):
        sink.emit(level="info", message=f"hi {i}", node_id=None, extra=None)
    await asyncio.sleep(0.2)
    await sink.stop()

    async with factory() as s:
        rows = (await s.exec(select(FlowRunLog).where(FlowRunLog.run_id == seeded_run.id))).all()
    assert len(rows) == 5


@pytest.mark.asyncio
async def test_log_sink_truncates_at_max_bytes(engine_and_factory, seeded_run):
    from langflow.worker_app.log_sink import RunLogSink
    from langflow.services.database.models.flow_run_log.model import FlowRunLog

    _, factory = engine_and_factory
    # Very small cap so we hit truncation quickly
    sink = RunLogSink(session_factory=factory, run_id=seeded_run.id, flush_interval=0.05, max_total_bytes=10)
    await sink.start()
    # First emit fits; later emits should be dropped, one truncation notice added.
    sink.emit(level="info", message="abc", node_id=None, extra=None)  # 3 bytes — fits
    sink.emit(level="info", message="defghijk", node_id=None, extra=None)  # pushes over 10
    sink.emit(level="info", message="xyzxyz", node_id=None, extra=None)  # should be dropped
    await asyncio.sleep(0.15)
    await sink.stop()

    async with factory() as s:
        rows = (await s.exec(select(FlowRunLog).where(FlowRunLog.run_id == seeded_run.id))).all()
    messages = [r.message for r in rows]
    # Must contain the truncation notice exactly once
    assert sum(1 for m in messages if "truncated" in m) == 1
