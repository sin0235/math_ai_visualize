import pytest

from app.schemas.scene_v3 import MathSceneV3
from app.services.downstream_scene_v3 import scene_v3_to_solver_input
from app.services.geometry.metric_precision import approximate_latex, parse_metric_precision
from app.services.solver_explainer import _payload
from app.services.solver_service import solve


FULL_PROBLEM = (
    "Cho hình lập phương (ABCD.MNPQ) có cạnh bằng (8), trong đó (M, N, P, Q) "
    "lần lượt nằm trên các đường thẳng vuông góc với mặt phẳng ((ABCD)) tại (A, B, C, D). "
    "Gọi (F) là trung điểm của đoạn thẳng (CD). "
    "Khoảng cách từ điểm (M) đến mặt phẳng ((PFB)) bằng bao nhiêu? "
    "Không làm tròn kết quả trong các phép tính trung gian, chỉ làm tròn kết quả cuối cùng đến hàng phần mười."
)


def _scene(problem_text: str = FULL_PROBLEM, *, misleading_render: bool = False) -> dict:
    edge = 8.0
    coordinates = {
        "A": (0, 0, 0),
        "B": (edge, 0, 0),
        "C": (edge, edge, 0),
        "D": (0, edge, 0),
        "M": (0, 0, edge),
        "N": (edge, 0, edge),
        "P": (edge, edge, edge),
        "Q": (0, edge, edge),
        "F": (edge / 2, edge, 0),
    }
    if misleading_render:
        coordinates = {
            name: (index * 7 + 1, index % 3 + 2, 19 - index * 2)
            for index, name in enumerate(coordinates)
        }
    scene = MathSceneV3.model_validate({
        "scene_id": "cube-coordinate-regression",
        "revision": 1,
        "problem_text": problem_text,
        "topic": "solid_geometry",
        "renderer": "threejs_3d",
        "objects": [
            {
                "id": f"point-{name.lower()}",
                "type": "point_3d",
                "label": name,
                "x": xyz[0],
                "y": xyz[1],
                "z": xyz[2],
            }
            for name, xyz in coordinates.items()
        ],
        "view": {"dimension": "3d"},
        "audit": {"created_by": "test"},
    })
    return scene_v3_to_solver_input(scene)


def _named_solid_scene(problem_text: str, labels: str) -> dict:
    return {
        "scene_id": "named-solid-coordinate",
        "revision": 1,
        "problem_text": problem_text,
        "topic": "solid_geometry",
        "objects": [
            {
                "object_id": f"point-{name.lower()}",
                "type": "point_3d",
                "name": name,
                "x": index * 5 + 1,
                "y": index % 2,
                "z": 20 - index,
            }
            for index, name in enumerate(labels)
        ],
        "relations": [],
        "annotations": [],
    }


def test_oxyz_solves_full_cube_problem_from_trusted_problem_facts():
    result = solve(
        _scene(misleading_render=True),
        "Khoảng cách từ điểm (M) đến mặt phẳng ((PFB)) bằng bao nhiêu?",
        geometry_method="oxyz",
    )

    assert result.answer == r"d(M,(PFB)) = 4 \sqrt{6} \approx 9{,}8"
    assert result.confidence == "verified"
    assert result.method == "oxyz"
    assert result.warnings == []
    assert [step.kind for step in result.steps] == [
        "coordinate_frame_setup",
        "coordinate_derivation",
        "distance_point_plane_setup",
        "distance_point_plane",
        "result",
    ]
    assert result.steps[3].result_latex == r"4 \sqrt{6}"
    assert result.steps[-1].result_latex == r"4 \sqrt{6} \approx 9{,}8"
    assert "F=\\frac{C+D}{2}" in (result.steps[1].formula_latex or "")
    assert any(fact["source"] == "given" and "hình lập phương" in fact["text"] for fact in result.used_facts)
    assert any(fact["source"] == "given" and "trung điểm" in fact["text"] for fact in result.used_facts)


def test_oxyz_keeps_exact_only_when_problem_has_no_rounding_request():
    problem = (
        "Cho hình lập phương (ABCD.MNPQ) có cạnh bằng (18). "
        "Gọi F là trung điểm của CD."
    )

    result = solve(_scene(problem), "d(M,(PFB))", geometry_method="oxyz")

    assert result.answer == r"d(M,(PFB)) = 9 \sqrt{6}"
    assert result.steps[-1].result_latex == r"9 \sqrt{6}"


def test_oxyz_reads_rounding_request_from_current_question():
    problem = (
        "Cho hình lập phương (ABCD.MNPQ) có cạnh bằng (8). "
        "Gọi F là trung điểm của CD."
    )

    result = solve(
        _scene(problem),
        "Khoảng cách từ M đến mặt phẳng (PFB) bằng bao nhiêu? Làm tròn đến hàng phần trăm.",
        geometry_method="oxyz",
    )

    assert result.answer == r"d(M,(PFB)) = 4 \sqrt{6} \approx 9{,}80"


