import json
import asyncio
from typing import Optional
from cachetools import TTLCache
from app.core.config import settings
import redis.asyncio as redis

# Fallback in-memory cache (not multi-instance safe)
_memory_cache = TTLCache(maxsize=5000, ttl=settings.IDEMPOTENCY_TTL_SECONDS)
_redis: Optional[redis.Redis] = None

async def init_idempotency():
    global _redis
    if settings.REDIS_URL:
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def _redis_get(key: str) -> Optional[str]:
    if _redis:
        return await _redis.get(key)
    return _memory_cache.get(key)

async def _redis_set(key: str, value: str):
    if _redis:
        await _redis.setex(key, settings.IDEMPOTENCY_TTL_SECONDS, value)
    else:
        _memory_cache[key] = value

async def get_cached_response(key: str) -> Optional[dict]:
    raw = await _redis_get(f"idemp:{key}")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            return None
    return None

async def set_cached_response(key: str, value: dict):
    await _redis_set(f"idemp:{key}", json.dumps(value))
