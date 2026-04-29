import pytest

from app.schemas.scene import Line3D, MathScene, Plane, Point3D, Relation, SceneView, Segment, Sphere
from app.services.geometry_engine import compute_three_geometry, normalize_scene


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


def annotation_targets(scene, annotation_type):
    return [annotation.target for annotation in scene.annotations if annotation.type == annotation_type]


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
