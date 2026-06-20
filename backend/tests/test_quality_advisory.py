from app.schemas.scene import CasIssueResponse, MathScene, RenderPayload
from app.services.quality_advisory import build_render_advisory, build_solve_advisory
from app.services.solver_service import SolverResult, SolverStep


def _scene(topic: str = "solid_geometry", objects: list[dict] | None = None, cas_issues: list[dict] | None = None) -> MathScene:
    return MathScene.model_validate(
        {
            "problem_text": "Cho hình chóp S.ABCD có SA vuông góc với đáy.",
            "topic": topic,
            "renderer": "threejs_3d",
            "view": {"dimension": "3d"},
            "objects": objects
            if objects is not None
            else [
                {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 3},
                {"type": "point_3d", "name": "B", "x": 0, "y": 0, "z": 0},
                {"type": "point_3d", "name": "C", "x": 4, "y": 0, "z": 0},
                {"type": "point_3d", "name": "D", "x": 0, "y": 4, "z": 0},
            ],
            "cas_issues": cas_issues or [],
        }
    )


def test_render_advisory_clean_scene_has_low_risk():
    scene = _scene()
    advisory = build_render_advisory(scene.problem_text, 12, scene, [], [], None)

    assert advisory.risk_level == "low"
    assert advisory.quality_score >= 90
    assert advisory.classification.topic == "solid_geometry"


def test_render_advisory_unknown_empty_scene_has_high_risk():
    scene = _scene(topic="unknown", objects=[])
    advisory = build_render_advisory(scene.problem_text, 12, scene, [], [], None)

    assert advisory.risk_level in {"high", "critical"}
    assert {factor.code for factor in advisory.factors}.issuperset({"unknown_topic", "empty_scene"})
    assert advisory.quality_score <= 40


def test_render_advisory_counts_cas_unresolved_and_auto_fixed():
    scene = _scene(
        cas_issues=[
            {"relation_type": "midpoint", "description": "M lệch khỏi trung điểm", "severity": "warning", "auto_fixed": False},
            {"relation_type": "on_line", "description": "Đã đưa M về AB", "severity": "warning", "auto_fixed": True},
        ]
    )
    advisory = build_render_advisory(scene.problem_text, 12, scene, [], scene.cas_issues, None)
    codes = {factor.code for factor in advisory.factors}

    assert "cas_unresolved" in codes
    assert "cas_auto_fixed" in codes
    assert advisory.risk_score >= 20


def test_render_advisory_uses_payload_computed_warnings():
    scene = _scene()
    payload = RenderPayload(renderer="threejs_3d", three_scene={"computed": {"warnings": ["line-plane degenerate"]}})
    advisory = build_render_advisory(scene.problem_text, 12, scene, [], [], payload)

    assert any(factor.code == "computed_warnings" for factor in advisory.factors)


def test_solve_advisory_verified_result_has_low_risk():
    result = SolverResult(
        "d(A,(BCD))",
        "d(A,(BCD)) = 3",
        [
            SolverStep(1, "Input", "", None, None, ["A", "B", "C", "D"], kind="input"),
            SolverStep(2, "Formula", "", None, None, ["A", "B", "C", "D"], kind="distance_point_plane"),
            SolverStep(3, "Result", "", None, "3", ["A", "B", "C", "D"], kind="result"),
        ],
        [],
        confidence="verified",
    )
    advisory = build_solve_advisory("d(A,(BCD))", {"topic": "coordinate_3d"}, result)

    assert advisory.risk_level == "low"
    assert advisory.classification.task_type == "distance"
    assert advisory.classification.sub_type == "point_plane"


def test_solve_advisory_insufficient_result_has_high_risk():
    result = SolverResult(
        "hãy giải thích ý nghĩa hình học",
        "Không xác định",
        [],
        ["Chưa nhận diện được dạng bài."],
        confidence="insufficient",
    )
    advisory = build_solve_advisory("hãy giải thích ý nghĩa hình học", {"topic": "coordinate_3d"}, result)

    assert advisory.risk_level in {"high", "critical"}
    assert any(factor.code == "solver_unsupported" for factor in advisory.factors)
    assert advisory.recommendations
