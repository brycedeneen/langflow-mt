import pytest
from uuid import uuid4
from langflow.services.runs.concurrency import OrgConcurrency


@pytest.mark.asyncio
async def test_acquire_respects_limit(redis_service):
    conc = OrgConcurrency(redis_service.client)
    org_id = uuid4()
    assert await conc.try_acquire(org_id, limit=2) is True
    assert await conc.try_acquire(org_id, limit=2) is True
    assert await conc.try_acquire(org_id, limit=2) is False
    await conc.release(org_id)
    assert await conc.try_acquire(org_id, limit=2) is True


@pytest.mark.asyncio
async def test_release_never_goes_negative(redis_service):
    conc = OrgConcurrency(redis_service.client)
    org_id = uuid4()
    await conc.release(org_id)
    assert await conc.try_acquire(org_id, limit=1) is True
