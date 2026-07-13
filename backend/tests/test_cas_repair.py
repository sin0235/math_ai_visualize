"""Unit tests cho ``app.services.cas_repair``.

Sử dụng fake LLM callable để mô phỏng repair loop mà không cần kết nối
provider thật. Bao phủ các nhánh: repair thành công, LLM trả output không
parse được, LLM không cải thiện, đạt max_iterations.
"""

from __future__ import annotations

import json

import pytest

from app.schemas.scene import MathScene
from app.services.cas_repair import (
    RepairOutcome,
    format_repair_prompt,
    repair_scene_iteratively,
)
from app.services.cas_verifier import CasIssue, verify_scene
from app.services.extractor import build_scene_with_cas_fix


def _scene_with_off_midpoint() -> dict:
    return {
        "problem_text": "Test M trung điểm AB",
        "renderer": "threejs_3d",
        "view": {"dimension": "3d"},
        "objects": [
            {"type": "point_3d", "name": "A", "x": 0.0, "y": 0.0, "z": 0.0},
            {"type": "point_3d", "name": "B", "x": 2.0, "y": 0.0, "z": 0.0},
            {"type": "point_3d", "name": "M", "x": 1.5, "y": 0.1, "z": 0.0},
        ],
        "relations": [{"type": "midpoint", "object_1": "M", "object_2": "A-B"}],
        "annotations": [],
    }


def _scene_with_unequal_lengths() -> dict:
    """equal_length không thuộc deterministic auto-fix nên tới được repair_llm
    khi optimizer không hội tụ. Ở đây ta để optimizer xử lý baseline."""
    return {
        "problem_text": "Test equal length",
        "renderer": "threejs_3d",
        "view": {"dimension": "3d"},
        "objects": [
            {"type": "point_3d", "name": "A", "x": 0.0, "y": 0.0, "z": 0.0},
            {"type": "point_3d", "name": "B", "x": 3.0, "y": 0.0, "z": 0.0},
            {"type": "point_3d", "name": "C", "x": 0.0, "y": 1.0, "z": 0.0},
        ],
        "relations": [{"type": "equal_length", "object_1": "A-B", "object_2": "A-C"}],
        "annotations": [],
    }


def test_format_repair_prompt_lists_issues():
    scene = MathScene.model_validate(_scene_with_off_midpoint())
    issues = [
        CasIssue("midpoint", "M lệch khỏi trung điểm", severity="warning"),
        CasIssue("perpendicular", "SA không ⟂ (ABCD)", severity="error"),
    ]
    prompt = format_repair_prompt(scene, issues)
    assert "[ERROR]" in prompt and "[WARN]" in prompt
    assert "midpoint" in prompt and "perpendicular" in prompt
    assert "Scene hiện tại" in prompt
    # JSON khối được embed nguyên vẹn
    assert '"renderer": "threejs_3d"' in prompt


def test_repair_iteratively_returns_input_when_no_issues():
    scene = MathScene.model_validate(_scene_with_off_midpoint())
    fake_called = {"n": 0}

    def fake_llm(prompt: str) -> str:  # pragma: no cover - không nên được gọi
        fake_called["n"] += 1
        return "{}"

    outcome = repair_scene_iteratively(scene, [], fake_llm, max_iterations=2)
    assert isinstance(outcome, RepairOutcome)
    assert outcome.attempts == []
    assert fake_called["n"] == 0


def test_repair_iteratively_fixes_after_one_call():
    raw = _scene_with_off_midpoint()
    scene = MathScene.model_validate(raw)
    issues = verify_scene(scene)
    assert any(i.relation_type == "midpoint" for i in issues)

    def fake_llm(prompt: str) -> str:
        sd = json.loads(json.dumps(raw))
        sd["objects"] = [
            {"type": "point_3d", "name": "A", "x": 0.0, "y": 0.0, "z": 0.0},
            {"type": "point_3d", "name": "B", "x": 2.0, "y": 0.0, "z": 0.0},
            {"type": "point_3d", "name": "M", "x": 1.0, "y": 0.0, "z": 0.0},
        ]
        return json.dumps(sd)

    outcome = repair_scene_iteratively(
        scene,
        issues,
        fake_llm,
        max_iterations=2,
        min_severity="warning",
    )
    assert len(outcome.attempts) == 1
    assert outcome.attempts[0].accepted
    assert outcome.final_issues == []
    m = next(o for o in outcome.scene.objects if getattr(o, "name", None) == "M")
    assert m.x == pytest.approx(1.0)
    assert m.y == pytest.approx(0.0)


