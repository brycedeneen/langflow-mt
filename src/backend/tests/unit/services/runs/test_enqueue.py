import pytest
from uuid import uuid4

from arq.connections import ArqRedis

from langflow.services.runs.enqueue import RunEnqueuer
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_run.model import TriggeredBy, RunStatus
from langflow.services.database.models.organization.model import Organization
from lfx.services.settings.base import Settings


@pytest.fixture
async def arq_redis():
    # ArqRedis IS a redis.asyncio.Redis subclass — create from DSN.
    from arq.connections import create_pool, RedisSettings

    pool = await create_pool(RedisSettings.from_dsn("redis://localhost:6379/15"))
    await pool.flushdb()  # clean slate before test
    yield pool
    await pool.flushdb()  # clean up after test
    await pool.aclose()


@pytest.fixture
async def org_and_flow(async_session):
    # Organization requires: name, slug (unique).
    org = Organization(
        name="test-org",
        slug=f"test-org-{uuid4().hex[:8]}",
        runs_max_concurrent=5,
        runs_priority_tier="default",
    )
    async_session.add(org)
    await async_session.commit()
    await async_session.refresh(org)

    # Flow requires: name, organization_id. user_id is nullable.
    flow = Flow(
        name="test-flow",
        organization_id=org.id,
        auto_retry=False,
        max_retries=3,
        timeout_seconds=600,
    )
    async_session.add(flow)
    await async_session.commit()
    await async_session.refresh(flow)
    return org, flow


@pytest.mark.asyncio
async def test_enqueue_persists_row_and_dispatches(async_session, arq_redis, org_and_flow):
    org, flow = org_and_flow
    settings = Settings(_env_file=None)
    enq = RunEnqueuer(db=async_session, redis=arq_redis, settings=settings)
    run = await enq.enqueue(
        org_id=org.id,
        flow_id=flow.id,
        triggered_by=TriggeredBy.API,
        actor_id=None,
        inputs={"q": "hi"},
    )
    assert run.status == RunStatus.QUEUED
    assert run.priority == 5  # default tier

    # Arq 0.26 stores jobs in a sorted set keyed by the queue name directly (e.g. "runs:default")
    # NOT "arq:queue:runs:default" — verified empirically against arq 0.26.3
    count = await arq_redis.zcard(b"runs:default")
    assert count >= 1
