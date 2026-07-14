import pytest

from app.schemas.scene_v3 import FaceV3, SegmentV3
from app.services.extractor_v3 import parse_math_scene_v3
from app.services.scene_fidelity_v3 import complete_standard_solid_topology


def _point(label: str, index: int) -> dict:
    slug = label.lower().replace("'", "_prime")
    return {
        "id": f"pt_{slug}",
        "type": "point_3d",
        "label": label,
        "x": float(index % 4),
        "y": float(index // 4),
        "z": float((index // 2) % 2),
    }


def _raw_solid(problem_text: str, labels: tuple[str, ...], *, relations: list[dict] | None = None) -> dict:
    return {
        "topic": "solid_geometry",
        "renderer": "threejs_3d",
        "objects": [_point(label, index) for index, label in enumerate(labels)],
        "relations": relations or [],
        "view": {"dimension": "3d"},
        "audit": {"created_by": "test"},
    }


def test_box_points_are_completed_to_twelve_edges_and_six_colored_faces():
    scene = parse_math_scene_v3(
        _raw_solid("Cho hình hộp chữ nhật ABCD.EFGH.", tuple("ABCDEFGH")),
        problem_text="Cho hình hộp chữ nhật ABCD.EFGH.",
        grade=11,
    )

    segments = [obj for obj in scene.objects if isinstance(obj, SegmentV3)]
    faces = [obj for obj in scene.objects if isinstance(obj, FaceV3)]
    assert len(segments) == 12
    assert len(faces) == 6
    assert len({face.color for face in faces}) == 6
    assert all(segment.style == "solid" and not segment.hidden for segment in segments)
    assert all(obj.source == "construction" for obj in [*segments, *faces])


@pytest.mark.parametrize(
    ("problem_text", "labels", "expected_segments", "expected_faces"),
    [
        ("Cho lăng trụ ABC.A'B'C'.", ("A", "B", "C", "A'", "B'", "C'"), 9, 5),
        ("Cho hình chóp S.ABCD.", ("S", "A", "B", "C", "D"), 8, 5),
        ("Cho tứ diện ABCD.", ("A", "B", "C", "D"), 6, 4),
    ],
)
def test_standard_solids_receive_complete_topology(
    problem_text: str,
    labels: tuple[str, ...],
    expected_segments: int,
    expected_faces: int,
):
    scene = parse_math_scene_v3(
        _raw_solid(problem_text, labels),
        problem_text=problem_text,
        grade=11,
    )

    assert sum(isinstance(obj, SegmentV3) for obj in scene.objects) == expected_segments
    assert sum(isinstance(obj, FaceV3) for obj in scene.objects) == expected_faces


def test_missing_standard_segment_reference_is_repaired_before_validation():
    problem_text = "Cho hình hộp chữ nhật ABCD.EFGH, biết AB = CD."
    relations = [{
        "id": "rel_equal",
        "type": "equal_length",
        "operands": [
            {"role": "first", "ref_id": "seg_ab", "ref_kind": "segment"},
            {"role": "second", "ref_id": "seg_cd", "ref_kind": "segment"},
        ],
    }]

    scene = parse_math_scene_v3(
        _raw_solid(problem_text, tuple("ABCDEFGH"), relations=relations),
        problem_text=problem_text,
        grade=11,
    )

    by_id = {obj.id: obj for obj in scene.objects}
    assert isinstance(by_id["seg_ab"], SegmentV3)
    assert isinstance(by_id["seg_cd"], SegmentV3)
    assert by_id["seg_cd"].point_ids == ("pt_c", "pt_d")


def test_completion_is_idempotent():
    scene = parse_math_scene_v3(
        _raw_solid("Cho tứ diện ABCD.", tuple("ABCD")),
        problem_text="Cho tứ diện ABCD.",
        grade=11,
    )

    completed_again = complete_standard_solid_topology(scene)

    assert [obj.id for obj in completed_again.objects] == [obj.id for obj in scene.objects]


def test_ambiguous_standard_solid_fails_instead_of_guessing():
    with pytest.raises(ValueError, match="SOLID_TOPOLOGY_AMBIGUOUS"):
        parse_math_scene_v3(
            _raw_solid("Cho một hình hộp chữ nhật.", ("X", "Y", "Z")),
            problem_text="Cho một hình hộp chữ nhật.",
            grade=11,
        )
