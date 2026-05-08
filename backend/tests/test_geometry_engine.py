import pytest

from app.schemas.scene import AdvancedRenderSettings, Line3D, MathScene, Plane, Point3D, Relation, SceneView, Segment, Sphere
from app.services.geometry_engine import (
    calculate_line_equation,
    calculate_line_line_angle,
    calculate_line_plane_angle,
    calculate_plane_equation,
    calculate_plane_plane_angle,
    calculate_point_line_distance,
    calculate_point_line_projection,
    calculate_point_plane_distance,
    calculate_point_plane_projection,
    calculate_point_plane_reflection,
    calculate_point_point_distance,
    calculate_polygon_area,
    calculate_pyramid_volume,
    calculate_tetrahedron_volume,
    calculate_vector_cross,
    calculate_vector_dot,
    compute_three_geometry,
    normalize_scene,
    prove_collinear,
    prove_coplanar,
)


def scene_with(objects):
    return MathScene(
        problem_text="test",
        renderer="threejs_3d",
        objects=objects,
        view=SceneView(dimension="3d"),
    )


def point(name, x, y, z):
    return Point3D(name=name, x=x, y=y, z=z)


def first_intersection(objects):
    computed = compute_three_geometry(scene_with(objects))
    assert computed["intersections"]
    return computed["intersections"][0]


def assert_point_close(actual, expected):
    assert actual["x"] == pytest.approx(expected[0])
    assert actual["y"] == pytest.approx(expected[1])
    assert actual["z"] == pytest.approx(expected[2])


def calc_points():
    return {
        "A": (0.0, 0.0, 3.0),
        "B": (0.0, 0.0, 0.0),
        "C": (4.0, 0.0, 0.0),
        "D": (0.0, 4.0, 0.0),
        "E": (4.0, 4.0, 0.0),
        "S": (0.0, 0.0, 6.0),
    }


def annotation_targets(scene, annotation_type):
    return [annotation.target for annotation in scene.annotations if annotation.type == annotation_type]


def test_calculate_point_point_distance():
    result = calculate_point_point_distance(calc_points(), "B", "C")

    assert result["status"] == "ok"
    assert result["result_value"] == pytest.approx(4)
    assert result["formula_latex"]


def test_calculate_point_line_distance():
    result = calculate_point_line_distance(calc_points(), "A", ("B", "C"))

    assert result["status"] == "ok"
    assert result["result_value"] == pytest.approx(3)
    assert_point_close(result["foot"], (0, 0, 0))


def test_calculate_point_plane_distance():
    result = calculate_point_plane_distance(calc_points(), "A", ["B", "C", "D"])

    assert result["status"] == "ok"
    assert result["result_value"] == pytest.approx(3)
    assert_point_close(result["foot"], (0, 0, 0))


def test_calculate_angles():
    points = calc_points()

    assert calculate_line_line_angle(points, ("B", "C"), ("B", "D"))["result_value"] == pytest.approx(90)
    assert calculate_line_plane_angle(points, ("B", "A"), ["B", "C", "D"])["result_value"] == pytest.approx(90)
    assert calculate_plane_plane_angle(points, ["B", "C", "D"], ["A", "C", "D"])["status"] == "ok"


def test_calculate_area_and_volume():
    points = calc_points()

    assert calculate_polygon_area(points, ["B", "C", "E", "D"])["result_value"] == pytest.approx(16)
    tetra = calculate_tetrahedron_volume(points, ["B", "C", "D", "A"])
    assert tetra["result_value"] == pytest.approx(8)
    assert tetra["result_latex"] == "8"
    assert calculate_pyramid_volume(points, "S", ["B", "C", "E", "D"])["result_value"] == pytest.approx(32)


def test_triangle_area_exact_radical():
    points = {"A": (0.0, 0.0, 0.0), "B": (1.0, 0.0, 0.0), "C": (0.0, 1.0, 1.0)}

    result = calculate_polygon_area(points, ["A", "B", "C"])

    assert result["result_value"] == pytest.approx(2 ** 0.5 / 2)
    assert result["result_latex"] == "\\frac{\\sqrt{2}}{2}"


def test_calculate_degenerate_line_warning():
    points = {"A": (0.0, 0.0, 0.0), "B": (0.0, 0.0, 0.0), "C": (1.0, 0.0, 0.0)}

    result = calculate_point_line_distance(points, "C", ("A", "B"))

    assert result["status"] == "degenerate"
    assert result["warnings"]


def test_calculate_vector_dot_and_cross():
    points = {"A": (0.0, 0.0, 0.0), "B": (1.0, 2.0, 3.0), "C": (0.0, 0.0, 0.0), "D": (4.0, 5.0, 6.0), "E": (0.0, 1.0, 0.0)}

    dot = calculate_vector_dot(points, ("A", "B"), ("C", "D"))
    cross = calculate_vector_cross(points, ("A", "B"), ("A", "E"))

    assert dot["status"] == "ok"
    assert dot["result_value"] == pytest.approx(32)
    assert cross["status"] == "ok"
    assert cross["result_vector"] == {"x": pytest.approx(-3), "y": pytest.approx(0), "z": pytest.approx(1)}


