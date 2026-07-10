import asyncio

from app.repositories.analytics import AnalyticsRepository
from app.repositories.errors import ErrorEventRepository, fingerprint_stack


class FakeDb:
    def __init__(self):
        self.rows = []
        self.executed = []

    async def execute(self, sql, params=None):
        self.executed.append((sql, params))

    async def fetch_one(self, sql, params=None):
        if "ai_call_metrics" in sql:
            return {"calls": 2, "tokens": 100, "avg_ms": 50}
        if "COUNT(*)" in sql and "error_events" in sql:
            return {"count": 2}
        if "COUNT(*)" in sql and "render_jobs" in sql and "failed" in sql:
            return {"count": 1}
        if "COUNT(*)" in sql and "render_jobs" in sql and "completed" in sql:
            return {"count": 9}
        if "COUNT(*)" in sql and "render_jobs" in sql:
            return {"count": 10}
        if "COUNT(DISTINCT user_id)" in sql and "user_activity_events" in sql:
            return {"count": 3}
        if "COUNT(*)" in sql and "user_activity_events" in sql:
            return {"count": 12}
        if "COUNT(*)" in sql and "users" in sql and "email_verified" in sql:
            return {"count": 4}
        if "COUNT(*)" in sql and "users" in sql:
            return {"count": 5}
        if "COUNT(DISTINCT user_id)" in sql and "usage_events" in sql:
            return {"count": 2}
        if "COUNT(DISTINCT user_id)" in sql and "render_jobs" in sql:
            return {"count": 3}
        return {"count": 0}

    async def fetch_all(self, sql, params=None):
        if "duration_ms" in sql and "ai_call_metrics" not in sql and "AVG" not in sql:
            return [{"duration_ms": 100}, {"duration_ms": 200}, {"duration_ms": 300}]
        if "stack_fingerprint" in sql or "fingerprint" in sql.lower():
            return [{
                "fingerprint": "abc123",
                "error_code": "TIMEOUT",
                "count": 3,
                "first_seen": "2026-07-01",
                "last_seen": "2026-07-02",
                "sample_message": "timeout",
            }]
        if "feature.open" in sql or "target_id" in sql and "feature" in sql:
            return [{"feature": "render", "count": 4}]
        if "ai_call_metrics" in sql:
            if "GROUP BY" in sql and "provider" in sql:
                return [{"provider": "openrouter", "calls": 2, "ok": 2, "tokens": 100, "avg_ms": 50}]
            if "GROUP BY" in sql and "task" in sql:
                return [{"task": "scene", "calls": 2, "tokens": 100, "avg_ms": 50}]
            return []
        if "GROUP BY day" in sql or "substr(created_at" in sql:
            return [{"day": "2026-07-01", "count": 2}]
        if "error_code" in sql and "GROUP BY" in sql:
            return [{"error_code": "TIMEOUT", "count": 2}]
        if "user_activity_events" in sql and "ORDER BY created_at DESC" in sql:
            return [{
                "id": "a1",
                "user_id": "u1",
                "session_id": None,
                "event_type": "render.completed",
                "target_type": "render_job",
                "target_id": "j1",
                "source": "server",
                "metadata_json": "{}",
                "created_at": "2026-07-01T00:00:00Z",
            }]
        if "event_type" in sql and "GROUP BY" in sql:
            return [{"event_type": "render.completed", "count": 5}]
        if "status" in sql and "GROUP BY" in sql:
            return [{"status": "completed", "count": 9}]
        if "provider" in sql and "GROUP BY" in sql:
            return [{"provider": "router9", "count": 4}]
        if "model" in sql and "GROUP BY" in sql:
            return [{"model": "cx/gpt", "count": 3}]
        if "error_events" in sql and "ORDER BY created_at DESC" in sql:
            return [{
                "id": "e1",
                "request_id": "r1",
                "user_id": "u1",
                "source": "server",
                "route": "/api/render",
                "method": "POST",
                "status_code": 500,
                "error_code": "TIMEOUT",
                "message": "timeout",
                "stack_fingerprint": "abc",
                "created_at": "2026-07-01T00:00:00Z",
            }]
        return []


def test_fingerprint_stable():
    assert fingerprint_stack("a  b") == fingerprint_stack("a b")
    assert len(fingerprint_stack("x")) == 16


def test_error_event_create_inserts():
    db = FakeDb()

    async def run():
        return await ErrorEventRepository(db).create(message="boom", error_code="X", source="server")

    event_id = asyncio.run(run())
    assert event_id
    assert any("INSERT INTO error_events" in sql for sql, _ in db.executed)


def test_analytics_overview_shape():
    db = FakeDb()
    overview = asyncio.run(AnalyticsRepository(db).overview(14))
    assert overview["renders"] == 10
    assert overview["renders_failed"] == 1
    assert overview["duration_p50_ms"] == 200
    assert overview["dau"] == 3


def test_analytics_funnel_shape():
    db = FakeDb()
    funnel = asyncio.run(AnalyticsRepository(db).funnel(30))
    assert funnel["registered"] == 5
    assert funnel["verified"] == 4


def test_error_groups_shape():
    db = FakeDb()

    async def run():
        return await AnalyticsRepository(db).error_groups(14)

    # FakeDb returns empty for unknown group query — still must not crash
    groups = asyncio.run(run())
    assert isinstance(groups, list)


def test_taxonomy_constants():
    from app.services.analytics_taxonomy import ALLOWED_CLIENT_EVENT_TYPES, FEATURE_OPEN, PAGE_VIEW

    assert FEATURE_OPEN in ALLOWED_CLIENT_EVENT_TYPES
    assert PAGE_VIEW in ALLOWED_CLIENT_EVENT_TYPES
