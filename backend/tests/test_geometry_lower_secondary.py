from types import SimpleNamespace

from app.services.geometry_engine import calculate_polygon_area, calculate_polygon_perimeter
from app.services.math_capabilities import infer_geometry_task, resolve_geometry_capability
from app.services.math_solution_projectors import project_geometry_solution
from app.services.plane_shape_solver import solve_plane_shape_metric
from app.services.pythagoras_solver import solve_pythagoras
from app.services.solver_service import solve
from app.services.triangle_proof_solver import solve_triangle_proof


def _rectangle_scene(*, trusted: bool = True):
    scene = {
        "scene_id": "rectangle-thcs",
        "revision": 1,
        "topic": "plane_geometry",
        "objects": [
            {"type": "point_2d", "name": "A", "x": 0, "y": 0},
            {"type": "point_2d", "name": "B", "x": 3, "y": 0},
            {"type": "point_2d", "name": "C", "x": 3, "y": 4},
            {"type": "point_2d", "name": "D", "x": 0, "y": 4},
            {"type": "face", "points": ["A", "B", "C", "D"]},
        ],
    }
    if not trusted:
        scene["topic"] = "plane_geometry"
        scene["problem_text"] = "Cho tứ giác ABCD."
    return scene


def _right_triangle_scene(*, lengths: dict[str, str], with_right_angle: bool = True):
    scene = {
        "scene_id": "right-triangle-thcs",
        "revision": 1,
        "topic": "plane_geometry",
        "problem_text": "Cho tam giác ABC vuông tại B.",
        "objects": [
            {"type": "point_2d", "name": "A", "x": 0, "y": 0},
            {"type": "point_2d", "name": "B", "x": 3, "y": 0},
            {"type": "point_2d", "name": "C", "x": 3, "y": 4},
        ],
        "relations": [],
        "annotations": [
            {"id": f"length-{edge}", "type": "length", "target": edge, "label": value, "source": "given"}
            for edge, value in lengths.items()
        ],
    }
    if with_right_angle:
        scene["relations"].append({
            "id": "right-angle-B",
            "type": "perpendicular",
            "object_1": "AB",
            "object_2": "BC",
            "source": "given",
        })
    return scene


def test_pythagoras_engine_returns_exact_hypotenuse_and_substitution_evidence():
    result = solve_pythagoras(_right_triangle_scene(lengths={"AB": "3", "BC": "4"}), "Tính cạnh AC")

    assert result.status == "ok"
    assert result.result_latex == "5"
    assert result.problem is not None
    assert result.problem.target == ("A", "C")
    assert result.problem.evidence_ids == ("right-angle-B", "length-AB", "length-BC")
    assert result.verification_latex == "5^2=3^2+4^2"

    radical = solve_pythagoras(_right_triangle_scene(lengths={"AB": "1", "BC": "1"}), "Tính cạnh AC")
    assert radical.status == "ok"
    assert radical.result_latex == r"\sqrt{2}"


def test_pythagoras_facade_returns_verified_solution_ir_ready_steps():
    result = solve(
        _right_triangle_scene(lengths={"AB": "3", "BC": "4"}),
        "Tính cạnh AC",
        geometry_method="classical",
    )

    assert result.answer == "AC = 5"
    assert result.confidence == "verified"
    assert result.steps[1].kind == "pythagoras_length"
    assert result.steps[1].theorem_id == "triangle.pythagoras.length"
    assert result.steps[1].substitution_latex == r"AC=\sqrt{3^2+4^2}"
    assert result.steps[-1].result_latex == "5"
    assert result.used_theorems == [{"id": "triangle.pythagoras.length", "name": "Định lý Pythagore"}]

    solution_ir = project_geometry_solution(
        SimpleNamespace(
            question="Tính cạnh AC",
            scene_ref=SimpleNamespace(scene_id="right-triangle-thcs", revision=1),
        ),
        result,
        scene_topic="plane_geometry",
    )
    assert solution_ir.problem.curriculum.skill_ids == ["geometry.similarity_pythagoras"]
    assert solution_ir.status == "solved_verified"
    assert solution_ir.verification[0].method == "pythagoras_substitution"


