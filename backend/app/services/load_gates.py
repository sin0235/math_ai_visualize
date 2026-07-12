"""Process-wide capacity gates for long-running endpoints.

Uses Redis when REDIS_URL is configured (multi-instance), otherwise in-process.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4

logger = logging.getLogger(__name__)


class CapacitySlot(Protocol):
    def release(self) -> None: ...


class CapacityGate(Protocol):
    name: str

    async def try_acquire(self, limit: int) -> CapacitySlot | None: ...
    def reserved_count(self) -> int: ...
    def stats(self) -> dict: ...


@dataclass
class InProcessSlot:
    _gate: InProcessGate
    _closed: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def release(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._gate._release()


class InProcessGate:
    def __init__(self, name: str) -> None:
        self.name = name
        self._async_lock = asyncio.Lock()
        self._reserved = 0
        self._lock = threading.Lock()

    def reserved_count(self) -> int:
        with self._lock:
            return self._reserved

    def _release(self) -> None:
        with self._lock:
            self._reserved = max(0, self._reserved - 1)

    async def try_acquire(self, limit: int) -> InProcessSlot | None:
        limit = max(1, int(limit))
        async with self._async_lock:
            with self._lock:
                if self._reserved >= limit:
                    return None
                self._reserved += 1
            return InProcessSlot(self)

    def stats(self) -> dict:
        return {"name": self.name, "backend": "in_process", "reserved": self.reserved_count()}


@dataclass
class RedisSlot:
    _gate: RedisGate
    _token: str
    _closed: bool = False

    def release(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._gate._release_token(self._token))
        except RuntimeError:
            # No running loop (sync teardown): best-effort fire-and-forget via new loop.
            try:
                asyncio.run(self._gate._release_token(self._token))
            except Exception:
                logger.debug("Redis slot release failed", exc_info=True)


class RedisGate:
    """Shared capacity via Redis sorted-set of tokens with TTL safety."""

    _ACQUIRE_SCRIPT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1])
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then
    return 0
end
redis.call('ZADD', KEYS[1], ARGV[4], ARGV[3])
return 1
"""

    def __init__(self, name: str, ttl_seconds: int = 600) -> None:
        self.name = name
        self.ttl_seconds = ttl_seconds
        self._local = InProcessGate(name)
        self._key = f"gate:{name}"

    def reserved_count(self) -> int:
        return self._local.reserved_count()

    async def try_acquire(self, limit: int) -> CapacitySlot | None:
        from app.services.redis_client import get_redis

        redis = await get_redis()
        if redis is None:
            return await self._local.try_acquire(limit)

        limit = max(1, int(limit))
        token = str(uuid4())
        now = time.time()
        try:
            accepted = await redis.eval(
                self._ACQUIRE_SCRIPT,
                1,
                self._key,
                now,
                limit,
                token,
                now + self.ttl_seconds,
            )
            return RedisSlot(self, token) if accepted == 1 else None
        except Exception:
            logger.warning("Redis gate acquire failed; fail-closed for %s", self.name, exc_info=True)
            return None

    async def _release_token(self, token: str) -> None:
        from app.services.redis_client import get_redis

        redis = await get_redis()
        if redis is None:
            return
        try:
            await redis.zrem(self._key, token)
        except Exception:
            logger.debug("Redis gate release failed", exc_info=True)

    def stats(self) -> dict:
        return {"name": self.name, "backend": "redis_or_local", "reserved": self.reserved_count()}


render_load_gate: CapacityGate = RedisGate("render")
ocr_load_gate: CapacityGate = RedisGate("ocr")


def all_gate_stats() -> list[dict]:
    from app.services.algebra.load_gate import algebra_load_gate

    return [
        render_load_gate.stats(),
        ocr_load_gate.stats(),
        {
            "name": "algebra",
            "backend": "in_process",
            "reserved": algebra_load_gate.reserved_count(),
            "worker_inflight": algebra_load_gate.worker_count(),
        },
    ]
