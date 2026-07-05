import pytest

from app.schemas.scene import MathScene
from app.services.render_quality_gate import assert_scene_safe_for_downstream
from app.services.scene_trust import scene_trust_labels, scene_with_trusted_annotations


def _scene(**overrides) -> MathScene:
    data = {
        "problem_text": "Tam giác ABC có AB = 3",
        "renderer": "geogebra_2d",
        "topic": "coordinate_2d",
        "view": {"dimension": "2d"},
        "objects": [
            {"type": "point_2d", "name": "A", "x": 0, "y": 0},
            {"type": "point_2d", "name": "B", "x": 3, "y": 0},
            {"type": "segment", "points": ["A", "B"]},
        ],
        "annotations": [],
        "relations": [],
    }
    data.update(overrides)
    return MathScene.model_validate(data)


def test_assumptions_block_downstream_until_user_confirms():
    scene = _scene(interpretation={"assumptions": ["Chọn C để hình dễ nhìn"], "missing_data": []})

    with pytest.raises(ValueError, match="giả định"):
        assert_scene_safe_for_downstream(scene, operation="giải bài")

    assert_scene_safe_for_downstream(scene, operation="giải bài", user_confirmed=True)


def test_missing_data_blocks_downstream_until_user_confirms():
    scene = _scene(interpretation={"assumptions": [], "missing_data": ["chưa biết AC"]})

    with pytest.raises(ValueError, match="thiếu dữ kiện"):
        assert_scene_safe_for_downstream(scene, operation="xuất file")

    assert_scene_safe_for_downstream(scene, operation="xuất file", user_confirmed=True)


def test_scene_trust_filters_untrusted_measurement_labels():
    scene = _scene(
        annotations=[
            {"type": "length", "target": "A-B", "label": "3", "metadata": {"source": "given", "confidence": "partial"}},
            {"type": "length", "target": "A-B", "label": "7", "metadata": {"source": "construction", "confidence": "unverified"}},
        ]
    )

    filtered, hidden = scene_with_trusted_annotations(scene)

    assert hidden == 1
    assert [annotation.label for annotation in filtered.annotations] == ["3"]


def test_scene_trust_labels_show_illustration_and_assumption():
    scene = _scene(interpretation={"assumptions": ["C tự chọn"], "missing_data": []})

    assert scene_trust_labels(scene) == ["Hình minh họa", "Không theo tỉ lệ", "Có giả định"]