def test_pythagoras_rejects_missing_premises_and_invalid_lengths():
    missing_angle = solve_pythagoras(
        _right_triangle_scene(lengths={"AB": "3", "BC": "4"}, with_right_angle=False),
        "Tính cạnh AC",
    )
    one_length = solve_pythagoras(_right_triangle_scene(lengths={"AB": "3"}), "Tính cạnh AC")
    non_positive = solve_pythagoras(_right_triangle_scene(lengths={"AB": "0", "BC": "4"}), "Tính cạnh AC")
    impossible = solve_pythagoras(_right_triangle_scene(lengths={"AC": "3", "BC": "4"}), "Tính cạnh AB")

    assert missing_angle.status == "insufficient"
    assert "Thiếu giả thiết góc vuông" in (missing_angle.warning or "")
    assert one_length.status == "insufficient"
    assert "đúng hai độ dài" in (one_length.warning or "")
    assert non_positive.status == "invalid"
    assert "exact dương" in (non_positive.warning or "")
    assert impossible.status == "invalid"
    assert "mâu thuẫn" in (impossible.warning or "")


def test_pythagoras_capability_is_limited_to_plane_geometry():
    task = infer_geometry_task("Tính cạnh AC bằng định lý Pythagore")
    plane = resolve_geometry_capability(
        question="Tính cạnh AC bằng định lý Pythagore",
        task=task,
        scene_id="right-triangle-thcs",
        revision=1,
        scene_topic="plane_geometry",
        method="classical",
    )
    solid = resolve_geometry_capability(
        question="Tính cạnh AC bằng định lý Pythagore",
        task=task,
        scene_id="solid-scene",
        revision=1,
        scene_topic="solid_geometry",
        method="classical",
    )

    assert task == "pythagoras"
    assert plane.accepted is True
    assert plane.skill_ids == ["geometry.similarity_pythagoras"]
    assert plane.verifier_methods == ["pythagoras_substitution"]
    assert solid.accepted is False
    assert solid.skill_ids == []


def _triangle_proof_scene(*, include_third_side: bool = True):
    relations = [
        {"id": "ab-de", "type": "equal_length", "object_1": "AB", "object_2": "DE", "source": "given"},
        {"id": "bc-ef", "type": "equal_length", "object_1": "BC", "object_2": "EF", "source": "given"},
    ]
    if include_third_side:
        relations.append({"id": "ac-df", "type": "equal_length", "object_1": "AC", "object_2": "DF", "source": "given"})
    return {
        "scene_id": "triangle-proof-thcs",
        "revision": 1,
        "topic": "plane_geometry",
        "problem_text": "Cho hai tam giác ABC và DEF.",
        "objects": [
            {"type": "point_2d", "name": name, "x": index, "y": index % 2}
            for index, name in enumerate("ABCDEF")
        ],
        "relations": relations,
        "annotations": [
            {"id": "angle-a", "type": "angle", "target": "A", "label": "50°", "metadata": {"arms": ["B", "C"], "source": "given"}},
            {"id": "angle-d", "type": "angle", "target": "D", "label": "50°", "metadata": {"arms": ["E", "F"], "source": "given"}},
            {"id": "angle-b", "type": "angle", "target": "B", "label": "60°", "metadata": {"arms": ["A", "C"], "source": "given"}},
            {"id": "angle-e", "type": "angle", "target": "E", "label": "60°", "metadata": {"arms": ["D", "F"], "source": "given"}},
        ],
    }