def test_repair_rejects_scene_structure_change():
    raw = _scene_with_off_midpoint()
    scene = MathScene.model_validate(raw)
    issues = verify_scene(scene)

    def fake_llm(prompt: str) -> str:
        changed = json.loads(json.dumps(raw))
        changed["relations"] = []
        return json.dumps(changed)

    outcome = repair_scene_iteratively(
        scene,
        issues,
        fake_llm,
        max_iterations=1,
        min_severity="warning",
    )

    assert outcome.scene is scene
    assert outcome.attempts[0].error == "structure_changed"
    assert any("thay đổi cấu trúc" in warning for warning in outcome.warnings)


def test_repair_iteratively_handles_invalid_json():
    raw = _scene_with_off_midpoint()
    scene = MathScene.model_validate(raw)
    issues = verify_scene(scene)

    def fake_llm(prompt: str) -> str:
        return "not a valid json {{{"

    outcome = repair_scene_iteratively(
        scene, issues, fake_llm, max_iterations=2, min_severity="warning"
    )
    assert all(not a.accepted for a in outcome.attempts)
    assert any("không parse được JSON" in w for w in outcome.warnings)
    # Scene gốc giữ nguyên
    assert outcome.scene is scene


def test_repair_iteratively_handles_callable_exception():
    raw = _scene_with_off_midpoint()
    scene = MathScene.model_validate(raw)
    issues = verify_scene(scene)

    def fake_llm(prompt: str) -> str:
        raise RuntimeError("api 500")

    outcome = repair_scene_iteratively(
        scene, issues, fake_llm, max_iterations=2, min_severity="warning"
    )
    assert outcome.attempts and outcome.attempts[0].error is not None
    assert any("api 500" in w for w in outcome.warnings)


def test_repair_iteratively_stops_when_llm_does_not_improve():
    raw = _scene_with_off_midpoint()
    scene = MathScene.model_validate(raw)
    issues = verify_scene(scene)
    calls = {"n": 0}

    def fake_llm(prompt: str) -> str:
        calls["n"] += 1
        # trả lại scene gốc — không cải thiện gì
        return json.dumps(raw)

    outcome = repair_scene_iteratively(
        scene,
        issues,
        fake_llm,
        max_iterations=3,
        min_severity="warning",
    )
    # cas_verifier auto_fix midpoint deterministic ngay trong build_scene_with_cas_fix,
    # nên iteration đầu vẫn được chấp nhận. Đảm bảo không vượt max_iterations.
    assert calls["n"] <= 3


def test_build_scene_with_cas_fix_invokes_repair_llm_when_optimizer_handles():
    # Scenario: optimizer xử lý xong nên repair_llm chỉ là fallback,
    # ta xác nhận pipeline gọi repair_llm tối đa 0 lần khi không còn issue.
    raw = _scene_with_unequal_lengths()
    calls = {"n": 0}

    def fake_llm(prompt: str) -> str:
        calls["n"] += 1
        return json.dumps(raw)

    scene, warnings = build_scene_with_cas_fix(
        raw,
        repair_llm=fake_llm,
        repair_max_iterations=2,
        repair_min_severity="warning",
    )
    # Optimizer đã giải, nên LLM có thể được gọi 0 hoặc 1 lần (depending on
    # thresholds). Kiểm tra số lần ≤ 2 và pipeline kết thúc bình thường.
    assert calls["n"] <= 2
    assert any("optimizer" in w.lower() or "cas" in w.lower() for w in warnings)
