import pytest

from app.services import solver_explainer
from app.services.solver_service import solve
from app.services.solver_service import SolverResult, SolverStep


@pytest.fixture
def scene():
    return {
        "objects": [
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 3},
            {"type": "point_3d", "name": "B", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 4, "z": 0},
            {"type": "point_3d", "name": "E", "x": 4, "y": 4, "z": 0},
            {"type": "point_3d", "name": "S", "x": 0, "y": 0, "z": 6},
            {"type": "face", "points": ["B", "C", "E", "D"]},
        ]
    }


def test_solve_point_point_distance(scene):
    result = solve(scene, "d(B,C)")

    assert result.answer == "d(B,C) = 4"
    assert result.steps[1].formula_latex
    assert result.steps[1].substitution_latex
    assert result.steps[2].result_latex == "4"


def test_solve_point_point_distance_exact_radical():
    scene = {"objects": [
        {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
        {"type": "point_3d", "name": "B", "x": 1, "y": 1, "z": 1},
    ]}

    result = solve(scene, "d(A,B)")

    assert result.answer == "d(A,B) = 1.732051"
    assert result.steps[2].result_latex == "\\sqrt{3}"


def test_solve_point_line_distance(scene):
    result = solve(scene, "d(A,BC)")

    assert result.answer == "d(A,BC) = 3"
    assert result.steps[1].kind == "distance_point_line"


def test_solve_point_plane_distance(scene):
    result = solve(scene, "d(A,(BCD))")

    assert result.answer == "d(A,(BCD)) = 3"
    assert result.steps[1].kind == "distance_point_plane"


def test_classical_solver_uses_deterministic_safe_template(scene):
    annotated_scene = {
        **scene,
        "annotations": [{"type": "length", "target": "A-B", "label": "3", "metadata": {}}],
        "relations": [{"type": "perpendicular", "object_1": "AB", "object_2": "plane(BCD)", "metadata": {}}],
    }
    result = solve(annotated_scene, "d(A,(BCD))", geometry_method="classical")

    assert result.answer == "d(A,(BCD)) = 3"
    assert result.steps[1].title == "Nhận ra đường cao"
    explanations = " ".join(step.explanation for step in result.steps).lower()
    assert "tọa độ" not in explanations
    assert "phép tính" not in explanations
    assert "ab là đoạn vuông góc" in explanations
    assert result.steps[2].explanation == "Mà AB = 3, nên d(A,(BCD)) = AB = 3."
    assert any("template deterministic an toàn" in warning for warning in result.warnings)
    assert result.method == "classical"
    assert result.confidence == "verified"
    assert any(fact["source"] == "given" and "AB = 3" in fact["text"] for fact in result.used_facts)
    assert any(fact["source"] == "verified" and "vuông góc" in fact["text"] for fact in result.used_facts)


def test_metric_solver_rejects_generic_solid_without_metric_evidence():
    generic_scene = {
        "problem_text": "Cho hình chóp S.ABCD.",
        "topic": "solid_geometry",
        "objects": [
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 1, "y": 0, "z": 1},
            {"type": "point_3d", "name": "D", "x": 0, "y": 0, "z": 1},
            {"type": "point_3d", "name": "S", "x": 0, "y": 1, "z": 0},
        ],
    }

    result = solve(generic_scene, "d(S,(ABCD))")

    assert result.answer == "Không đủ dữ kiện"
    assert "không dùng tọa độ minh họa" in result.warnings[-1]
    assert result.confidence == "insufficient"
    assert result.data_issues


def test_metric_solver_rejects_construction_only_metric_label(scene):
    construction_scene = {
        **scene,
        "problem_text": "Cho hình chóp S.BCED.",
        "topic": "solid_geometry",
        "annotations": [
            {
                "type": "length",
                "target": "A-B",
                "label": "3",
                "metadata": {"source": "construction", "confidence": "unverified"},
            }
        ],
    }

    result = solve(construction_scene, "d(A,(BCD))")

    assert result.answer == "Không đủ dữ kiện"
    assert result.confidence == "insufficient"


def test_metric_solver_accepts_given_metric_label(scene):
    given_scene = {
        **scene,
        "problem_text": "Cho AB = 3.",
        "topic": "solid_geometry",
        "annotations": [
            {
                "type": "length",
                "target": "A-B",
                "label": "3",
                "metadata": {"source": "given", "confidence": "partial", "evidence": "AB = 3"},
            }
        ],
    }

    result = solve(given_scene, "d(A,(BCD))")

    assert result.answer == "d(A,(BCD)) = 3"
    assert any(fact["source"] == "given" and "Căn cứ: AB = 3" in fact["text"] for fact in result.used_facts)


