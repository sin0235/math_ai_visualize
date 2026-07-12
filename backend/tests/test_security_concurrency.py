import asyncio
import os

import pytest

from app.db.migrations import apply_sqlite_migrations
from app.db.session import SQLiteClient
from app.repositories.auth import RateLimitRepository
from app.services.load_gates import RedisGate


def test_rate_limit_enforces_exact_limit_under_128_concurrent_hits(tmp_path):
    async def run():
        db = SQLiteClient(str(tmp_path / "rate-limit.db"))
        await apply_sqlite_migrations(db)
        try:
            results = await asyncio.gather(
                *(RateLimitRepository(db).hit("security:burst", 12, 60) for _ in range(128))
            )
        finally:
            await db.close()

        assert sum(result.allowed for result in results) == 12
        assert all(result.retry_after_seconds > 0 for result in results if not result.allowed)

    asyncio.run(run())


@pytest.mark.skipif(not os.getenv("TEST_REDIS_URL"), reason="requires isolated Redis test container")
def test_redis_gate_enforces_exact_limit_under_256_concurrent_acquires(monkeypatch):
    async def run():
        from redis.asyncio import Redis

        client = Redis.from_url(os.environ["TEST_REDIS_URL"], decode_responses=True)
        gate = RedisGate("security-concurrency", ttl_seconds=60)

        async def get_redis():
            return client

        monkeypatch.setattr("app.services.redis_client.get_redis", get_redis)
        await client.delete("gate:security-concurrency")
        try:
            slots = await asyncio.gather(*(gate.try_acquire(16) for _ in range(256)))
            accepted = [slot for slot in slots if slot is not None]

            assert len(accepted) == 16
            assert await client.zcard("gate:security-concurrency") == 16

            for slot in accepted:
                slot.release()
            await asyncio.sleep(0.05)
            assert await client.zcard("gate:security-concurrency") == 0
        finally:
            await client.delete("gate:security-concurrency")
            await client.aclose()

    asyncio.run(run())