def test_oxyz_supports_renamed_cube_without_render_coordinates():
    scene = _named_solid_scene(
        "Cho hình lập phương (ABCD.EFGH) có cạnh bằng 4. K là trung điểm của CD.",
        "ABCDEFGHK",
    )

    result = solve(scene, "d(E,(GKB))", geometry_method="oxyz")

    assert result.answer == r"d(E,(GKB)) = 2 \sqrt{6}"
    assert result.confidence == "verified"


@pytest.mark.parametrize("edge_phrase", ["cạnh là 4", "cạnh dài 4", "cạnh có độ dài bằng 4"])
def test_oxyz_accepts_common_numeric_cube_edge_phrases(edge_phrase: str):
    scene = _named_solid_scene(
        f"Cho hình lập phương (ABCD.EFGH) {edge_phrase}. K là trung điểm của CD.",
        "ABCDEFGHK",
    )

    result = solve(scene, "d(E,(GKB))", geometry_method="oxyz")

    assert result.answer == r"d(E,(GKB)) = 2 \sqrt{6}"


def test_oxyz_supports_rectangular_cuboid_frame():
    scene = _named_solid_scene(
        "Cho hình hộp chữ nhật (ABCD.EFGH), AB = 2, AD = 3, AE = 4. K là trung điểm của CD.",
        "ABCDEFGHK",
    )

    result = solve(scene, "d(E,(GKB))", geometry_method="oxyz")

    assert result.answer == r"d(E,(GKB)) = \frac{36}{13}"
    assert result.confidence == "verified"


def test_oxyz_reports_missing_cube_edge_instead_of_using_render_scale():
    problem = "Cho hình lập phương (ABCD.MNPQ). Gọi F là trung điểm của CD."

    result = solve(_scene(problem), "d(M,(PFB))", geometry_method="oxyz")

    assert result.answer == "Không đủ dữ kiện"
    assert result.confidence == "insufficient"
    assert any("độ dài ba phương" in warning for warning in result.warnings)


def test_oxyz_rejects_non_positive_cube_edge():
    problem = "Cho hình lập phương (ABCD.MNPQ) có cạnh bằng 0. Gọi F là trung điểm của CD."

    result = solve(_scene(problem), "d(M,(PFB))", geometry_method="oxyz")

    assert result.answer == "Không đủ dữ kiện"
    assert result.confidence == "insufficient"


def test_oxyz_reports_missing_midpoint_premise():
    problem = "Cho hình lập phương (ABCD.MNPQ) có cạnh bằng 8."

    result = solve(_scene(problem), "d(M,(PFB))", geometry_method="oxyz")

    assert result.answer == "Không đủ dữ kiện"
    assert result.confidence == "insufficient"
    assert any("F" in warning and "midpoint" in warning for warning in result.warnings)


def test_verified_metric_evidence_remains_available_when_frame_length_is_missing():
    scene = _scene("Cho hình lập phương (ABCD.MNPQ). Gọi F là trung điểm của CD.")
    scene["annotations"] = [{
        "id": "given-ab",
        "type": "length",
        "target": "A-B",
        "target_ids": ["point-a", "point-b"],
        "label": "8",
        "metadata": {"source": "given", "confidence": "verified"},
    }]

    result = solve(scene, "d(M,(PFB))", geometry_method="oxyz")

    assert result.answer == r"d(M,(PFB)) = 4 \sqrt{6}"
    assert result.confidence == "verified"


def test_explainer_payload_does_not_expose_misleading_render_coordinates():
    scene = _scene(misleading_render=True)
    result = solve(scene, "d(M,(PFB))", geometry_method="oxyz")

    payload = _payload(result, scene, method="oxyz")

    assert payload["coordinate_source"] == "trusted_problem_facts"
    assert payload["point_coordinates"] == {}
    assert all(not {"x", "y", "z"}.intersection(obj) for obj in payload["scene_objects"])


@pytest.mark.parametrize(
    ("text", "places"),
    [
        ("làm tròn đến hàng phần mười", 1),
        ("làm tròn đến hàng phần trăm", 2),
        ("làm tròn đến hàng phần nghìn", 3),
        ("làm tròn đến 4 chữ số thập phân", 4),
    ],
)
def test_parse_metric_precision_vietnamese(text: str, places: int):
    precision = parse_metric_precision(text)

    assert precision is not None
    assert precision.decimal_places == places


def test_approximation_rounds_directly_from_exact_expression():
    import sympy as sp

    precision = parse_metric_precision("hàng phần mười")

    assert precision is not None
    assert approximate_latex(4 * sp.sqrt(6), precision) == "9{,}8"