def test_triangle_congruence_sss_replays_exact_corresponding_premises():
    question = "Chứng minh tam giác ABC và tam giác DEF bằng nhau"
    proof = solve_triangle_proof(_triangle_proof_scene(), question)
    result = solve(_triangle_proof_scene(), question, geometry_method="classical")

    assert proof.status == "verified"
    assert proof.theorem_id == "triangle.congruence.sss"
    assert [fact.id for fact in proof.premise_facts] == ["ab-de", "bc-ef", "ac-df"]
    assert result.answer == "△ABC ≅ △DEF"
    assert result.confidence == "verified"
    assert result.steps[1].kind == "triangle_congruence_sss"

    solution_ir = project_geometry_solution(
        SimpleNamespace(question=question, scene_ref=SimpleNamespace(scene_id="triangle-proof-thcs", revision=1)),
        result,
        scene_topic="plane_geometry",
    )
    assert solution_ir.problem.curriculum.skill_ids == ["geometry.triangle_congruence"]
    assert solution_ir.status == "solved_verified"


def test_triangle_similarity_aa_uses_two_corresponding_angle_measures():
    question = "Chứng minh tam giác ABC đồng dạng tam giác DEF"
    proof = solve_triangle_proof(_triangle_proof_scene(), question)
    result = solve(_triangle_proof_scene(), question, geometry_method="classical")

    assert proof.status == "verified"
    assert proof.theorem_id == "triangle.similarity.aa"
    assert [fact.id for fact in proof.premise_facts] == ["angle-a", "angle-d", "angle-b", "angle-e"]
    assert result.answer == "△ABC ∼ △DEF"
    assert result.steps[1].kind == "triangle_similarity_aa"


def test_triangle_proof_reports_missing_or_wrong_corresponding_premise():
    question = "Chứng minh tam giác ABC và tam giác DEF bằng nhau"
    missing = solve_triangle_proof(_triangle_proof_scene(include_third_side=False), question)
    wrong_scene = _triangle_proof_scene(include_third_side=False)
    wrong_scene["relations"].append({
        "id": "ac-ef",
        "type": "equal_length",
        "object_1": "AC",
        "object_2": "EF",
        "source": "given",
    })
    wrong = solve_triangle_proof(wrong_scene, question)
    facade = solve(_triangle_proof_scene(include_third_side=False), question)

    assert missing.status == "missing_premise"
    assert missing.missing_premises == ("AC = DF",)
    assert wrong.status == "missing_premise"
    assert facade.answer == "Không đủ dữ kiện"
    assert facade.confidence == "insufficient"
    assert any("Thiếu premise SSS" in warning for warning in facade.warnings)


def test_triangle_proof_capabilities_are_skill_specific_and_plane_only():
    congruence = resolve_geometry_capability(
        question="Chứng minh tam giác ABC và tam giác DEF bằng nhau",
        task="triangle_congruence",
        scene_id="triangle-proof-thcs",
        revision=1,
        scene_topic="plane_geometry",
        method="classical",
    )
    similarity = resolve_geometry_capability(
        question="Chứng minh tam giác ABC đồng dạng tam giác DEF",
        task="triangle_similarity",
        scene_id="triangle-proof-thcs",
        revision=1,
        scene_topic="plane_geometry",
        method="classical",
    )
    solid = resolve_geometry_capability(
        question="Chứng minh tam giác ABC và tam giác DEF bằng nhau",
        task="triangle_congruence",
        scene_id="solid-scene",
        revision=1,
        scene_topic="solid_geometry",
        method="classical",
    )

    assert congruence.skill_ids == ["geometry.triangle_congruence"]
    assert congruence.verifier_methods == ["triangle_congruence_replay"]
    assert similarity.skill_ids == ["geometry.similarity_pythagoras"]
    assert "triangle_similarity_replay" in similarity.verifier_methods
    assert solid.accepted is False