def test_solver_used_facts_reflects_inferred_metadata(scene):
    inferred_scene = {
        **scene,
        "problem_text": "ABCD là hình vuông.",
        "topic": "solid_geometry",
        "annotations": [{"type": "length", "target": "A-B", "label": "3", "metadata": {"source": "given", "confidence": "partial"}}],
        "relations": [
            {
                "type": "perpendicular",
                "object_1": "AB",
                "object_2": "BC",
                "metadata": {"source": "inferred", "confidence": "partial", "evidence": "ABCD là hình vuông"},
            }
        ],
    }

    result = solve(inferred_scene, "góc giữa AB và BC")

    assert any(fact["source"] == "inferred" and "ABCD là hình vuông" in fact["text"] for fact in result.used_facts)


def test_angle_solver_allows_verified_qualitative_relation_without_metric_values():
    relation_scene = {
        "problem_text": "Cho AB vuông góc CD.",
        "topic": "solid_geometry",
        "objects": [
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "D", "x": 0, "y": 1, "z": 0},
        ],
        "relations": [{"type": "perpendicular", "object_1": "AB", "object_2": "CD", "metadata": {}}],
    }

    result = solve(relation_scene, "góc giữa AB và CD")

    assert result.answer == "\\angle(AB,CD) = 90°"
    assert result.steps


def test_metric_solver_warns_when_using_parameter_defaults(scene):
    param_scene = {
        **scene,
        "problem_text": "Cho hình chóp với chiều cao h.",
        "topic": "solid_geometry",
        "parameters": [{"name": "h", "label": "Chiều cao h", "min": 1, "max": 8, "default": 3, "step": 0.5}],
    }

    result = solve(param_scene, "d(A,(BCD))")

    assert result.answer == "d(A,(BCD)) = 3"
    assert any("giá trị mặc định" in warning for warning in result.warnings)
    assert result.confidence == "partial"
    assert any(fact["source"] == "parameter_default" for fact in result.used_facts)


def test_solve_line_plane_angle(scene):
    result = solve(scene, "Góc giữa BA và (BCD)")

    assert result.answer == "\\angle(BA,(BCD)) = 90°"
    assert result.steps[1].kind == "angle_line_plane"


def test_classical_line_plane_angle_uses_projection():
    projection_scene = {
        "problem_text": "Cho SA vuông góc với (ABC). Tính góc giữa SB và (ABC).",
        "topic": "solid_geometry",
        "objects": [
            {"type": "point_3d", "name": "S", "x": 0, "y": 0, "z": 3},
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 4, "z": 0},
        ],
        "annotations": [
            {"type": "length", "target": "S-A", "label": "3", "metadata": {"source": "given", "confidence": "partial"}},
            {"type": "length", "target": "A-B", "label": "4", "metadata": {"source": "given", "confidence": "partial"}},
        ],
        "relations": [
            {
                "type": "perpendicular",
                "object_1": "SA",
                "object_2": "plane(ABC)",
                "metadata": {"source": "given", "confidence": "verified"},
            }
        ],
    }

    result = solve(projection_scene, "Góc giữa SB và (ABC)", geometry_method="classical")

    assert result.answer == "\\angle(SB,(ABC)) = 36.869898°"
    assert result.steps[1].title == "Dùng hình chiếu trên mặt phẳng"
    explanations = " ".join(step.explanation for step in result.steps).lower()
    assert "tọa độ" not in explanations
    assert "phép tính" not in explanations
    assert "hình chiếu của s" in explanations
    assert "hình chiếu của sb trên (abc) là ab" in explanations
    assert "góc sba" in explanations


def test_classical_line_plane_angle_detects_perpendicular_line(scene):
    annotated_scene = {
        **scene,
        "annotations": [{"type": "length", "target": "A-B", "label": "3", "metadata": {}}],
        "relations": [{"type": "perpendicular", "object_1": "AB", "object_2": "plane(BCD)", "metadata": {}}],
    }

    result = solve(annotated_scene, "Góc giữa BA và (BCD)", geometry_method="classical")

    assert result.answer == "\\angle(BA,(BCD)) = 90°"
    assert result.steps[1].title == "Nhận ra đường vuông góc mặt phẳng"
    assert "góc giữa BA và (BCD) bằng 90°" in result.steps[2].explanation


