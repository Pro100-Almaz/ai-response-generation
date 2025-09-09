from aiolimiter import AsyncLimiter
from typing import Dict
from app.core.config import settings

# In-memory per-key limiter (for production, prefer Redis-based token buckets)
_limiters: Dict[str, AsyncLimiter] = {}

def get_limiter(key: str) -> AsyncLimiter:
    # per 60s window; AsyncLimiter uses a per-second rate, so we simulate approximate per-minute
    rate = max(1, settings.RATE_LIMIT_PER_MINUTE)
    # We'll just set per-minute tokens; limiter uses capacity/rate semantics
    if key not in _limiters:
        _limiters[key] = AsyncLimiter(rate, time_period=60)
    return _limiters[key]
