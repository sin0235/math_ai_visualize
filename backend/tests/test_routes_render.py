import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.deps import require_active_user
from app.schemas.scene import MathScene, CasIssueResponse

def test_render_routes_cas_issues(monkeypatch):
    async def mock_active_user():
        return None

    async def mock_noop(*args, **kwargs):
        return None

    # We mock extract_scene to return a scene with cas_issues
    async def mock_extract_scene(*args, **kwargs):
        scene = MathScene.model_validate({
            "problem_text": "M là trung điểm AB",
            "renderer": "threejs_3d",
            "view": {"dimension": "3d"},
            "objects": [
                {"type": "point_3d", "name": "A", "x": 0.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "B", "x": 2.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "M", "x": 1.5, "y": 0.1, "z": 0.0},
            ],
            "relations": [{"type": "midpoint", "object_1": "M", "object_2": "A-B"}],
            "cas_issues": [
                {
                    "relation_type": "midpoint",
                    "description": "M lệch khỏi trung điểm",
                    "severity": "warning",
                    "auto_fixed": False,
                    "metadata": {}
                }
            ]
        })
        return scene, ["[CAS] Cảnh báo CAS (midpoint): M lệch khỏi trung điểm"]

    # Mock build_render_payload to not crash or do real rendering logic
    def mock_build_render_payload(scene, settings):
        from app.schemas.scene import RenderPayload
        return RenderPayload(renderer="threejs_3d", three_scene={"computed": {"warnings": []}})

    app.dependency_overrides[require_active_user] = mock_active_user
    monkeypatch.setattr("app.api.routes_render.enforce_rate_limit", mock_noop)
    monkeypatch.setattr("app.api.routes_render.enforce_render_access", mock_noop)
    monkeypatch.setattr("app.services.extractor.extract_scene", mock_extract_scene)
    monkeypatch.setattr("app.services.renderer_router.build_render_payload", mock_build_render_payload)

    try:
        client = TestClient(app)
        # Test render endpoint
        response = client.post("/api/render", json={
            "problem_text": "M là trung điểm AB",
            "grade": 10,
            "tier": "tier1"
        })
        assert response.status_code == 200
        payload = response.json()
        assert "cas_issues" in payload
        assert len(payload["cas_issues"]) == 1
        assert payload["cas_issues"][0]["relation_type"] == "midpoint"
        assert payload["cas_issues"][0]["description"] == "M lệch khỏi trung điểm"
        assert payload["cas_issues"][0]["severity"] == "warning"
        assert payload["advisory"]["classification"]["task_type"] == "render_scene"
        assert payload["advisory"]["risk_score"] >= 15

        # Test render/scene endpoint
        scene_data = {
            "problem_text": "M là trung điểm AB",
            "renderer": "threejs_3d",
            "view": {"dimension": "3d", "show_axes": True, "show_grid": True, "show_coordinates": False},
            "objects": [
                {"type": "point_3d", "name": "A", "x": 0.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "B", "x": 2.0, "y": 0.0, "z": 0.0},
                {"type": "point_3d", "name": "M", "x": 1.5, "y": 0.1, "z": 0.0},
            ],
            "relations": [{"type": "midpoint", "object_1": "M", "object_2": "A-B"}],
            "cas_issues": [
                {
                    "relation_type": "midpoint",
                    "description": "M lệch khỏi trung điểm",
                    "severity": "warning",
                    "auto_fixed": False,
                    "metadata": {}
                }
            ]
        }
        response_scene = client.post("/api/render/scene", json={
            "scene": scene_data,
            "advanced_settings": {}
        })
        assert response_scene.status_code == 200
        payload_scene = response_scene.json()
        assert "cas_issues" in payload_scene
        assert len(payload_scene["cas_issues"]) == 1
        assert payload_scene["cas_issues"][0]["relation_type"] == "midpoint"
        assert payload_scene["advisory"]["classification"]["task_type"] == "render_scene"
    finally:
        app.dependency_overrides.clear()