def test_calculate_line_and_plane_equations():
    points = calc_points()

    line = calculate_line_equation(points, ("A", "C"))
    plane = calculate_plane_equation(points, ["B", "C", "D"])

    assert line["status"] == "ok"
    assert line["kind"] == "equation_line"
    assert "x=0+4t" in line["result_latex"]
    assert plane["status"] == "ok"
    assert plane["coefficients"]["c"] == pytest.approx(16)
    assert plane["coefficients"]["d"] == pytest.approx(0)


def test_calculate_projection_and_reflection_point_plane():
    points = calc_points()

    projection = calculate_point_plane_projection(points, "A", ["B", "C", "D"])
    reflection = calculate_point_plane_reflection(points, "A", ["B", "C", "D"])
    line_projection = calculate_point_line_projection(points, "A", ("B", "C"))

    assert projection["status"] == "ok"
    assert_point_close(projection["point"], (0, 0, 0))
    assert reflection["status"] == "ok"
    assert_point_close(reflection["point"], (0, 0, -3))
    assert line_projection["status"] == "ok"
    assert_point_close(line_projection["point"], (0, 0, 0))


def test_prove_collinear_and_coplanar():
    points = {"A": (0.0, 0.0, 0.0), "B": (1.0, 1.0, 1.0), "C": (2.0, 2.0, 2.0), "D": (0.0, 0.0, 1.0), "E": (1.0, 0.0, 0.0), "F": (0.0, 1.0, 0.0)}

    assert prove_collinear(points, ["A", "B", "C"])["answer"].endswith("ĐÚNG")
    assert prove_collinear(points, ["A", "B", "D"])["answer"].endswith("SAI")
    assert prove_coplanar(points, ["A", "E", "F", "C"])["answer"].endswith("SAI")
    assert prove_coplanar(points, ["A", "E", "F"])["answer"].endswith("ĐÚNG")


def test_midpoint_relation_adds_equal_marks():
    scene = scene_with([
        point("A", 0, 0, 0),
        point("M", 1, 0, 0),
        point("B", 2, 0, 0),
    ])
    scene.relations.append(Relation(type="midpoint", object_1="M", object_2="A-B"))

    normalized = normalize_scene(scene)

    assert set(annotation_targets(normalized, "equal_marks")) >= {"A-M", "M-B"}


def test_equal_length_relation_adds_equal_marks():
    scene = scene_with([
        point("A", 0, 0, 0),
        point("B", 1, 0, 0),
        point("C", 1, 1, 0),
    ])
    scene.relations.append(Relation(type="equal_length", object_1="AB", object_2="B-C"))

    normalized = normalize_scene(scene)

    assert set(annotation_targets(normalized, "equal_marks")) >= {"A-B", "B-C"}


def test_perpendicular_relation_adds_right_angle():
    scene = scene_with([
        point("A", 0, 0, 0),
        point("B", 1, 0, 0),
        point("C", 0, 1, 0),
    ])
    scene.relations.append(Relation(type="perpendicular", object_1="AB", object_2="AC"))

    normalized = normalize_scene(scene)

    right_angles = [annotation for annotation in normalized.annotations if annotation.type == "right_angle"]
    assert len(right_angles) == 1
    assert right_angles[0].target == "A"
    assert set(right_angles[0].metadata["arms"]) == {"B", "C"}


def test_segment_intersections_use_spatial_prefilter_for_many_segments():
    objects = [point("A", 0, 0, 0), point("B", 2, 2, 0), point("C", 0, 2, 0), point("D", 2, 0, 0)]
    objects.extend([Segment(points=["A", "B"]), Segment(points=["C", "D"])])
    for index in range(30):
        p = f"P{index}"
        q = f"Q{index}"
        y = 10 + index
        objects.extend([point(p, 0, y, 0), point(q, 1, y, 0), Segment(points=[p, q])])

    normalized = normalize_scene(scene_with(objects))

    intersection = next(obj for obj in normalized.objects if isinstance(obj, Point3D) and obj.name == "I")
    assert intersection.x == pytest.approx(1)
    assert intersection.y == pytest.approx(1)


def test_normalize_scene_adds_segment_intersection_point():
    scene = scene_with([
        point("A", 0, 0, 0),
        point("B", 2, 2, 0),
        point("C", 0, 2, 0),
        point("D", 2, 0, 0),
        Segment(points=["A", "B"]),
        Segment(points=["C", "D"]),
    ])

    normalized = normalize_scene(scene)

    intersection = next(obj for obj in normalized.objects if isinstance(obj, Point3D) and obj.name == "I")
    assert intersection.x == pytest.approx(1)
    assert intersection.y == pytest.approx(1)
    assert intersection.z == pytest.approx(0)
    assert any(relation.type == "intersection" and relation.object_1 == "I" for relation in normalized.relations)



