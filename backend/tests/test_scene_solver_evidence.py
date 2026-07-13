from app.schemas.scene_v3 import MathSceneV3
from app.services.downstream_scene_v3 import scene_v3_to_solver_input
from app.services.geometry_facts import build_geometry_fact_graph


def _scene() -> MathSceneV3:
    return MathSceneV3.model_validate({
        "scene_id": "scene-evidence",
        "revision": 1,
        "problem_text": "Cho SA vuông góc với (ABC), SA = 3.",
        "topic": "solid_geometry",
        "renderer": "threejs_3d",
        "view": {"dimension": "3d"},
        "objects": [
            {"id": "point-s", "type": "point_3d", "label": "S", "x": 0, "y": 0, "z": 3},
            {"id": "point-a", "type": "point_3d", "label": "A", "x": 0, "y": 0, "z": 0},
            {"id": "point-b", "type": "point_3d", "label": "B", "x": 1, "y": 0, "z": 0},
            {"id": "point-c", "type": "point_3d", "label": "C", "x": 0, "y": 1, "z": 0},
            {"id": "segment-sa", "type": "segment", "label": "SA", "point_ids": ["point-s", "point-a"]},
            {"id": "plane-abc", "type": "plane", "label": "ABC", "point_ids": ["point-a", "point-b", "point-c"]},
        ],
        "relations": [
            {
                "id": "relation-sa-perp-abc",
                "type": "perpendicular",
                "operands": [
                    {"role": "line", "ref_id": "segment-sa", "ref_kind": "segment"},
                    {"role": "plane", "ref_id": "plane-abc", "ref_kind": "plane"},
                ],
                "source": "given",
                "verification": {
                    "relation_id": "relation-sa-perp-abc",
                    "status": "verified",
                    "verifier": "geometry-kernel-v3",
                    "residual": 0,
                },
            }
        ],
        "annotations": [
            {
                "id": "annotation-sa",
                "type": "length",
                "target_ids": ["point-s", "point-a"],
                "label": "3",
                "provenance": "given",
                "relation_id": "relation-sa-perp-abc",
            }
        ],
        "derived_facts": [
            {
                "id": "derived-height",
                "kind": "measurement",
                "source_ids": ["segment-sa"],
                "value": {"text": "SA là chiều cao", "length": 3},
                "provenance": "verified",
                "relation_id": "relation-sa-perp-abc",
            }
        ],
        "construction_steps": [
            {
                "id": "construction-height",
                "description": "Dựng SA vuông góc đáy",
                "object_ids": ["segment-sa"],
                "relation_ids": ["relation-sa-perp-abc"],
            }
        ],
        "audit": {"created_by": "manual"},
    })


def test_solver_adapter_preserves_scene_evidence_and_identity():
    payload = scene_v3_to_solver_input(_scene())

    assert payload["objects"][0]["object_id"] == "point-s"
    assert payload["relations"][0]["operands"][0]["ref_id"] == "segment-sa"
    assert payload["relations"][0]["verification"]["status"] == "verified"
    assert payload["annotations"][0]["target_ids"] == ["point-s", "point-a"]
    assert payload["derived_facts"][0]["id"] == "derived-height"
    assert payload["construction_steps"][0]["relation_ids"] == ["relation-sa-perp-abc"]


def test_fact_graph_keeps_verified_derived_fact():
    graph = build_geometry_fact_graph(scene_v3_to_solver_input(_scene()))

    fact = next(item for item in graph.facts if item.id == "derived-height")
    assert fact.type == "derived_measurement"
    assert fact.trusted is True


def test_unverifiable_inferred_relation_is_not_trusted():
    graph = build_geometry_fact_graph({
        "relations": [
            {
                "id": "inferred-unverifiable",
                "type": "perpendicular",
                "object_1": "SA",
                "object_2": "plane(ABC)",
                "source": "ai_inferred",
                "verification": {"status": "unverifiable"},
                "metadata": {"confidence": "unverifiable"},
            }
        ]
    })

    assert graph.facts[0].trusted is False
    assert graph.by_type("perpendicular_line_plane") == []