def test_classical_plane_plane_angle_template(scene):
    result = solve(scene, "Góc giữa (ABC) và (BCD)", geometry_method="classical")

    assert result.answer.startswith("\\angle((ABC),(BCD))")
    assert result.steps[1].title == "Dựng góc giữa hai mặt phẳng"
    assert "giao tuyến" in result.steps[1].explanation


def test_classical_plane_plane_angle_uses_flat_dihedral_angle():
    dihedral_scene = {
        "problem_text": "Cho (SAB) và (ABC) cắt nhau theo AB, SA vuông góc AB, AC vuông góc AB.",
        "topic": "solid_geometry",
        "objects": [
            {"type": "point_3d", "name": "S", "x": 0, "y": 0, "z": 3},
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 4, "z": 0},
        ],
        "relations": [
            {
                "type": "perpendicular",
                "object_1": "SA",
                "object_2": "AB",
                "metadata": {"source": "given", "confidence": "verified"},
            },
            {
                "type": "perpendicular",
                "object_1": "AC",
                "object_2": "AB",
                "metadata": {"source": "given", "confidence": "verified"},
            },
        ],
    }

    result = solve(dihedral_scene, "Góc giữa (SAB) và (ABC)", geometry_method="classical")

    assert result.answer == "\\angle((SAB),(ABC)) = 90°"
    assert result.steps[1].title == "Dựng góc phẳng nhị diện"
    explanations = " ".join(step.explanation for step in result.steps).lower()
    assert "tọa độ" not in explanations
    assert "phép tính" not in explanations
    assert "cắt nhau theo ab" in explanations
    assert "sa vuông góc ab" in explanations
    assert "ac vuông góc ab" in explanations
    assert "góc sac" in explanations


def test_solve_area(scene):
    result = solve(scene, "S(BCED)")

    assert result.answer == "S(BCED) = 16"


def test_solve_pyramid_volume(scene):
    result = solve(scene, "V(S.BCED)")

    assert result.answer == "V(S.BCED) = 32"


def test_classical_pyramid_volume_uses_declared_height(scene):
    annotated_scene = {
        **scene,
        "problem_text": "Cho hình chóp S.BCED có SB vuông góc với đáy BCED và SB = 6.",
        "topic": "solid_geometry",
        "annotations": [{"type": "length", "target": "S-B", "label": "6", "metadata": {"source": "given", "confidence": "partial"}}],
        "relations": [{"type": "perpendicular", "object_1": "SB", "object_2": "plane(BCED)", "metadata": {"source": "given", "confidence": "verified"}}],
    }

    result = solve(annotated_scene, "V(S.BCED)", geometry_method="classical")

    assert result.answer == "V(S.BCED) = 32"
    assert result.steps[1].title == "Nhận ra đáy và chiều cao"
    explanations = " ".join(step.explanation for step in result.steps).lower()
    assert "tọa độ" not in explanations
    assert "bc ed" not in explanations
    assert "sb là chiều cao" in explanations
    assert "với đáy bced và chiều cao sb = 6" in explanations


def test_classical_pyramid_volume_rejects_missing_height_relation(scene):
    generic_scene = {
        **scene,
        "problem_text": "Cho hình chóp S.BCED có cạnh SB = 6.",
        "topic": "solid_geometry",
        "annotations": [{"type": "length", "target": "S-B", "label": "6", "metadata": {"source": "given", "confidence": "partial"}}],
    }

    result = solve(generic_scene, "V(S.BCED)", geometry_method="classical")

    assert result.answer == "Không đủ dữ kiện"
    assert result.confidence == "insufficient"
    assert any("chưa xác định được chiều cao" in warning.lower() for warning in result.warnings)


def test_solve_zero_distance_warns_about_scene_geometry(scene):
    result = solve(scene, "d(B,(BCD))")

    assert result.answer == "d(B,(BCD)) = 0"
    assert "đang nằm trên mặt phẳng" in result.warnings[0]


def test_solve_skew_line_distance():
    scene = {
        "objects": [
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 1},
            {"type": "point_3d", "name": "D", "x": 0, "y": 2, "z": 1},
        ]
    }

    result = solve(scene, "d(AB,CD)")

    assert result.answer == "d(AB,CD) = 1"
    assert result.steps[1].kind == "distance_line_line"


