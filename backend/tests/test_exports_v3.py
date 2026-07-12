from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes_export import export_svg
from app.db.models import UserRecord
from app.renderers.projection_export_v3 import (
    build_ggb_v3,
    build_image_v3,
    build_katex_html_v3,
    build_pdf_v3,
    build_tikz_document_v3,
)
from app.schemas.scene_v3 import MathSceneV3, SceneExportRequestV3
from app.services.committed_scene_v3 import CommittedSceneError
from app.services.scene_pipeline_v3 import run_scene_pipeline_v3


def _result():
    scene = MathSceneV3.model_validate({
        "scene_id": "export-v3",
        "revision": 2,
        "problem_text": "Cho tam giác ABC.",
        "topic": "coordinate_2d",
        "renderer": "geogebra_2d",
        "view": {"dimension": "2d"},
        "objects": [
            {"id": "a", "type": "point_2d", "label": "A", "x": 0, "y": 0},
            {"id": "b", "type": "point_2d", "label": "B", "x": 4, "y": 0},
            {"id": "c", "type": "point_2d", "label": "C", "x": 0, "y": 3},
            {"id": "ab", "type": "segment", "point_ids": ["a", "b"]},
            {"id": "bc", "type": "segment", "point_ids": ["b", "c"]},
            {"id": "ca", "type": "segment", "point_ids": ["c", "a"]},
        ],
        "annotations": [{
            "id": "length-ab",
            "type": "length",
            "target_ids": ["a", "b"],
            "label": "4",
            "provenance": "given",
        }],
        "audit": {"created_by": "manual"},
    })
    result = run_scene_pipeline_v3(scene)
    assert result.status == "verified"
    return result


def _user() -> UserRecord:
    return UserRecord(
        id="export-user",
        email="export@example.com",
        password_hash="",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        status="active",
        email_verified_at="2024-01-01T00:00:00Z",
    )


def test_projection_v3_exports_without_math_scene_v2():
    result = _result()
    projection = result.projection
    problem_text = result.scene.problem_text

    assert "\\begin{tikzpicture}" in build_tikz_document_v3(projection, problem_text)
    assert build_ggb_v3(projection, problem_text).startswith(b"PK")
    assert build_pdf_v3(projection, problem_text).startswith(b"%PDF-")
    assert build_image_v3(projection, problem_text, "png").startswith(b"\x89PNG")
    assert "<svg" in build_image_v3(projection, problem_text, "svg")
    assert "katex.min.css" in build_katex_html_v3(projection, problem_text)


@pytest.mark.anyio
async def test_export_route_loads_committed_reference(monkeypatch):
    result = _result()
    captured = {}

    async def noop(*args, **kwargs):
        return None

    async def load(db, user_id, reference):
        captured["user_id"] = user_id
        captured["reference"] = reference
        return SimpleNamespace(result=result)

    monkeypatch.setattr("app.api.routes_export.enforce_rate_limit", noop)
    monkeypatch.setattr("app.api.routes_export.enforce_render_access", noop)
    monkeypatch.setattr("app.api.routes_export.try_log_user_activity", noop)
    monkeypatch.setattr("app.api.routes_export.load_committed_scene_v3", load)

    response = await export_svg(
        SceneExportRequestV3(scene_ref={"scene_id": "export-v3", "revision": 2}),
        http_request=object(),
        user=_user(),
        db=object(),
    )

    assert response.status_code == 200
    assert b"<svg" in response.body
    assert captured["user_id"] == "export-user"
    assert captured["reference"].revision == 2


@pytest.mark.anyio
async def test_export_route_preserves_boundary_error_code(monkeypatch):
    async def noop(*args, **kwargs):
        return None

    async def stale(*args, **kwargs):
        raise CommittedSceneError("SCENE_EDIT_STALE", "Revision cũ.", 409)

    monkeypatch.setattr("app.api.routes_export.enforce_rate_limit", noop)
    monkeypatch.setattr("app.api.routes_export.enforce_render_access", noop)
    monkeypatch.setattr("app.api.routes_export.load_committed_scene_v3", stale)

    with pytest.raises(HTTPException) as error:
        await export_svg(
            SceneExportRequestV3(scene_ref={"scene_id": "export-v3", "revision": 1}),
            http_request=object(),
            user=_user(),
            db=object(),
        )

    assert error.value.status_code == 409
    assert error.value.detail["code"] == "SCENE_EDIT_STALE"