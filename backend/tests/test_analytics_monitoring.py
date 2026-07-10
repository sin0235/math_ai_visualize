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
        if "render_jobs" in sql and "status" in sql and "GROUP BY" in sql:
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


def test_analytics_errors_method_not_shadowed():
    db = FakeDb()
    repo = AnalyticsRepository(db)

    assert callable(repo.errors)
    result = asyncio.run(repo.errors(14))
    assert result["top_codes"] == [{"error_code": "TIMEOUT", "count": 2}]
    assert result["recent"][0]["id"] == "e1"


def test_product_usage_aggregates_users_outcomes_and_comparison():
    class ProductUsageDb:
        def __init__(self):
            self.activity_period = 0
            self.error_period = 0

        async def fetch_all(self, sql, params=None):
            if "COALESCE(target_id, 'unknown') AS feature" in sql:
                return [{"feature": "render", "opens": 6, "unique_users": 3, "sessions": 4}]
            if "END AS feature" in sql:
                return [{"feature": "render", "completed": 3, "failed": 1, "unique_users": 2}]
            if "COUNT(DISTINCT user_id) AS unique_users" in sql:
                return [{"day": "2026-07-01", "unique_users": 3, "events": 8, "completed": 3}]
            return []

        async def fetch_one(self, sql, params=None):
            if "AS active_users" in sql:
                self.activity_period += 1
                return (
                    {"active_users": 5, "feature_opens": 7, "completed_outcomes": 4}
                    if self.activity_period == 1
                    else {"active_users": 4, "feature_opens": 5, "completed_outcomes": 2}
                )
            if "error_events" in sql:
                self.error_period += 1
                return {"count": 3 if self.error_period == 1 else 1}
            return None

    result = asyncio.run(AnalyticsRepository(ProductUsageDb()).product_usage(14))
    assert result["sample_scope"] == "authenticated_users"
    assert result["feature_usage"][0] == {
        "feature": "render",
        "opens": 6,
        "unique_users": 3,
        "sessions": 4,
        "share_pct": 100.0,
    }
    assert result["outcomes"][0]["success_rate"] == 75.0
    assert result["outcomes"][-1]["success_rate"] is None
    assert result["daily_active_users"][0]["unique_users"] == 3
    assert result["period_comparison"]["active_users"]["change_pct"] == 25.0
    assert result["period_comparison"]["errors"]["change_pct"] == 200.0


