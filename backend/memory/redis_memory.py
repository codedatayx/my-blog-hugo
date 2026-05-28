import json
import redis.asyncio as aioredis
from config import REDIS_URL, REDIS_TTL, REDIS_MAX_TURNS


class RedisMemory:
    def __init__(self):
        self.redis = None

    async def connect(self):
        self.redis = aioredis.from_url(REDIS_URL, decode_responses=True)

    async def close(self):
        if self.redis:
            await self.redis.aclose()

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def save_turn(self, session_id: str, role: str, content: str):
        key = self._key(session_id)
        data = json.dumps({"role": role, "content": content})
        await self.redis.rpush(key, data)
        await self.redis.expire(key, REDIS_TTL)

        # Check if we need to compress
        length = await self.redis.llen(key)
        if length > REDIS_MAX_TURNS:
            await self._trim_old(session_id)

    async def get_context(self, session_id: str, limit: int = REDIS_MAX_TURNS) -> list:
        key = self._key(session_id)
        raw = await self.redis.lrange(key, -limit, -1)
        return [json.loads(item) for item in raw]

    async def get_turn_count(self, session_id: str) -> int:
        key = self._key(session_id)
        return await self.redis.llen(key)

    async def _trim_old(self, session_id: str):
        """Keep only the most recent turns, discard older ones."""
        key = self._key(session_id)
        length = await self.redis.llen(key)
        if length > REDIS_MAX_TURNS:
            # Remove oldest entries beyond the limit
            await self.redis.ltrim(key, length - REDIS_MAX_TURNS, -1)

    async def clear_session(self, session_id: str):
        key = self._key(session_id)
        await self.redis.delete(key)