def test_normalize_scene_does_not_add_endpoint_segment_intersection():
    scene = scene_with([
        point("A", 0, 0, 0),
        point("B", 1, 0, 0),
        point("C", 1, 1, 0),
        Segment(points=["A", "B"]),
        Segment(points=["B", "C"]),
    ])

    normalized = normalize_scene(scene)

    assert len([obj for obj in normalized.objects if isinstance(obj, Point3D)]) == 3



def test_line_line_intersect():
    result = first_intersection([
        point("A", 0, 0, 0),
        point("B", 1, 0, 0),
        point("C", 0, 0, 0),
        point("D", 0, 1, 0),
        Line3D(name="d1", through=["A", "B"]),
        Line3D(name="d2", through=["C", "D"]),
    ])

    assert result["status"] == "intersect"
    assert_point_close(result["point"], (0, 0, 0))


def test_line_line_parallel():
    result = first_intersection([
        point("A", 0, 0, 0),
        point("B", 1, 0, 0),
        point("C", 0, 1, 0),
        point("D", 1, 1, 0),
        Line3D(name="d1", through=["A", "B"]),
        Line3D(name="d2", through=["C", "D"]),
    ])

    assert result["status"] == "parallel"
    assert result["point"] is None


def test_line_line_coincident():
    result = first_intersection([
        point("A", 0, 0, 0),
        point("B", 1, 0, 0),
        point("C", 2, 0, 0),
        point("D", 3, 0, 0),
        Line3D(name="d1", through=["A", "B"]),
        Line3D(name="d2", through=["C", "D"]),
    ])

    assert result["status"] == "coincident"
    assert result["point"] is None


def test_line_line_skew():
    result = first_intersection([
        point("A", 0, 0, 0),
        point("B", 1, 0, 0),
        point("C", 0, 1, 1),
        point("D", 0, 2, 1),
        Line3D(name="d1", through=["A", "B"]),
        Line3D(name="d2", through=["C", "D"]),
    ])

    assert result["status"] == "skew"
    assert result["point"] is None
    assert result["distance"] > 0


def test_line_line_degenerate():
    result = first_intersection([
        point("A", 0, 0, 0),
        point("B", 0, 0, 0),
        point("C", 0, 1, 0),
        point("D", 1, 1, 0),
        Line3D(name="d1", through=["A", "B"]),
        Line3D(name="d2", through=["C", "D"]),
    ])

    assert result["status"] == "degenerate"
    assert result["point"] is None


def test_line_plane_intersect():
    result = first_intersection([
        point("A", 0, 0, 0),
        point("B", 1, 0, 0),
        point("C", 0, 1, 0),
        point("P", 0, 0, 1),
        point("Q", 0, 0, -1),
        Line3D(name="d", through=["P", "Q"]),
        Plane(name="alpha", points=["A", "B", "C"]),
    ])

    assert result["status"] == "intersect"
    assert_point_close(result["point"], (0, 0, 0))


def test_line_plane_parallel():
    result = first_intersection([
        point("A", 0, 0, 0),
        point("B", 1, 0, 0),
        point("C", 0, 1, 0),
        point("P", 0, 0, 1),
        point("Q", 1, 0, 1),
        Line3D(name="d", through=["P", "Q"]),
        Plane(name="alpha", points=["A", "B", "C"]),
    ])

    assert result["status"] == "parallel"
    assert result["point"] is None


def test_line_plane_line_in_plane():
    result = first_intersection([
        point("A", 0, 0, 0),
        point("B", 1, 0, 0),
        point("C", 0, 1, 0),
        Line3D(name="d", through=["A", "B"]),
        Plane(name="alpha", points=["A", "B", "C"]),
    ])

    assert result["status"] == "line_in_plane"
    assert result["point"] is None


def test_line_plane_degenerate_plane():
    result = first_intersection([
        point("A", 0, 0, 0),
        point("B", 1, 0, 0),
        point("C", 2, 0, 0),
        point("P", 0, 0, 1),
        point("Q", 0, 0, -1),
        Line3D(name="d", through=["P", "Q"]),
        Plane(name="alpha", points=["A", "B", "C"]),
    ])

    assert result["status"] == "degenerate"
    assert result["point"] is None


def test_svd_plane_normal_handles_four_coplanar_points():
    computed = compute_three_geometry(scene_with([
        point("A", 0, 0, 0),
        point("B", 1, 0, 0),
        point("C", 0, 1, 0),
        point("D", 1, 1, 0),
        Plane(name="alpha", points=["A", "B", "C", "D"]),
    ]))

    normal = computed["vectors"][0]
    assert normal["kind"] == "normal"
    assert normal["from"]["z"] == pytest.approx(0)
    assert normal["to"]["z"] > 0


