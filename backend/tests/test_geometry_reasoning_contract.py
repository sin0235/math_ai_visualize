import pytest

from app.schemas.geometry_reasoning import GeometryProofPlan


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