def test_product_usage_sqlite_queries(tmp_path):
    from app.db.session import SQLiteClient

    async def run():
        db = SQLiteClient(str(tmp_path / "analytics.db"))
        await db.execute_many([
            (
                """
                CREATE TABLE user_activity_events (
                  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, session_id TEXT, event_type TEXT NOT NULL,
                  target_type TEXT, target_id TEXT, source TEXT NOT NULL DEFAULT 'server',
                  metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                None,
            ),
            (
                """
                CREATE TABLE error_events (
                  id TEXT PRIMARY KEY, user_id TEXT, source TEXT, route TEXT, status_code INTEGER,
                  error_code TEXT, message TEXT NOT NULL, stack_fingerprint TEXT,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                None,
            ),
            ("INSERT INTO user_activity_events (id, user_id, session_id, event_type, target_id) VALUES (?, ?, ?, ?, ?)", ["a1", "u1", "s1", "feature.open", "render"]),
            ("INSERT INTO user_activity_events (id, user_id, session_id, event_type, target_id) VALUES (?, ?, ?, ?, ?)", ["a2", "u1", "s1", "feature.open", "render"]),
            ("INSERT INTO user_activity_events (id, user_id, session_id, event_type, target_id) VALUES (?, ?, ?, ?, ?)", ["a3", "u2", None, "feature.open", "analyzer"]),
            ("INSERT INTO user_activity_events (id, user_id, event_type) VALUES (?, ?, ?)", ["a4", "u1", "render.completed"]),
            ("INSERT INTO user_activity_events (id, user_id, event_type) VALUES (?, ?, ?)", ["a5", "u2", "render.failed"]),
            ("INSERT INTO error_events (id, user_id, source, route, status_code, error_code, message) VALUES (?, ?, ?, ?, ?, ?, ?)", ["e1", "u2", "server", "/api/render", 500, "RENDER_FAILED", "boom"]),
        ])
        try:
            return await AnalyticsRepository(db).product_usage(7)
        finally:
            await db.close()

    result = asyncio.run(run())
    assert result["feature_usage"][0]["feature"] == "render"
    assert result["feature_usage"][0]["unique_users"] == 1
    assert result["feature_usage"][0]["sessions"] == 1
    assert result["outcomes"][0]["success_rate"] == 50.0
    assert result["period_comparison"]["errors"]["current"] == 1


def test_product_usage_empty_shape():
    class EmptyDb:
        async def fetch_all(self, sql, params=None):
            return []

        async def fetch_one(self, sql, params=None):
            return None

    result = asyncio.run(AnalyticsRepository(EmptyDb()).product_usage(7))
    assert result["feature_usage"] == []
    assert result["daily_active_users"] == []
    assert len(result["outcomes"]) == 6
    assert all(item["success_rate"] is None for item in result["outcomes"])
    assert result["period_comparison"]["errors"]["change_pct"] == 0.0


def test_render_quality_breakdown():
    class RenderDb:
        async def fetch_all(self, sql, params=None):
            if "COALESCE(provider, 'unknown') AS provider" in sql:
                return [{"provider": "router9", "count": 5, "completed": 4, "failed": 1, "avg_ms": 1200}]
            if "COALESCE(renderer, 'unknown') AS renderer" in sql:
                return [{"renderer": "threejs", "count": 5, "completed": 4, "failed": 1, "avg_ms": 1200}]
            if "COALESCE(source_type, 'unknown') AS source" in sql:
                return [{"source": "problem", "count": 5, "completed": 4, "failed": 1}]
            if "COALESCE(status, 'unknown')" in sql:
                return [{"status": "completed", "count": 4}, {"status": "failed", "count": 1}]
            if "COALESCE(model, 'unknown')" in sql:
                return [{"model": "cx/gpt", "count": 5}]
            if "duration_ms" in sql and "ORDER BY duration_ms" in sql:
                return [{"duration_ms": 1200}]
            return []

        async def fetch_one(self, sql, params=None):
            if "status = 'completed'" in sql:
                return {"count": 4}
            if "status = 'failed'" in sql:
                return {"count": 1}
            if "render_jobs" in sql:
                return {"count": 5}
            return {"count": 0}

    result = asyncio.run(AnalyticsRepository(RenderDb()).renders(14))
    assert result["by_provider"][0]["fail_rate"] == 20.0
    assert result["by_renderer"][0]["avg_ms"] == 1200
    assert result["by_source"][0]["completed"] == 4


def test_ai_usage_includes_failure_and_model_breakdown():
    class AiDb:
        async def fetch_all(self, sql, params=None):
            row = {"calls": 4, "ok": 3, "tokens": 800, "avg_ms": 900}
            if "AS model" in sql:
                return [{**row, "provider": "openrouter", "model": "cx/gpt"}]
            if "AS task" in sql:
                return [{**row, "task": "render"}]
            if "AS provider" in sql:
                return [{**row, "provider": "openrouter"}]
            return []

        async def fetch_one(self, sql, params=None):
            return {"calls": 4, "ok": 3, "tokens": 800, "avg_ms": 900}

    result = asyncio.run(AnalyticsRepository(AiDb()).ai_usage(14))
    assert result["failed"] == 1
    assert result["success_rate"] == 75.0
    assert result["by_task"][0]["failed"] == 1
    assert result["by_model"][0]["model"] == "cx/gpt"


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
