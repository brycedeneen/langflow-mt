import pytest
from langflow.services.redis.service import RedisService


@pytest.mark.asyncio
async def test_redis_service_roundtrip(redis_service: RedisService):
    await redis_service.client.set("k", "v")
    assert (await redis_service.client.get("k")) == b"v"