def _metric_fact_scene(**measures: str):
    return {
        "scene_id": "plane-metric-thcs",
        "revision": 1,
        "topic": "plane_geometry",
        "problem_text": "Các kích thước được cho trực tiếp trong đề.",
        "objects": [],
        "relations": [],
        "annotations": [
            {"id": f"measure-{name}", "type": "measure", "target": name, "label": value, "metadata": {"source": "given"}}
            for name, value in measures.items()
        ],
    }


def test_quadrilateral_metrics_use_exact_scalar_facts():
    rectangle = _metric_fact_scene(length="8", width="5")
    square = _metric_fact_scene(side="6")
    parallelogram = _metric_fact_scene(base="7", height="4")
    trapezoid = _metric_fact_scene(base1="5", base2="9", height="3")

    assert solve(rectangle, "Tính diện tích hình chữ nhật").answer == "S = 40"
    assert solve(rectangle, "Tính chu vi hình chữ nhật").answer == "P = 26"
    assert solve(square, "Tính diện tích hình vuông").answer == "S = 36"
    assert solve(square, "Tính chu vi hình vuông").answer == "P = 24"
    assert solve(parallelogram, "Tính diện tích hình bình hành").answer == "S = 28"
    assert solve(trapezoid, "Tính diện tích hình thang").answer == "S = 21"


def test_circle_metrics_return_exact_pi_and_task_specific_solution_ir():
    scene = _metric_fact_scene(radius="3")
    area = solve(scene, "Tính diện tích hình tròn", geometry_method="classical")
    circumference = solve(scene, "Tính chu vi đường tròn", geometry_method="classical")

    assert area.answer == r"S = 9 \pi"
    assert circumference.answer == r"C = 6 \pi"
    assert area.steps[1].kind == "circle_metric"
    assert area.confidence == "verified"

    solution_ir = project_geometry_solution(
        SimpleNamespace(question="Tính diện tích hình tròn", scene_ref=SimpleNamespace(scene_id="plane-metric-thcs", revision=1)),
        area,
        scene_topic="plane_geometry",
    )
    assert solution_ir.problem.curriculum.skill_ids == ["geometry.circle_basic"]
    assert solution_ir.verification[0].method == "circle_metric_recompute"


def test_plane_shape_metric_rejects_missing_invalid_and_conflicting_dimensions():
    missing = solve_plane_shape_metric(_metric_fact_scene(length="8"), "Tính diện tích hình chữ nhật")
    invalid = solve_plane_shape_metric(_metric_fact_scene(radius="-3"), "Tính chu vi đường tròn")
    conflicting_scene = _metric_fact_scene(length="8", width="5")
    conflicting_scene["annotations"].append({
        "id": "measure-width-conflict",
        "type": "measure",
        "target": "width",
        "label": "6",
        "metadata": {"source": "given"},
    })
    conflicting = solve_plane_shape_metric(conflicting_scene, "Tính diện tích hình chữ nhật")

    assert missing.status == "missing_premise"
    assert missing.missing_premises == ("width",)
    assert invalid.status == "invalid"
    assert "exact dương" in (invalid.warning or "")
    assert conflicting.status == "invalid"
    assert "mâu thuẫn" in (conflicting.warning or "")


def test_plane_shape_capabilities_are_skill_specific():
    quadrilateral_task = infer_geometry_task("Tính diện tích hình chữ nhật")
    circle_task = infer_geometry_task("Tính chu vi đường tròn")
    quadrilateral = resolve_geometry_capability(
        question="Tính diện tích hình chữ nhật",
        task=quadrilateral_task,
        scene_id="plane-metric-thcs",
        revision=1,
        scene_topic="plane_geometry",
        method="classical",
    )
    circle = resolve_geometry_capability(
        question="Tính chu vi đường tròn",
        task=circle_task,
        scene_id="plane-metric-thcs",
        revision=1,
        scene_topic="plane_geometry",
        method="classical",
    )

    assert quadrilateral_task == "quadrilateral_metric"
    assert quadrilateral.skill_ids == ["geometry.quadrilateral"]
    assert quadrilateral.verifier_methods == ["plane_metric_recompute"]
    assert circle_task == "circle_metric"
    assert circle.skill_ids == ["geometry.circle_basic"]
    assert circle.verifier_methods == ["circle_metric_recompute"]


