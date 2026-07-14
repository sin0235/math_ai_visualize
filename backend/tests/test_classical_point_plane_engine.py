from app.services.solver_service import solve


def _point(name: str, *, x: float | None = None, y: float | None = None, z: float | None = None) -> dict:
    point = {"id": f"point-{name.lower()}", "type": "point_3d", "name": name, "label": name}
    if x is not None and y is not None and z is not None:
        point.update({"x": x, "y": y, "z": z})
    return point


def _renamed_cube_scene(side: int = 4, *, with_midpoint: bool = True, misleading_render: bool = False) -> dict:
    objects = [_point(name) for name in "ABCDEFGHK"]
    if misleading_render:
        objects = [
            _point(name, x=index * 7, y=index % 3, z=13 - index)
            for index, name in enumerate("ABCDEFGHK")
        ]
    relations = []
    if with_midpoint:
        relations.append({
            "id": "midpoint-k-cd",
            "type": "midpoint",
            "object_1": "K",
            "object_2": "C-D",
            "metadata": {"source": "given", "confidence": "verified"},
            "verification": {"status": "verified"},
        })
    return {
        "scene_id": "renamed-orthogonal-solid",
        "revision": 1,
        "topic": "solid_geometry",
        "problem_text": (
            f"Cho hình lập phương (ABCD.EFGH) có cạnh bằng ({side})."
            + (" K là trung điểm của CD." if with_midpoint else "")
        ),
        "objects": objects,
        "relations": relations,
        "annotations": [],
    }


def test_classical_point_plane_engine_solves_renamed_cube_without_render_coordinates():
    result = solve(_renamed_cube_scene(), "d(E,(GKB))", geometry_method="classical")

    assert result.answer == r"d(E,(GKB)) = 2 \sqrt{6}"
    assert result.confidence == "verified"
    assert result.method == "classical"
    assert result.proof_plan is not None
    assert all("tọa độ" not in step.explanation.lower() for step in result.steps)
    assert any(step.theorem_id == "perpendicular.line_plane.two_intersecting_lines" for step in result.steps)
    assert any(action["type"] == "project_point" for step in result.steps for action in step.construction_actions)


def test_classical_point_plane_engine_solves_original_abcd_mnpq_problem():
    scene = {
        "scene_id": "cube-abcd-mnpq",
        "revision": 1,
        "topic": "solid_geometry",
        "problem_text": (
            "Cho hình lập phương (ABCD.MNPQ) có cạnh bằng (4), trong đó M, N, P, Q "
            "lần lượt nằm trên các đường thẳng vuông góc với mặt phẳng (ABCD) tại A, B, C, D. "
            "Gọi F là trung điểm của đoạn thẳng CD."
        ),
        "objects": [_point(name) for name in "ABCDFMNPQ"],
        "relations": [],
        "annotations": [],
    }

    result = solve(scene, "d(M,(PFB))", geometry_method="classical")

    assert result.answer == r"d(M,(PFB)) = 2 \sqrt{6}"
    assert result.confidence == "verified"
    assert result.proof_plan is not None


def test_classical_point_plane_engine_scales_exact_result_from_given_edge():
    result = solve(_renamed_cube_scene(18), "d(E,(GKB))", geometry_method="classical")

    assert result.answer == r"d(E,(GKB)) = 9 \sqrt{6}"
    assert result.steps[-1].result_latex == r"9 \sqrt{6}"


def test_classical_point_plane_engine_ignores_misleading_render_coordinates():
    result = solve(
        _renamed_cube_scene(4, misleading_render=True),
        "d(E,(GKB))",
        geometry_method="classical",
    )

    assert result.answer == r"d(E,(GKB)) = 2 \sqrt{6}"
    assert result.proof_plan is not None


def test_classical_point_plane_engine_requires_midpoint_premise():
    result = solve(
        _renamed_cube_scene(with_midpoint=False),
        "d(E,(GKB))",
        geometry_method="classical",
    )

    assert result.answer == "Không đủ dữ kiện"
    assert result.confidence == "insufficient"
    assert any("midpoint" in warning.lower() or "trung điểm" in warning.lower() for warning in result.warnings)


def test_classical_point_plane_engine_reports_missing_frame_lengths_without_reading_render_data():
    scene = _renamed_cube_scene()
    scene["problem_text"] = "Cho hình lập phương (ABCD.EFGH). K là trung điểm của CD."

    result = solve(scene, "d(E,(GKB))", geometry_method="classical")

    assert result.answer == "Không đủ dữ kiện"
    assert result.confidence == "insufficient"
    assert any("độ dài ba phương" in warning for warning in result.warnings)


def test_classical_point_plane_engine_consumes_generic_verified_orthogonal_frame_fact():
    scene = {
        "scene_id": "generic-orthogonal-frame",
        "revision": 1,
        "topic": "solid_geometry",
        "problem_text": "Khối hộp có ba phương cạnh đôi một vuông góc.",
        "objects": [_point(name) for name in "ABCDEFGHK"],
        "relations": [{
            "id": "midpoint-k-cd",
            "type": "midpoint",
            "object_1": "K",
            "object_2": "C-D",
            "metadata": {"source": "given", "confidence": "verified"},
        }],
        "derived_facts": [{
            "id": "frame-abcdef-gh",
            "kind": "orthogonal_frame",
            "provenance": "verified",
            "source_ids": ["solid-given"],
            "value": {
                "base": ["A", "B", "C", "D"],
                "top": ["E", "F", "G", "H"],
                "axis_lengths": ["2", "3", "4"],
                "text": "Ba phương cạnh của khối hộp đôi một vuông góc.",
            },
        }],
        "annotations": [],
    }

    result = solve(scene, "d(E,(GKB))", geometry_method="classical")

    assert result.answer == r"d(E,(GKB)) = \frac{36}{13}"
    assert result.proof_plan is not None


def test_classical_point_plane_engine_normalizes_rectangular_cuboid_to_same_frame_contract():
    scene = {
        "scene_id": "rectangular-cuboid",
        "revision": 1,
        "topic": "solid_geometry",
        "problem_text": (
            "Cho hình hộp chữ nhật (ABCD.EFGH), AB = 2, AD = 3, AE = 4. "
            "K là trung điểm của CD."
        ),
        "objects": [_point(name) for name in "ABCDEFGHK"],
        "relations": [],
        "annotations": [],
    }

    result = solve(scene, "d(E,(GKB))", geometry_method="classical")

    assert result.answer == r"d(E,(GKB)) = \frac{36}{13}"
    assert result.confidence == "verified"
    assert result.proof_plan is not None


def test_classical_point_plane_engine_keeps_direct_height_as_low_cost_path():
    scene = {
        "scene_id": "direct-height",
        "revision": 1,
        "topic": "solid_geometry",
        "problem_text": "SA vuông góc (ABC), SA = 3.",
        "objects": [_point(name) for name in "SABC"],
        "relations": [{
            "id": "sa-perp-abc",
            "type": "perpendicular",
            "object_1": "SA",
            "object_2": "plane(ABC)",
            "metadata": {"source": "given", "confidence": "verified"},
        }],
        "annotations": [{
            "id": "length-sa",
            "type": "length",
            "target": "S-A",
            "label": "3",
            "metadata": {"source": "given", "confidence": "verified"},
        }],
    }

    result = solve(scene, "d(S,(ABC))", geometry_method="classical")

    assert result.answer == "d(S,(ABC)) = 3"
    assert result.proof_plan is not None
    assert len(result.steps) <= 3
