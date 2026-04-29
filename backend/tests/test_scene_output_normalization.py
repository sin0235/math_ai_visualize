from app.renderers.three_scene import build_three_scene
from app.schemas.scene import MathScene, SceneView
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