def test_degenerate_plane_has_no_normal_overlay():
    computed = compute_three_geometry(scene_with([
        point("A", 0, 0, 0),
        point("B", 1, 0, 0),
        point("C", 2, 0, 0),
        Plane(name="alpha", points=["A", "B", "C"]),
    ]))

    assert computed["vectors"] == []
    assert any("degenerate" in warning for warning in computed["warnings"])


def first_measurement(objects):
    computed = compute_three_geometry(scene_with(objects))
    assert computed["measurements"]
    return computed["measurements"][0]


def test_sphere_plane_distance_separate():
    result = first_measurement([
        point("O", 1, 2, 3),
        point("A", 0, 0, -4.5),
        point("B", 0, 9, 0),
        point("C", -4.5, 0, 0),
        Sphere(name="S", center="O", radius=3),
        Plane(name="P", points=["A", "B", "C"]),
    ])

    assert result["status"] == "separate"
    assert result["center_distance"] == pytest.approx(5)
    assert result["minimum_distance"] == pytest.approx(2)
    assert_point_close(result["plane_foot"], (-2.3333333333, 3.6666666667, -0.3333333333))
    assert_point_close(result["nearest_sphere_point"], (-1, 3, 1))


def test_sphere_plane_distance_tangent():
    result = first_measurement([
        point("O", 0, 0, 3),
        point("A", 0, 0, 0),
        point("B", 1, 0, 0),
        point("C", 0, 1, 0),
        Sphere(name="S", center="O", radius=3),
        Plane(name="P", points=["A", "B", "C"]),
    ])

    assert result["status"] == "tangent"
    assert result["minimum_distance"] == pytest.approx(0)


def test_sphere_plane_distance_intersect():
    result = first_measurement([
        point("O", 0, 0, 1),
        point("A", 0, 0, 0),
        point("B", 1, 0, 0),
        point("C", 0, 1, 0),
        Sphere(name="S", center="O", radius=3),
        Plane(name="P", points=["A", "B", "C"]),
    ])

    assert result["status"] == "intersect"
    assert result["minimum_distance"] == pytest.approx(0)


def test_prefer_o_origin_translates_existing_o():
    scene = scene_with([
        point("O", 2, 3, 4),
        point("A", 5, 3, 4),
    ])

    normalized = normalize_scene(scene, AdvancedRenderSettings(coordinate_assignment="prefer_o_origin"))
    points = {obj.name: obj for obj in normalized.objects if isinstance(obj, Point3D)}

    assert points["O"].x == pytest.approx(0)
    assert points["O"].y == pytest.approx(0)
    assert points["O"].z == pytest.approx(0)
    assert points["A"].x == pytest.approx(3)
    assert points["A"].y == pytest.approx(0)
    assert points["A"].z == pytest.approx(0)


def test_auto_origin_chooses_nice_existing_point():
    scene = scene_with([
        point("A", 10, 0, 0),
        point("B", 11, 0, 0),
        point("C", 10, 2, 0),
    ])

    normalized = normalize_scene(scene, AdvancedRenderSettings(coordinate_assignment="auto_origin"))
    points = {obj.name: obj for obj in normalized.objects if isinstance(obj, Point3D)}

    assert points["A"].x == pytest.approx(0)
    assert points["B"].x == pytest.approx(1)
    assert points["C"].y == pytest.approx(2)


def test_ai_coordinate_assignment_keeps_coordinates():
    scene = scene_with([
        point("A", 10, 0, 0),
        point("B", 11, 0, 0),
    ])

    normalized = normalize_scene(scene, AdvancedRenderSettings(coordinate_assignment="ai"))
    points = {obj.name: obj for obj in normalized.objects if isinstance(obj, Point3D)}

    assert points["A"].x == pytest.approx(10)
    assert points["B"].x == pytest.approx(11)


def test_origin_rebase_preserves_exact_expressions():
    scene = scene_with([
        Point3D(name="A", x=2 ** 0.5, y=0.5, z=0, x_expr="sqrt(2)", y_expr="1/2", z_expr="0"),
        Point3D(name="B", x=2 ** 0.5 + 1, y=0.5, z=0, x_expr="sqrt(2)+1", y_expr="1/2", z_expr="0"),
    ])

    normalized = normalize_scene(scene, AdvancedRenderSettings(coordinate_assignment="auto_origin"))
    points = {obj.name: obj for obj in normalized.objects if isinstance(obj, Point3D)}

    assert points["A"].x_expr == "0"
    assert points["B"].x_expr == "1"
    assert points["B"].y_expr == "0"
