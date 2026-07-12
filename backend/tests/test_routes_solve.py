from types import SimpleNamespace

import pytest

from app.api.routes_solve import SolveRequest, router, solve_problem
from app.core.config import Settings
from app.db.models import UserRecord
from app.schemas.scene_v3 import MathSceneV3
from app.services.model_registry import registry_from_settings
from app.services.scene_pipeline_v3 import run_scene_pipeline_v3


def _user() -> UserRecord:
    return UserRecord(
        id="test_user",
        email="test@example.com",
        password_hash="",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        status="active",
        email_verified_at="2024-01-01T00:00:00Z",
    )


def _scene() -> MathSceneV3:
    return MathSceneV3.model_validate({
        "scene_id": "solve-scene",
        "revision": 3,
        "problem_text": "Cho hình chóp S.ABCD có SA = 3 và SA vuông góc với đáy.",
        "topic": "solid_geometry",
        "renderer": "threejs_3d",
        "view": {"dimension": "3d"},
        "objects": [
            {"id": "point-a", "type": "point_3d", "label": "A", "x": 0, "y": 0, "z": 3},
            {"id": "point-b", "type": "point_3d", "label": "B", "x": 0, "y": 0, "z": 0},
            {"id": "point-c", "type": "point_3d", "label": "C", "x": 4, "y": 0, "z": 0},
            {"id": "point-d", "type": "point_3d", "label": "D", "x": 0, "y": 4, "z": 0},
        ],
        "annotations": [{
            "id": "length-ab",
            "type": "length",
            "target_ids": ["point-a", "point-b"],
            "label": "3",
            "provenance": "given",
        }],
        "audit": {"created_by": "manual"},
    })


def test_solve_route_registered():
    paths = {route.path for route in router.routes}
    assert "/api/solve" in paths


@pytest.mark.anyio
async def test_solve_endpoint_returns_trust_metadata(monkeypatch):
    settings = Settings(router9_api_key="", openrouter_api_key="")

    async def mock_noop(*args, **kwargs):
        return None

    async def mock_settings(*args, **kwargs):
        return settings

    async def mock_registry(*args, **kwargs):
        return registry_from_settings(settings)

    async def mock_committed(*args, **kwargs):
        return SimpleNamespace(result=run_scene_pipeline_v3(_scene()))

    monkeypatch.setattr("app.api.routes_solve.enforce_rate_limit", mock_noop)
    monkeypatch.setattr("app.api.routes_solve.enforce_render_access", mock_noop)
    monkeypatch.setattr("app.api.routes_solve.resolve_effective_settings", mock_settings)
    monkeypatch.setattr("app.api.routes_solve.load_model_registry", mock_registry)
    monkeypatch.setattr("app.api.routes_solve.load_committed_scene_v3", mock_committed)

    payload = await solve_problem(
        SolveRequest(
            scene_ref={"scene_id": "solve-scene", "revision": 3},
            question="d(A,(BCD))",
            geometry_method="classical",
        ),
        http_request=object(),
        user=_user(),
        db=object(),
    )

    assert payload.answer == "d(A,(BCD)) = 3"
    assert payload.method == "classical"
    assert payload.confidence == "verified"
    assert any(fact["source"] == "given" for fact in payload.used_facts)
    assert payload.data_issues == []
    assert payload.advisory is not None
    assert payload.advisory.classification.task_type == "distance"
    assert payload.advisory.classification.sub_type == "point_plane"
    assert payload.advisory.risk_level == "low"
