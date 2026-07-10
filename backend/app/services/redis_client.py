"""Optional Redis client for multi-instance gates, cache, WS, job notify."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis: Any | None = None
_redis_failed = False


async def get_redis() -> Any | None:
    """Return shared async Redis client, or None if unavailable/unconfigured."""
    global _redis, _redis_failed
    if _redis is not None:
        return _redis
    if _redis_failed:
        return None
    settings = get_settings()
    if not settings.redis_url:
        return None
    try:
        from redis.asyncio import Redis

        client = Redis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        _redis = client
        logger.info("Redis connected")
        return _redis
    except Exception:
        _redis_failed = True
        logger.warning("Redis unavailable; falling back to in-process state", exc_info=True)
        return None


async def close_redis() -> None:
    global _redis, _redis_failed
    if _redis is not None:
        try:
            await _redis.aclose()
        except Exception:
            logger.debug("Redis close error", exc_info=True)
    _redis = None
    _redis_failed = False


async def redis_ping() -> dict[str, Any]:
    client = await get_redis()
    if client is None:
        return {"configured": bool(get_settings().redis_url), "ok": False, "mode": "disabled"}
    try:
        await client.ping()
        return {"configured": True, "ok": True, "mode": "redis"}
    except Exception as error:
        return {"configured": True, "ok": False, "mode": "redis", "error": str(error)}
