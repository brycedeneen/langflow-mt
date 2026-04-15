from __future__ import annotations
from uuid import UUID
from redis.asyncio import Redis


def _key(run_id: UUID) -> str:
    return f"run:cancel:{run_id}"


async def request_cancel(redis: Redis, run_id: UUID, *, ttl_seconds: int = 3600) -> None:
    await redis.set(_key(run_id), b"1", ex=ttl_seconds)


async def is_cancel_requested(redis: Redis, run_id: UUID) -> bool:
    return bool(await redis.get(_key(run_id)))
