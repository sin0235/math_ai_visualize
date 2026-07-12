import asyncio

from app.services.load_gates import RedisGate


class FakeRedis:
    def __init__(self) -> None:
        self.tokens: set[str] = set()

    async def eval(self, script, key_count, key, now, limit, token, expires_at):
        assert key_count == 1
        assert key == "gate:test"
        assert "ZREMRANGEBYSCORE" in script
        assert "ZCARD" in script
        assert "ZADD" in script
        if len(self.tokens) >= int(limit):
            return 0
        self.tokens.add(token)
        return 1

    async def zrem(self, key, token):
        self.tokens.discard(token)


def test_redis_gate_acquires_exact_limit_atomically(monkeypatch):
    async def run():
        redis = FakeRedis()

        async def get_redis():
            return redis

        monkeypatch.setattr("app.services.redis_client.get_redis", get_redis)
        gate = RedisGate("test")
        slots = await asyncio.gather(*(gate.try_acquire(4) for _ in range(40)))
        accepted = [slot for slot in slots if slot is not None]

        assert len(accepted) == 4
        assert len(redis.tokens) == 4

        for slot in accepted:
            slot.release()
        await asyncio.sleep(0)
        assert not redis.tokens

    asyncio.run(run())