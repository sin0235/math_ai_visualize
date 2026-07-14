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


def test_parse_wraps_scalar_interpretation_values_without_losing_data():
    scene = parse_math_scene_v3(
        {
            "topic": "solid_geometry",
            "renderer": "threejs_3d",
            "objects": [],
            "view": {"dimension": "3d"},
            "interpretation": {"values": [18, {"name": "edge", "value": 3}]},
            "audit": {"created_by": "test"},
        },
        problem_text="Cho hình có thể tích 18.",
        grade=11,
    )

    assert scene.interpretation.values == [
        {"value": 18},
        {"name": "edge", "value": 3},
    ]


def test_parse_converts_unknown_distance_goal_to_render_only_measurement():
    scene = parse_math_scene_v3(
        {
            "topic": "solid_geometry",
            "renderer": "threejs_3d",
            "objects": [
                {"id": "pt_m", "type": "point_3d", "label": "M", "x": 0, "y": 2, "z": 0},
                {"id": "pt_p", "type": "point_3d", "label": "P", "x": 0, "y": 0, "z": 0},
                {"id": "pt_f", "type": "point_3d", "label": "F", "x": 1, "y": 0, "z": 0},
                {"id": "pt_b", "type": "point_3d", "label": "B", "x": 0, "y": 0, "z": 1},
                {"id": "plane_pfb", "type": "plane", "label": "PFB", "point_ids": ["pt_p", "pt_f", "pt_b"]},
            ],
            "relations": [{
                "id": "rel_distance_m_plane_pfb",
                "type": "distance",
                "operands": [
                    {"role": "point", "ref_id": "pt_m", "ref_kind": "point"},
                    {"role": "plane", "ref_id": "plane_pfb", "ref_kind": "plane"},
                ],
                "args": {},
                "source": "ai_inferred",
            }],
            "view": {"dimension": "3d"},
            "audit": {"created_by": "test"},
        },
        problem_text="Tính khoảng cách từ M đến mặt phẳng (PFB).",
        grade=11,
    )

    assert scene.relations == []
    assert len(scene.derived_facts) == 1
    goal = scene.derived_facts[0]
    assert goal.kind == "measurement"
    assert goal.provenance == "render_only"
    assert goal.source_ids == ["pt_m", "plane_pfb"]
    assert goal.value["quantity"] == "distance"
    result = run_scene_pipeline_v3(scene)
    assert result.status == "verified"
    assert result.can_project


def test_parse_rejects_given_distance_without_expected_value():
    with pytest.raises(ValueError, match=r"rel_distance_given cần args\.value"):
        parse_math_scene_v3(
            {
                "topic": "coordinate_2d",
                "renderer": "geogebra_2d",
                "objects": [
                    {"id": "pt_a", "type": "point_2d", "label": "A", "x": 0, "y": 0},
                    {"id": "pt_b", "type": "point_2d", "label": "B", "x": 3, "y": 0},
                ],
                "relations": [{
                    "id": "rel_distance_given",
                    "type": "distance",
                    "operands": [
                        {"role": "first", "ref_id": "pt_a", "ref_kind": "point"},
                        {"role": "second", "ref_id": "pt_b", "ref_kind": "point"},
                    ],
                    "args": {},
                    "source": "given",
                }],
                "view": {"dimension": "2d"},
                "audit": {"created_by": "test"},
            },
            problem_text="Cho AB có độ dài xác định.",
            grade=10,
        )


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


@pytest.mark.anyio
async def test_extract_scene_v3_falls_back_when_first_candidate_has_ambiguous_solid(monkeypatch):
    from app.core.config import Settings
    from app.schemas.scene import AdvancedRenderSettings
    from app.services.model_registry import registry_from_settings

    settings = Settings(_env_file=None, allow_render_mock=False, database_backend="sqlite")

    class _Candidate:
        provider_id = "openrouter"

        def __init__(self, model_id: str):
            self.model_id = model_id

    async def fake_settings(*_args, **_kwargs):
        return settings

    async def fake_registry(*_args, **_kwargs):
        return registry_from_settings(settings)

    async def fake_prompts(*_args, **_kwargs):
        return "sys", "reason"

    async def fake_extract(*_args, preferred_ai_model=None, **_kwargs):
        if preferred_ai_model == "bad-model":
            return {
                "topic": "solid_geometry",
                "renderer": "threejs_3d",
                "objects": [
                    {"id": "pt_x", "type": "point_3d", "label": "X", "x": 0, "y": 0, "z": 0},
                ],
                "view": {"dimension": "3d"},
                "audit": {"created_by": "test"},
            }
        return {
            "topic": "solid_geometry",
            "renderer": "threejs_3d",
            "objects": [
                {
                    "id": f"pt_{label.lower()}",
                    "type": "point_3d",
                    "label": label,
                    "x": index % 4,
                    "y": index // 4,
                    "z": (index // 2) % 2,
                }
                for index, label in enumerate("ABCDEFGH")
            ],
            "view": {"dimension": "3d"},
            "audit": {"created_by": "test"},
        }

    monkeypatch.setattr("app.services.extractor_v3.resolve_effective_settings", fake_settings)
    monkeypatch.setattr("app.services.extractor_v3.load_model_registry", fake_registry)
    monkeypatch.setattr("app.services.extractor_v3.get_system_prompts", fake_prompts)
    monkeypatch.setattr(
        "app.services.extractor_v3.resolve_render_tier_candidates",
        lambda *_args, **_kwargs: [_Candidate("bad-model"), _Candidate("good-model")],
    )
    monkeypatch.setattr("app.services.extractor_v3._extract_with_provider", fake_extract)

    result = await extract_scene_v3(
        "Cho một hình hộp chữ nhật.",
        tier="tier2",
        advanced_settings=AdvancedRenderSettings(reasoning_layer="off"),
    )

    assert result.model == "good-model"
    assert len(result.attempts) == 1
    assert "SOLID_TOPOLOGY_AMBIGUOUS" in result.attempts[0].message
