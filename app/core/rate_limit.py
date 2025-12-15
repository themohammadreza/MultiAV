from __future__ import annotations

import time
from collections import defaultdict, deque
from functools import lru_cache
from typing import Any, DefaultDict, Deque, Optional

from fastapi import HTTPException

from app.db.models import APIKey as APIKeyModel

_in_memory_windows: DefaultDict[str, Deque[float]] = defaultdict(deque)


@lru_cache(maxsize=4)
def get_rate_limit_redis_client(redis_url: str) -> Any | None:
    if redis_url.strip().lower().startswith("memory://"):
        return None

    import redis

    return redis.from_url(redis_url)


def check_rate_limit(
    api_key: Optional[APIKeyModel],
    redis_client: Any | None,
    *,
    window_seconds: int = 60,
) -> None:
    if api_key is None:
        return

    limit = int(getattr(api_key, "rate_limit_per_minute", 0) or 0)
    if limit <= 0:
        return

    if redis_client is None:
        _check_rate_limit_in_memory(str(api_key.id), limit, window_seconds)
        return

    now_ns = time.time_ns()
    window_start_ns = now_ns - (window_seconds * 1_000_000_000)
    key = f"rate_limit:{api_key.id}"

    try:
        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(key, 0, window_start_ns)
        pipe.zadd(key, {str(now_ns): now_ns})
        pipe.zcard(key)
        pipe.expire(key, window_seconds + 1)
        request_count = int(pipe.execute()[2])
    except Exception:
        _check_rate_limit_in_memory(str(api_key.id), limit, window_seconds)
        return

    if request_count > limit:
        raise HTTPException(
            status_code=429,
            detail=f"rate limit exceeded: {limit}/min",
            headers={"Retry-After": str(window_seconds)},
        )


def _check_rate_limit_in_memory(api_key_id: str, limit: int, window_seconds: int) -> None:
    now = time.time()
    window_start = now - window_seconds

    timestamps = _in_memory_windows[api_key_id]
    while timestamps and timestamps[0] <= window_start:
        timestamps.popleft()
    timestamps.append(now)

    if len(timestamps) > limit:
        raise HTTPException(
            status_code=429,
            detail=f"rate limit exceeded: {limit}/min",
            headers={"Retry-After": str(window_seconds)},
        )
