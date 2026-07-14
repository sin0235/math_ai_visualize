import pytest

from app.services.extractor_v3 import parse_math_scene_v3
from app.services.scene_pipeline_v3 import run_scene_pipeline_v3


def _scene(problem_text: str, points: list[tuple[str, float, float, float]]):
    return parse_math_scene_v3(
        {
            "topic": "solid_geometry",
            "renderer": "threejs_3d",
            "objects": [
                {"id": f"pt_{label.lower()}", "type": "point_3d", "label": label, "x": x, "y": y, "z": z}
                for label, x, y, z in points
            ],
            "view": {"dimension": "3d"},
            "audit": {"created_by": "test"},
        },
        problem_text=problem_text,
        grade=11,
    )


@pytest.mark.parametrize(
    ("problem_text", "points", "goal_kind"),
    [
        (
            "Góc ABC bằng bao nhiêu?",
            [("A", 1, 0, 0), ("B", 0, 0, 0), ("C", 0, 1, 0)],
            "point_angle",
        ),
        (
            "Tính góc giữa hai đường thẳng AB và CD.",
            [("A", 0, 0, 0), ("B", 1, 0, 0), ("C", 0, 1, 1), ("D", 0, 2, 1)],
            "line_line",
        ),
        (
            "Tính góc giữa đường thẳng MN và mặt phẳng (PFB).",
            [("M", 0, 2, 0), ("N", 1, 0, 0), ("P", 0, 0, 0), ("F", 1, 0, 0), ("B", 0, 0, 1)],
            "line_plane",
        ),
        (
            "Tính góc giữa hai mặt phẳng (ABC) và (PFB).",
            [
                ("A", 0, 0, 0), ("B", 1, 0, 0), ("C", 0, 1, 0),
                ("P", 0, 0, 0), ("F", 0, 0, 1),
            ],
            "plane_plane",
        ),
    ],
)
def test_angle_goal_creates_safe_visible_annotation(problem_text, points, goal_kind):
    scene = _scene(problem_text, points)
    annotation = next(
        item for item in scene.annotations
        if item.metadata.get("visualization_role") == "angle_goal"
    )

    assert annotation.type == "angle"
    assert annotation.metadata["goal_kind"] == goal_kind
    assert len(annotation.target_ids) == 3
    result = run_scene_pipeline_v3(scene)
    assert result.can_project
    assert result.projection is not None
    assert [item.annotation_id for item in result.projection.annotations] == [annotation.id]
