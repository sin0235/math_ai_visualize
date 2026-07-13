"""Unit tests for native Scene v3 extraction helpers."""

import pytest

from app.schemas.scene_v3 import MathSceneV3
from app.services.extractor_v3 import (
    extract_scene_v3,
    extract_scene_v3_mock,
    normalize_scene_v3_json,
    parse_math_scene_v3,
)
from app.services.scene_pipeline_v3 import run_scene_pipeline_v3


def test_mock_extracts_points_and_segment_native():
    scene = extract_scene_v3_mock("Cho A(0,0), B(2,0).", grade=10)
    assert isinstance(scene, MathSceneV3)
    assert scene.schema_version == "3.0"
    assert scene.problem_text == "Cho A(0,0), B(2,0)."
    assert scene.grade == 10
    labels = {obj.label for obj in scene.objects if obj.label}
    assert {"A", "B"}.issubset(labels)
    assert any(obj.type == "segment" for obj in scene.objects)
    result = run_scene_pipeline_v3(scene)
    assert result.can_project
    assert result.status in {"verified", "partially_verified", "needs_confirmation"}


def test_mock_3d_points():
    scene = extract_scene_v3_mock("Cho A(0,0,0), B(1,0,0), C(0,1,0).")
    assert scene.renderer == "threejs_3d"
    assert scene.view.dimension == "3d"
    assert all(obj.type in {"point_3d", "segment"} for obj in scene.objects)
    assert run_scene_pipeline_v3(scene).can_project


def test_parse_fills_missing_ids_and_preserves_problem_text():
    raw = {
        "topic": "coordinate_2d",
        "renderer": "geogebra_2d",
        "objects": [
            {"type": "point_2d", "label": "A", "x": 0, "y": 0},
            {"type": "point_2d", "label": "B", "x": 3, "y": 0},
            {"type": "segment", "label": "AB", "point_ids": []},  # filled below after ids
        ],
        "view": {"dimension": "2d"},
        "audit": {"created_by": "test"},
    }
    normalized = normalize_scene_v3_json(raw, problem_text="nguyên văn đề", grade=11)
    # Wire segment after id assignment
    ids = {obj["label"]: obj["id"] for obj in normalized["objects"] if obj.get("label")}
    for obj in normalized["objects"]:
        if obj.get("type") == "segment":
            obj["point_ids"] = [ids["A"], ids["B"]]
    scene = parse_math_scene_v3(normalized, problem_text="nguyên văn đề", grade=11)
    assert scene.problem_text == "nguyên văn đề"
    assert scene.grade == 11
    assert all(obj.id for obj in scene.objects)


def test_native_midpoint_relation_contract_passes():
    scene = parse_math_scene_v3(
        {
            "scene_id": "mid-test",
            "topic": "coordinate_2d",
            "renderer": "geogebra_2d",
            "objects": [
                {"id": "pt_a", "type": "point_2d", "label": "A", "x": 0, "y": 0},
                {"id": "pt_b", "type": "point_2d", "label": "B", "x": 2, "y": 0},
                {"id": "pt_m", "type": "point_2d", "label": "M", "x": 1, "y": 0},
                {"id": "seg_ab", "type": "segment", "label": "AB", "point_ids": ["pt_a", "pt_b"]},
            ],
            "relations": [
                {
                    "id": "rel_mid",
                    "type": "midpoint",
                    "operands": [
                        {"role": "point", "ref_id": "pt_m", "ref_kind": "point"},
                        {"role": "segment", "ref_id": "seg_ab", "ref_kind": "segment"},
                    ],
                }
            ],
            "view": {"dimension": "2d"},
            "audit": {"created_by": "test"},
        },
        problem_text="Cho M trung điểm AB",
        grade=10,
    )
    result = run_scene_pipeline_v3(scene)
    assert not any(issue.code == "RELATION_CONTRACT_INVALID" for issue in result.issues)
    assert result.can_project


def test_shorthand_style_point_operands_on_perpendicular_fails_contract():
    """Documents the old bridge failure mode: two points for linear relation."""
    scene = parse_math_scene_v3(
        {
            "scene_id": "bad-perp",
            "topic": "solid_geometry",
            "renderer": "threejs_3d",
            "objects": [
                {"id": "pt_s", "type": "point_3d", "label": "S", "x": 0, "y": 3, "z": 0},
                {"id": "pt_a", "type": "point_3d", "label": "A", "x": 0, "y": 0, "z": 0},
                {"id": "pt_b", "type": "point_3d", "label": "B", "x": 4, "y": 0, "z": 0},
                {"id": "pt_c", "type": "point_3d", "label": "C", "x": 4, "y": 0, "z": 4},
                {
                    "id": "pl_base",
                    "type": "plane",
                    "label": "ABCD",
                    "point_ids": ["pt_a", "pt_b", "pt_c"],
                },
            ],
            "relations": [
                {
                    "id": "rel_bad",
                    "type": "perpendicular",
                    "operands": [
                        {"role": "a", "ref_id": "pt_s", "ref_kind": "point"},
                        {"role": "b", "ref_id": "pt_a", "ref_kind": "point"},
                    ],
                }
            ],
            "view": {"dimension": "3d"},
            "audit": {"created_by": "test"},
        },
        problem_text="SA vuông góc đáy",
        grade=11,
    )
    result = run_scene_pipeline_v3(scene)
    assert any(issue.code == "RELATION_CONTRACT_INVALID" for issue in result.issues)
    assert not result.can_project


@pytest.mark.anyio
async def test_extract_scene_v3_fails_closed_without_mock(monkeypatch):
    """When every provider fails, do not return a mock figure."""
    from app.core.config import Settings
    from app.services.model_registry import registry_from_settings
    from app.schemas.scene import AdvancedRenderSettings

    settings = Settings(_env_file=None, allow_render_mock=False, database_backend="sqlite")

    class _Cand:
        provider_id = "openrouter"
        model_id = "fake-model"

    async def fake_settings(*_a, **_k):
        return settings

    async def fake_registry(*_a, **_k):
        return registry_from_settings(settings)

    async def fake_prompts(*_a, **_k):
        return ("sys", "reason")

    async def fail_extract(*_a, **_k):
        raise RuntimeError("provider down")

    monkeypatch.setattr("app.services.extractor_v3.resolve_effective_settings", fake_settings)
    monkeypatch.setattr("app.services.extractor_v3.load_model_registry", fake_registry)
    monkeypatch.setattr("app.services.extractor_v3.registry_from_settings", lambda *_a, **_k: registry_from_settings(settings))
    monkeypatch.setattr("app.services.extractor_v3.get_system_prompts", fake_prompts)
    monkeypatch.setattr("app.services.extractor_v3.resolve_render_tier_candidates", lambda *_a, **_k: [_Cand()])
    monkeypatch.setattr("app.services.extractor_v3._extract_with_provider", fail_extract)

    with pytest.raises(RuntimeError, match="không dựng hình giả|thất bại"):
        await extract_scene_v3(
            "Cho A(0,0), B(1,0).",
            tier="tier1",
            advanced_settings=AdvancedRenderSettings(reasoning_layer="off"),
        )
