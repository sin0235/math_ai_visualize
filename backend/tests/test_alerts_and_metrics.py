import asyncio

from app.repositories.ai_metrics import AiCallMetricsRepository
from app.services.alerts import run_alert_checks
from app.services.provider_logging import extract_token_usage


class RecordingDb:
    def __init__(self):
        self.executed = []
        self.counts = {
            "error": 40,
            "render_total": 20,
            "render_failed": 10,
            "queued": 2,
        }

    async def execute(self, sql, params=None):
        self.executed.append((sql, list(params or [])))

    async def fetch_one(self, sql, params=None):
        if "error_events" in sql:
            return {"count": self.counts["error"]}
        if "status = 'failed'" in sql:
            return {"count": self.counts["render_failed"]}
        if "status IN ('completed', 'failed')" in sql or "status IN ('completed','failed')" in sql:
            return {"count": self.counts["render_total"]}
        if "status = 'queued'" in sql:
            return {"count": self.counts["queued"]}
        return {"count": 0}


def test_extract_token_usage_from_openai_payload():
    usage = extract_token_usage({"usage": {"prompt_tokens": 3, "completion_tokens": 7, "total_tokens": 10}})
    assert usage == {"prompt_tokens": 3, "completion_tokens": 7, "total_tokens": 10}
    assert extract_token_usage({"foo": 1}) is None


def test_ai_call_metrics_insert():
    db = RecordingDb()

    async def run():
        return await AiCallMetricsRepository(db).create(
            task="scene",
            provider="openrouter",
            model="m",
            elapsed_ms=123,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )

    event_id = asyncio.run(run())
    assert event_id
    assert any("INSERT INTO ai_call_metrics" in sql for sql, _ in db.executed)


def test_alert_checks_fire_on_spike(monkeypatch):
    db = RecordingDb()
    sent = []

    async def fake_webhook(settings, alert):
        sent.append(alert)

    monkeypatch.setattr("app.services.alerts._dispatch_webhook", fake_webhook)
    from app.core.config import Settings

    settings = Settings(
        _env_file=None,
        alert_error_spike_threshold=10,
        alert_render_fail_rate_percent=20,
        alert_webhook_url="https://example.test/hook",
    )
    alerts = asyncio.run(run_alert_checks(db, settings))
    types = {a["type"] for a in alerts}
    assert "error_spike" in types
    assert "render_fail_rate" in types
    assert "queue_lag" in types
    assert len(sent) == len(alerts)
