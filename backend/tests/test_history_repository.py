import json

import pytest

from app.repositories.activity import UserActivityRepository
from app.repositories.history import RenderHistoryRepository


class FakeDb:
    def __init__(self):
        self.sql = ""
        self.params = []

    async def fetch_all(self, sql, params):
        self.sql = sql
        self.params = params
        return [{
            "id": "job-1",
            "user_id": "user-1",
            "problem_text": "Vẽ A.",
            "provider": "openrouter",
            "model": "model-a",
            "warnings_json": "[]",
            "created_at": "2026-05-09T00:00:00Z",
            "source_type": "problem",
            "renderer": "geogebra_2d",
        }]


@pytest.mark.anyio
async def test_history_list_does_not_select_heavy_scene_payload_columns():
    db = FakeDb()

    rows = await RenderHistoryRepository(db).list_for_user("user-1")

    selected_columns = db.sql.lower().split("from render_jobs", 1)[0]
    assert "scene_json" not in selected_columns
    assert "payload_json" not in selected_columns
    assert rows[0].id == "job-1"


class FakeActivityDb:
    def __init__(self):
        self.params = []

    async def execute(self, sql, params):
        self.params = params

    async def fetch_one(self, sql, params):
        return {
            "id": params[0],
            "user_id": "user-1",
            "session_id": None,
            "event_type": "byok_provider.updated",
            "target_type": "user_ai_provider_settings",
            "target_id": "user-1",
            "source": "server",
            "metadata_json": self.params[7],
            "created_at": "2026-05-09T00:00:00Z",
        }


@pytest.mark.anyio
async def test_activity_log_strips_secret_metadata():
    db = FakeActivityDb()

    event = await UserActivityRepository(db).create(
        "user-1",
        "byok_provider.updated",
        target_type="user_ai_provider_settings",
        target_id="user-1",
        metadata={
            "enabled": True,
            "api_key": "sk-secret",
            "api_key_last4": "1234",
            "base_url": "http://private.local/v1",
            "nested": {"token": "secret", "model": "qwen"},
        },
    )

    metadata = json.loads(event.metadata_json)
    assert metadata == {"enabled": True, "nested": {"model": "qwen"}}
