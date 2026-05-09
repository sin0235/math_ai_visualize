import pytest

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
