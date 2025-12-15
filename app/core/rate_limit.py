from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from functools import lru_cache
from typing import Any, DefaultDict, Optional

from fastapi import HTTPException

from app.db.models import APIKey as APIKeyModel

_in_memory_daily_counts: DefaultDict[str, dict[str, int]] = defaultdict(dict)


@dataclass(frozen=True)
class RateLimitInfo:
    limit: int
    used: int
    remaining: int | None
    resets_at: datetime
    retry_after_seconds: int


@lru_cache(maxsize=4)
def get_rate_limit_redis_client(redis_url: str) -> Any | None:
    if redis_url.strip().lower().startswith("memory://"):
        return None

    import redis

    return redis.from_url(redis_url)


def _get_daily_window(now: datetime) -> tuple[str, datetime, int]:
    now_utc = now.astimezone(timezone.utc)
    day_key = now_utc.date().isoformat()
    resets_at = datetime.combine(now_utc.date() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    retry_after_seconds = max(0, int((resets_at - now_utc).total_seconds()))
    return day_key, resets_at, retry_after_seconds


def _redis_counter_key(api_key_id: str, day_key: str) -> str:
    return f"rate_limit:{api_key_id}:{day_key}"


def get_rate_limit_info(
    api_key: Optional[APIKeyModel],
    redis_client: Any | None,
    *,
    now: datetime | None = None,
) -> RateLimitInfo | None:
    if api_key is None:
        return None

    limit = int(getattr(api_key, "rate_limit_per_day", 0) or 0)
    now = now or datetime.now(timezone.utc)
    day_key, resets_at, retry_after_seconds = _get_daily_window(now)
    api_key_id = str(api_key.id)

    if limit <= 0:
        return RateLimitInfo(
            limit=0,
            used=0,
            remaining=None,
            resets_at=resets_at,
            retry_after_seconds=retry_after_seconds,
        )

    used = 0
    if redis_client is None:
        used = int(_in_memory_daily_counts.get(api_key_id, {}).get(day_key, 0))
        remaining = max(0, limit - used)
        return RateLimitInfo(
            limit=limit,
            used=used,
            remaining=remaining,
            resets_at=resets_at,
            retry_after_seconds=retry_after_seconds,
        )

    key = _redis_counter_key(api_key_id, day_key)
    try:
        raw = redis_client.get(key)
        used = int(raw) if raw is not None else 0
    except Exception:
        used = int(_in_memory_daily_counts.get(api_key_id, {}).get(day_key, 0))

    remaining = max(0, limit - used)
    return RateLimitInfo(
        limit=limit,
        used=used,
        remaining=remaining,
        resets_at=resets_at,
        retry_after_seconds=retry_after_seconds,
    )


def check_rate_limit(
    api_key: Optional[APIKeyModel],
    redis_client: Any | None,
    *,
    consume: bool = True,
) -> None:
    if api_key is None:
        return

    limit = int(getattr(api_key, "rate_limit_per_day", 0) or 0)
    if limit <= 0:
        return

    now = datetime.now(timezone.utc)
    day_key, resets_at, retry_after_seconds = _get_daily_window(now)
    api_key_id = str(api_key.id)

    if not consume:
        return

    if redis_client is None:
        count = _in_memory_daily_counts[api_key_id].get(day_key, 0) + 1
        _in_memory_daily_counts[api_key_id][day_key] = count
        if count > limit:
            raise HTTPException(
                status_code=429,
                detail=f"rate limit exceeded: {limit}/day",
                headers={"Retry-After": str(retry_after_seconds)},
            )
        return

    key = _redis_counter_key(api_key_id, day_key)
    try:
        count = int(redis_client.incr(key))
        if count == 1:
            redis_client.expire(key, retry_after_seconds + 60)
    except Exception:
        count = _in_memory_daily_counts[api_key_id].get(day_key, 0) + 1
        _in_memory_daily_counts[api_key_id][day_key] = count

    if count > limit:
        raise HTTPException(
            status_code=429,
            detail=f"rate limit exceeded: {limit}/day",
            headers={"Retry-After": str(retry_after_seconds)},
        )
