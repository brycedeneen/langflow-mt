from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool
from taskiq import InMemoryBroker

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import RunStatus, TriggeredBy
from langflow.services.database.models.organization.model import Organization
from langflow.services.runs.enqueue import RunEnqueuer
from lfx.services.settings.base import Settings


class _RecordingBroker(InMemoryBroker):
    """InMemoryBroker subclass that records kicks instead of executing them.

    taskiq 0.12.x's InMemoryBroker.kick() schedules the task to run immediately,
    which would try to import worker dependencies (DB, Redis, storage). For a
    pure unit test of the enqueuer's tier-routing, we want to assert one task
    was kicked into the right broker without actually running it.
    """

    def __init__(self) -> None:
        super().__init__()
        self.kicked = []

    async def kick(self, message) -> None:  # type: ignore[override]
        self.kicked.append(message)

    def messages_count(self) -> int:
        return len(self.kicked)


@pytest.fixture
async def async_session():
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


@pytest.fixture
async def in_memory_broker_registry():
    high = _RecordingBroker()
    default = _RecordingBroker()
    low = _RecordingBroker()
    for b in (high, default, low):
        await b.startup()
    yield {"high": high, "default": default, "low": low}
    for b in (high, default, low):
        await b.shutdown()


async def _make_org_and_flow(session: AsyncSession, *, tier: str) -> tuple[Organization, Flow]:
    org = Organization(
        name=f"org-{tier}",
        slug=f"org-{tier}-{uuid4().hex[:8]}",
        runs_max_concurrent=5,
        runs_priority_tier=tier,
    )
    session.add(org)
    await session.commit()
    await session.refresh(org)

    flow = Flow(
        name="test-flow",
        organization_id=org.id,
        auto_retry=False,
        max_retries=3,
        timeout_seconds=600,
    )
    session.add(flow)
    await session.commit()
    await session.refresh(flow)
    return org, flow


@pytest.mark.asyncio
async def test_enqueue_uses_default_broker_for_default_tier(
    async_session, in_memory_broker_registry
):
    org, flow = await _make_org_and_flow(async_session, tier="default")
    settings = Settings(_env_file=None)
    enqueuer = RunEnqueuer(
        db=async_session,
        brokers=in_memory_broker_registry,
        settings=settings,
    )
    run = await enqueuer.enqueue(
        org_id=org.id,
        flow_id=flow.id,
        triggered_by=TriggeredBy.API,
        actor_id=None,
        inputs={"q": "hi"},
    )
    assert run.status == RunStatus.QUEUED
    assert run.priority == 5
    assert in_memory_broker_registry["default"].messages_count() == 1
    assert in_memory_broker_registry["high"].messages_count() == 0
    assert in_memory_broker_registry["low"].messages_count() == 0
    # And the kicked message carries the run_id and the right task name.
    msg = in_memory_broker_registry["default"].kicked[0]
    assert msg.task_name == "execute_run"


@pytest.mark.asyncio
async def test_enqueue_uses_high_broker_for_high_tier(
    async_session, in_memory_broker_registry
):
    org, flow = await _make_org_and_flow(async_session, tier="high")
    settings = Settings(_env_file=None)
    enqueuer = RunEnqueuer(
        db=async_session,
        brokers=in_memory_broker_registry,
        settings=settings,
    )
    run = await enqueuer.enqueue(
        org_id=org.id,
        flow_id=flow.id,
        triggered_by=TriggeredBy.API,
        actor_id=None,
        inputs=None,
    )
    assert run.priority == 1
    assert in_memory_broker_registry["high"].messages_count() == 1
    assert in_memory_broker_registry["default"].messages_count() == 0


@pytest.mark.asyncio
async def test_enqueue_uses_low_broker_for_low_tier(
    async_session, in_memory_broker_registry
):
    org, flow = await _make_org_and_flow(async_session, tier="low")
    settings = Settings(_env_file=None)
    enqueuer = RunEnqueuer(
        db=async_session,
        brokers=in_memory_broker_registry,
        settings=settings,
    )
    run = await enqueuer.enqueue(
        org_id=org.id,
        flow_id=flow.id,
        triggered_by=TriggeredBy.API,
        actor_id=None,
        inputs=None,
    )
    assert run.priority == 9
    assert in_memory_broker_registry["low"].messages_count() == 1