def test_polygon_perimeter_is_computed_and_verified_through_facade():
    result = solve(_rectangle_scene(), "Tính chu vi ABCD")

    assert result.answer == "P(ABCD) = 14"
    assert result.confidence == "verified"
    assert result.steps[-1].result_latex == "14"
    assert result.steps[1].kind == "perimeter_polygon"


def test_polygon_area_is_computed_and_verified_through_facade():
    result = solve(_rectangle_scene(), "Tính diện tích ABCD")

    assert result.answer == "S(ABCD) = 12"
    assert result.confidence == "verified"
    assert result.steps[-1].result_latex == "12"
    assert result.steps[1].kind == "area_polygon"


def test_polygon_area_rejects_degenerate_and_non_coplanar_vertices():
    degenerate = calculate_polygon_area(
        {"A": (0.0, 0.0, 0.0), "B": (1.0, 0.0, 0.0), "C": (2.0, 0.0, 0.0)},
        ["A", "B", "C"],
    )
    non_coplanar = calculate_polygon_area(
        {
            "A": (0.0, 0.0, 0.0),
            "B": (1.0, 0.0, 0.0),
            "C": (1.0, 1.0, 0.0),
            "D": (0.0, 1.0, 1.0),
        },
        ["A", "B", "C", "D"],
    )

    assert degenerate["status"] == "degenerate"
    assert "suy biến" in degenerate["warnings"][0]
    assert non_coplanar["status"] == "degenerate"
    assert "không đồng phẳng" in non_coplanar["warnings"][0]


def test_polygon_perimeter_calculator_rejects_degenerate_edge():
    points = {"A": (0.0, 0.0, 0.0), "B": (0.0, 0.0, 0.0), "C": (1.0, 0.0, 0.0)}

    result = calculate_polygon_perimeter(points, ["A", "B", "C"])

    assert result["status"] == "degenerate"
    assert "suy biến" in result["warnings"][0]


def test_plane_measurements_do_not_trust_illustrative_coordinates():
    perimeter = solve(_rectangle_scene(trusted=False), "P(ABCD)")
    area = solve(_rectangle_scene(trusted=False), "S(ABCD)")

    assert perimeter.answer == "Không đủ dữ kiện"
    assert perimeter.confidence == "insufficient"
    assert any("không dùng tọa độ minh họa" in warning for warning in perimeter.warnings)
    assert area.answer == "Không đủ dữ kiện"
    assert area.confidence == "insufficient"
    assert any("không dùng tọa độ minh họa" in warning for warning in area.warnings)


def test_perimeter_capability_resolves_to_lower_secondary_measurement():
    task = infer_geometry_task("P(ABCD)")
    snapshot = resolve_geometry_capability(
        question="P(ABCD)",
        task=task,
        scene_id="rectangle-thcs",
        revision=1,
        scene_topic="plane_geometry",
        method="oxyz",
    )

    assert task == "perimeter"
    assert snapshot.accepted is True
    assert snapshot.skill_ids == ["geometry.basic_measurement"]


def test_area_capability_stays_inside_scene_curriculum_boundary():
    def resolve(scene_topic: str):
        return resolve_geometry_capability(
            question="S(ABC)",
            task="area",
            scene_id=f"{scene_topic}-scene",
            revision=1,
            scene_topic=scene_topic,
            method="oxyz",
        )

    assert resolve("plane_geometry").skill_ids == ["geometry.basic_measurement"]
    assert resolve("coordinate_2d").skill_ids == ["geometry.coordinate_2d"]
    assert resolve("solid_geometry").skill_ids == ["geometry.solid_metric"]
    assert resolve("coordinate_3d").skill_ids == ["geometry.coordinate_3d"]
