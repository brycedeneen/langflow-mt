from __future__ import annotations

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from lfx.services.deps import get_settings_service


_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        settings = get_settings_service().settings
        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool


async def close_arq_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
