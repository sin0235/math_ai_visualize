from app.renderers.geogebra_commands import build_geogebra_commands
from app.renderers.three_scene import build_three_scene
from app.schemas.scene import AdvancedRenderSettings, MathScene, SceneView
from app.services.extractor import normalize_scene_json


def test_normalize_angle_target_and_arms():
    data = normalize_scene_json({
        "problem_text": "test",
        "renderer": "threejs_3d",
        "objects": [],
        "annotations": [
            {"type": "angle", "target": "ABC", "label": "60°", "metadata": {}},
            {"type": "angle", "target": "D", "metadata": {"arms": "E,F"}},
        ],
        "view": {"dimension": "3d"},
    })

    assert data["annotations"][0]["target"] == "B"
    assert data["annotations"][0]["metadata"]["arms"] == ["A", "C"]
    assert data["annotations"][0]["color"] == "#b45309"
    assert data["annotations"][1]["metadata"]["arms"] == ["E", "F"]


def test_normalize_segment_target_and_color_names():
    data = normalize_scene_json({
        "problem_text": "test",
        "renderer": "threejs_3d",
        "objects": [
            {"type": "segment", "points": ["A", "B"], "color": "orange", "style": "weird"},
        ],
        "annotations": [
            {"type": "length", "target": "AB", "label": "a", "metadata": {}},
        ],
        "view": {"dimension": "3d"},
    })

    segment = data["objects"][0]
    assert segment["hidden"] is False
    assert segment["color"] == "#f97316"
    assert segment["style"] == "solid"
    assert data["annotations"][0]["target"] == "A-B"


def test_segment_style_reaches_three_scene_payload():
    scene = MathScene(
        problem_text="test",
        renderer="threejs_3d",
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "segment", "points": ["A", "B"], "hidden": False, "color": "#f97316", "line_width": 4, "style": "dashed"},
        ],
        view=SceneView(dimension="3d"),
    )

    segment = build_three_scene(scene)["segments"][0]
    assert segment["color"] == "#f97316"
    assert segment["line_width"] == 4
    assert segment["style"] == "dashed"


def test_segment_style_reaches_geogebra_commands():
    scene = MathScene(
        problem_text="test",
        renderer="geogebra_2d",
        objects=[
            {"type": "point_2d", "name": "A", "x": 0, "y": 0},
            {"type": "point_2d", "name": "B", "x": 1, "y": 0},
            {"type": "segment", "name": "edge", "points": ["A", "B"], "hidden": True, "color": "#f97316", "line_width": 4, "style": "dashed"},
        ],
        view=SceneView(dimension="2d"),
    )

    commands = build_geogebra_commands(scene)
    assert "edge = Segment(A, B)" in commands
    assert "SetColor(edge, 249, 115, 22)" in commands
    assert "SetLineThickness(edge, 4)" in commands
    assert "SetLineStyle(edge, 1)" in commands
    assert "SetVisibleInView(edge, 1, false)" in commands


def test_geogebra_commands_include_basic_annotations():
    scene = MathScene(
        problem_text="test",
        renderer="geogebra_2d",
        objects=[
            {"type": "point_2d", "name": "A", "x": 0, "y": 0},
            {"type": "point_2d", "name": "B", "x": 1, "y": 0},
            {"type": "point_2d", "name": "C", "x": 1, "y": 1},
        ],
        annotations=[
            {"type": "length", "target": "A-B", "label": "a", "metadata": {}},
            {"type": "equal_marks", "target": "B-C", "metadata": {}},
            {"type": "right_angle", "target": "B", "label": "90°", "metadata": {"arms": ["A", "C"]}},
            {"type": "coordinate_label", "target": "A", "metadata": {}},
        ],
        view=SceneView(dimension="2d"),
    )

    commands = build_geogebra_commands(scene)
    assert "annMid1 = Midpoint(A, B)" in commands
    assert 'annText1 = Text("a", annMid1)' in commands
    assert "annMid2 = Midpoint(B, C)" in commands
    assert 'annText2 = Text("≅", annMid2)' in commands
    assert "annAngle1 = Angle(A, B, C)" in commands
    assert 'SetCaption(annAngle1, "90°")' in commands
    assert 'SetCaption(A, "A = (0, 0)")' in commands


def test_geogebra_commands_support_basic_3d_objects_and_coordinate_labels():
    scene = MathScene(
        problem_text="test",
        renderer="geogebra_3d",
        objects=[
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 0},
            {"type": "line_3d", "name": "l", "through": ["A", "B"], "color": "#1d3557"},
            {"type": "vector_3d", "name": "u", "from_point": "A", "to_point": "C", "color": "#7c3aed"},
            {"type": "plane", "name": "p", "points": ["A", "B", "C"], "color": "#4f8cff", "opacity": 0.16},
            {"type": "sphere", "name": "s", "center": "A", "radius": 2, "color": "#5da9ff", "opacity": 0.18},
            {"type": "face", "name": "abc", "points": ["A", "B", "C"], "color": "#4f8cff", "opacity": 0.22},
        ],
        view=SceneView(dimension="3d", show_coordinates=True),
    )

    commands = build_geogebra_commands(scene, AdvancedRenderSettings(show_coordinates=True))
    assert "A = (0.0, 0.0, 0.0)" in commands
    assert 'SetCaption(A, "A = (0, 0, 0)")' in commands
    assert "l = Line(A, B)" in commands
    assert "u = Vector(A, C)" in commands
    assert "p = Plane(A, B, C)" in commands
    assert "s = Sphere(A, 2.0)" in commands
    assert "abc = Polygon(A, B, C)" in commands
    assert "SetFilling(p, 0.16)" in commands
    assert "SetColor(u, 124, 58, 237)" in commands
