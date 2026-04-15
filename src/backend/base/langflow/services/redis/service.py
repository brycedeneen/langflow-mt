from __future__ import annotations

from redis.asyncio import Redis

from langflow.services.base import Service


class RedisService(Service):
    name = "redis_service"

    def __init__(self, url: str) -> None:
        self.url = url
        self.client: Redis | None = None

    async def start(self) -> None:
        self.client = Redis.from_url(self.url, decode_responses=False)
        await self.client.ping()

    async def stop(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def teardown(self) -> None:
        await self.stop()