def test_perpendicular_check_rejects_skew_orthogonal_lines():
    scene = {
        "objects": [
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 1},
            {"type": "point_3d", "name": "D", "x": 0, "y": 2, "z": 1},
        ]
    }

    result = solve(scene, "AB vuông góc CD")

    assert result.answer == "AB vuông góc CD: SAI"
    assert "chéo nhau" in result.warnings[0]


def test_solve_line_equation(scene):
    result = solve(scene, "viết phương trình đường thẳng AC")

    assert result.answer.startswith("d_{AC}:")
    assert result.steps[1].kind == "equation_line"
    assert "x=0+4t" in result.steps[2].result_latex


def test_solve_plane_equation(scene):
    result = solve(scene, "pt mặt phẳng (BCD)")

    assert result.answer.startswith("(BCD):")
    assert result.steps[1].kind == "equation_plane"
    assert result.steps[2].result_latex.endswith("=0")


def test_solve_dot_product(scene):
    result = solve(scene, "BA . BC")

    assert result.answer == "\\overrightarrow{BA}\\cdot\\overrightarrow{BC} = 0"
    assert result.steps[1].kind == "vector_dot"


def test_solve_cross_product(scene):
    result = solve(scene, "BC × BD")

    assert result.answer.startswith("\\overrightarrow{BC}\\times\\overrightarrow{BD}")
    assert result.steps[1].kind == "vector_cross"
    assert result.steps[2].result_latex


def test_solve_projection_point_plane(scene):
    result = solve(scene, "hình chiếu của A lên (BCD)")

    assert result.answer == "H(0,0,0)"
    assert result.steps[1].kind == "projection_point_plane"


def test_solve_reflection_point_plane(scene):
    result = solve(scene, "đối xứng A qua (BCD)")

    assert result.answer == "A'(0,0,-3)"
    assert result.steps[1].kind == "reflection_point_plane"


def test_solve_collinear_false(scene):
    result = solve(scene, "A B C thẳng hàng?")

    assert result.answer == "ABC thẳng hàng: SAI"
    assert result.steps[1].kind == "proof_collinear"


def test_classical_collinear_template(scene):
    result = solve(scene, "A B C thẳng hàng?", geometry_method="classical")

    assert result.answer == "ABC thẳng hàng: SAI"
    assert result.steps[1].title == "Kiểm tra quan hệ thẳng hàng"


def test_solve_coplanar_true(scene):
    result = solve(scene, "B C D E đồng phẳng?")

    assert result.answer == "BCDE đồng phẳng: ĐÚNG"
    assert result.steps[1].kind == "proof_coplanar"


def test_classical_coplanar_template(scene):
    result = solve(scene, "B C D E đồng phẳng?", geometry_method="classical")

    assert result.answer == "BCDE đồng phẳng: ĐÚNG"
    assert result.steps[1].title == "Kiểm tra quan hệ đồng phẳng"


def test_solve_unsupported_returns_warning(scene):
    result = solve(scene, "tính gì đó")

    assert result.answer == "Không xác định"
    assert result.warnings


def test_ai_explainer_cannot_change_formula_or_result(monkeypatch):
    async def fake_call_explainer(*args, **kwargs):
        return {
            "steps": [
                {
                    "index": 1,
                    "title": "AI title",
                    "explanation": "AI explanation",
                    "formula_latex": "wrong",
                    "substitution_latex": "wrong",
                    "result_latex": "999",
                    "sub_steps": [
                        {
                            "index": 1,
                            "title": "AI sub",
                            "explanation": "AI sub explanation",
                            "formula_latex": "wrong-sub",
                            "result_latex": "888",
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr(solver_explainer, "_call_explainer", fake_call_explainer)
    result = SolverResult(
        "d(A,B)",
        "d(A,B) = 1",
        [
            SolverStep(
                1,
                "Gốc",
                "Giải thích gốc",
                None,
                None,
                ["A", "B"],
                formula_latex="AB",
                substitution_latex="1",
                result_latex="1",
            )
        ],
        [],
    )

    explained = __import__("asyncio").run(
        solver_explainer.explain_solver_result(result, {}, object(), method="oxyz")
    )

    assert explained.steps[0].title == "AI title"
    assert explained.steps[0].formula_latex == "AB"
    assert explained.steps[0].substitution_latex == "1"
    assert explained.steps[0].result_latex == "1"
    assert explained.steps[0].sub_steps == []
