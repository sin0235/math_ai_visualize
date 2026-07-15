import pytest

from app.schemas.geometry_reasoning import GeometryProofPlan
from app.services.geometry.proof_search import replay_proof_plan
from app.services.geometry_theorems import theorem
from app.services.solver_service import solve


def _plan_payload():
    return {
        "goal": {
            "task": "distance",
            "subtype": "point_plane",
            "target_object_ids": ["point-s", "plane-abc"],
        },
        "facts": [
            {
                "fact_id": "fact-sa-perp-abc",
                "type": "perpendicular_line_plane",
                "object_ids": ["segment-sa", "plane-abc"],
                "provenance": "verified",
                "evidence": [
                    {
                        "source": "relation",
                        "ref_id": "relation-sa-perp-abc",
                        "status": "verified",
                        "verifier": "geometry-kernel-v3",
                    }
                ],
            }
        ],
        "steps": [
            {
                "index": 1,
                "title": "Nhận ra đường cao",
                "explanation": "SA vuông góc với mặt phẳng (ABC), nên SA là đoạn khoảng cách.",
                "claim": {
                    "claim_id": "claim-distance-is-sa",
                    "text": "d(S,(ABC)) = SA",
                    "fact_ids": ["fact-sa-perp-abc"],
                    "theorem_id": "distance.point_plane.perpendicular_segment",
                },
                "highlight_object_ids": ["point-s", "segment-sa", "plane-abc"],
                "relation_ids": ["relation-sa-perp-abc"],
            },
            {
                "index": 2,
                "title": "Kết luận",
                "explanation": "Vì SA = 3 nên d(S,(ABC)) = 3.",
                "claim": {
                    "claim_id": "claim-answer",
                    "text": "d(S,(ABC)) = 3",
                    "depends_on": ["claim-distance-is-sa"],
                },
                "highlight_object_ids": ["segment-sa"],
            },
        ],
        "answer": "d(S,(ABC)) = 3",
        "verification_state": "verified",
    }


def test_geometry_proof_contract_accepts_grounded_ordered_plan():
    plan = GeometryProofPlan.model_validate(_plan_payload())

    assert plan.steps[0].claim.theorem_id == "distance.point_plane.perpendicular_segment"
    assert plan.steps[1].claim.depends_on == ["claim-distance-is-sa"]


def test_geometry_proof_contract_accepts_33_highlight_object_ids():
    payload = _plan_payload()
    payload["steps"][0]["highlight_object_ids"] = [f"object-{index}" for index in range(33)]

    plan = GeometryProofPlan.model_validate(payload)

    assert len(plan.steps[0].highlight_object_ids) == 33


def test_geometry_proof_contract_rejects_unknown_fact_reference():
    payload = _plan_payload()
    payload["steps"][0]["claim"]["fact_ids"] = ["missing"]

    with pytest.raises(ValueError, match="fact không tồn tại"):
        GeometryProofPlan.model_validate(payload)


def test_geometry_proof_contract_rejects_forward_claim_dependency():
    payload = _plan_payload()
    payload["steps"][0]["claim"]["depends_on"] = ["claim-answer"]

    with pytest.raises(ValueError, match="chưa được chứng minh"):
        GeometryProofPlan.model_validate(payload)


def test_theorem_registry_exposes_typed_replay_contract():
    spec = theorem("distance.point_plane.perpendicular_segment")

    assert [premise.fact_type for premise in spec.premises] == ["perpendicular_line_plane"]
    assert spec.conclusion == "distance_equals_perpendicular_segment"
    assert spec.construction == ("project_point",)
    assert spec.cost > 0


def test_classical_solver_builds_replayable_proof_plan():
    scene = {
        "problem_text": "Cho SA vuông góc (ABC), SA = 3.",
        "topic": "solid_geometry",
        "objects": [
            {"object_id": "point-s", "type": "point_3d", "name": "S", "x": 0, "y": 0, "z": 3},
            {"object_id": "point-a", "type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"object_id": "point-b", "type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"object_id": "point-c", "type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 0},
        ],
        "annotations": [
            {"id": "length-sa", "type": "length", "target": "S-A", "label": "3", "metadata": {"source": "given"}},
        ],
        "relations": [
            {
                "id": "sa-perp-base",
                "type": "perpendicular",
                "object_1": "SA",
                "object_2": "plane(ABC)",
                "metadata": {"source": "given"},
            }
        ],
    }

    result = solve(scene, "d(S,(ABC))", geometry_method="classical")
    plan = GeometryProofPlan.model_validate(result.proof_plan)
    replay = replay_proof_plan(plan)

    assert result.answer == "d(S,(ABC)) = 3"
    assert replay.accepted is True
    assert plan.verification_state == "verified"
    assert all(
        not step.claim.depends_on or step.claim.depends_on[0] == plan.steps[index - 1].claim.claim_id
        for index, step in enumerate(plan.steps[1:], start=1)
    )


def test_proof_replay_catches_mutated_premise_type():
    payload = _plan_payload()
    payload["facts"][0]["type"] = "length"
    payload["steps"][0]["claim"]["theorem_id"] = "distance.point_plane.perpendicular_segment"
    plan = GeometryProofPlan.model_validate(payload)

    replay = replay_proof_plan(plan)

    assert replay.accepted is False
    assert replay.reason and "Missing premise" in replay.reason


def test_classical_solver_rejects_render_coordinates_without_premise():
    scene = {
        "problem_text": "Cho hình chóp S.ABC.",
        "topic": "solid_geometry",
        "objects": [
            {"type": "point_3d", "name": "S", "x": 0, "y": 0, "z": 3},
            {"type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
            {"type": "point_3d", "name": "B", "x": 1, "y": 0, "z": 0},
            {"type": "point_3d", "name": "C", "x": 0, "y": 1, "z": 0},
        ],
    }

    result = solve(scene, "d(S,(ABC))", geometry_method="classical")

    assert result.answer == "Không đủ dữ kiện"
    assert result.proof_plan is None
    assert any("không dùng tọa độ minh họa" in warning for warning in result.warnings)
