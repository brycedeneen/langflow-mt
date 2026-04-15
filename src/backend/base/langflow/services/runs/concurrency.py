from __future__ import annotations

from uuid import UUID

from redis.asyncio import Redis

_ACQUIRE_LUA = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local current = tonumber(redis.call('GET', key) or '0')
if current < limit then
  redis.call('INCR', key)
  return 1
else
  return 0
end
"""

_RELEASE_LUA = """
local key = KEYS[1]
local current = tonumber(redis.call('GET', key) or '0')
if current > 0 then
  redis.call('DECR', key)
end
return 1
"""


class OrgConcurrency:
    def __init__(self, client: Redis):
        self.client = client
        self._acq = self.client.register_script(_ACQUIRE_LUA)
        self._rel = self.client.register_script(_RELEASE_LUA)

    @staticmethod
    def key(org_id: UUID) -> str:
        return f"org:{org_id}:running"

    async def try_acquire(self, org_id: UUID, *, limit: int) -> bool:
        result = await self._acq(keys=[self.key(org_id)], args=[limit])
        return int(result) == 1

    async def release(self, org_id: UUID) -> None:
        await self._rel(keys=[self.key(org_id)], args=[])

    async def current(self, org_id: UUID) -> int:
        v = await self.client.get(self.key(org_id))
        return int(v) if v else 0
