import pytest

from app.api.routes_solve import SolveRequest, router, solve_problem
from app.core.config import Settings
from app.db.models import UserRecord
from app.services.model_registry import registry_from_settings


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


def _scene() -> dict:
    return {
        "problem_text": "Cho hình chóp S.ABCD có SA = 3 và SA vuông góc với đáy.",
        "topic": "solid_geometry",
        "objects": [
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 3},
            {"type": "point_3d", "name": "B", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 4, "z": 0},
        ],
        "annotations": [
            {
                "type": "length",
                "target": "A-B",
                "label": "3",
                "metadata": {"source": "given", "confidence": "partial", "evidence": "SA = 3"},
            }
        ],
        "relations": [
            {
                "type": "perpendicular",
                "object_1": "AB",
                "object_2": "plane(BCD)",
                "metadata": {"source": "given", "confidence": "verified", "evidence": "SA vuông góc với đáy"},
            }
        ],
    }


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

    monkeypatch.setattr("app.api.routes_solve.enforce_rate_limit", mock_noop)
    monkeypatch.setattr("app.api.routes_solve.enforce_render_access", mock_noop)
    monkeypatch.setattr("app.api.routes_solve.resolve_effective_settings", mock_settings)
    monkeypatch.setattr("app.api.routes_solve.load_model_registry", mock_registry)

    payload = await solve_problem(
        SolveRequest(scene=_scene(), question="d(A,(BCD))", geometry_method="classical"),
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
