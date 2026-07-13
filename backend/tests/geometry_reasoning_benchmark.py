from __future__ import annotations

import json
from dataclasses import dataclass

from app.services.solver_service import solve


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    question: str
    expected_answer: str


SCENE = {
    "problem_text": "Cho hình chóp S.ABCD có SA vuông góc đáy, SA = 3, AB = AC = 4 và ABCD là hình vuông.",
    "topic": "solid_geometry",
    "objects": [
        {"object_id": "point-s", "type": "point_3d", "name": "S", "x": 0, "y": 0, "z": 3},
        {"object_id": "point-a", "type": "point_3d", "name": "A", "x": 0, "y": 0, "z": 0},
        {"object_id": "point-b", "type": "point_3d", "name": "B", "x": 4, "y": 0, "z": 0},
        {"object_id": "point-c", "type": "point_3d", "name": "C", "x": 0, "y": 4, "z": 0},
        {"object_id": "point-d", "type": "point_3d", "name": "D", "x": 4, "y": 4, "z": 0},
        {"object_id": "point-e", "type": "point_3d", "name": "E", "x": 2, "y": 0, "z": 0},
        {"object_id": "face-abcd", "type": "face", "name": "ABCD", "points": ["A", "B", "D", "C"]},
    ],
    "annotations": [
        {"id": "length-sa", "type": "length", "target": "S-A", "label": "3", "metadata": {"source": "given"}},
        {"id": "length-ab", "type": "length", "target": "A-B", "label": "4", "metadata": {"source": "given"}},
        {"id": "length-ac", "type": "length", "target": "A-C", "label": "4", "metadata": {"source": "given"}},
    ],
    "relations": [
        {
            "id": "sa-perp-base",
            "type": "perpendicular",
            "object_1": "SA",
            "object_2": "plane(ABC)",
            "metadata": {"source": "given", "confidence": "verified"},
            "verification": {"status": "verified"},
        },
        {
            "id": "ab-perp-ac",
            "type": "perpendicular",
            "object_1": "AB",
            "object_2": "AC",
            "metadata": {"source": "inferred", "confidence": "verified"},
            "verification": {"status": "verified"},
        },
        {
            "id": "ab-parallel-cd",
            "type": "parallel",
            "object_1": "AB",
            "object_2": "CD",
            "metadata": {"source": "given", "confidence": "verified"},
            "verification": {"status": "verified"},
        },
        {
            "id": "aeb-collinear",
            "type": "collinear",
            "operand_names": ["A", "E", "B"],
            "object_1": "A",
            "object_2": "E",
            "metadata": {"source": "given", "confidence": "verified"},
            "verification": {"status": "verified"},
        },
        {
            "id": "abcd-coplanar",
            "type": "coplanar",
            "operand_names": ["A", "B", "C", "D"],
            "object_1": "A",
            "object_2": "B",
            "metadata": {"source": "given", "confidence": "verified"},
            "verification": {"status": "verified"},
        },
    ],
}

CASES = (
    BenchmarkCase("distance-point-plane", "d(S,(ABC))", "d(S,(ABC)) = 3"),
    BenchmarkCase("distance-point-line", "d(S,AB)", "d(S,AB) = 3"),
    BenchmarkCase("angle-line-line", "Góc giữa AB và AC", "\\angle(AB,AC) = 90°"),
    BenchmarkCase("angle-line-plane", "Góc giữa SB và (ABC)", "\\angle(SB,(ABC)) = 36.869898°"),
    BenchmarkCase("angle-plane-plane", "Góc giữa (SAB) và (ABC)", "\\angle((SAB),(ABC)) = 90°"),
    BenchmarkCase("area", "S(ABC)", "S(ABC) = 8"),
    BenchmarkCase("volume", "V(S.ABC)", "V(S.ABC) = 8"),
    BenchmarkCase("proof-perpendicular", "Chứng minh AB vuông góc AC", "AB vuông góc AC: ĐÚNG"),
    BenchmarkCase("proof-parallel", "Chứng minh AB song song CD", "AB song song CD: ĐÚNG"),
    BenchmarkCase("proof-collinear", "Chứng minh AEB thẳng hàng", "AEB thẳng hàng: ĐÚNG"),
    BenchmarkCase("proof-coplanar", "Chứng minh ABCD đồng phẳng", "ABCD đồng phẳng: ĐÚNG"),
)


def evaluate() -> dict[str, float | int]:
    results = [solve(SCENE, case.question, geometry_method="classical") for case in CASES]
    answers = sum(result.answer == case.expected_answer for case, result in zip(CASES, results, strict=True))
    theorem_cases = sum(bool(result.used_theorems) for result in results)
    grounded_steps = sum(
        bool(result.steps) and all(step.claim and (step.depends_on or step.kind == "input") for step in result.steps)
        for result in results
    )
    fallbacks = sum(not result.used_theorems for result in results)
    object_ids = {str(item.get("object_id")) for item in SCENE["objects"] if item.get("object_id")}
    construction_actions = [action for result in results for step in result.steps for action in step.construction_actions]
    valid_construction_actions = sum(
        set(action.get("source_object_ids") or []).issubset(object_ids)
        and (not action.get("result_object_id") or action["result_object_id"] in object_ids)
        for action in construction_actions
    )
    total = len(CASES)
    return {
        "cases": total,
        "answer_accuracy": answers / total,
        "theorem_coverage": theorem_cases / total,
        "fully_grounded_proof_rate": grounded_steps / total,
        "construction_reference_validity": valid_construction_actions / len(construction_actions) if construction_actions else 1.0,
        "fallback_rate": fallbacks / total,
    }


if __name__ == "__main__":
    report = evaluate()
    assert report["cases"] == len(CASES)
    assert report["answer_accuracy"] >= 1.0
    assert report["theorem_coverage"] >= 1.0
    assert report["fully_grounded_proof_rate"] >= 1.0
    assert report["construction_reference_validity"] >= 1.0
    assert report["fallback_rate"] <= 0.0
    print(json.dumps(report, ensure_ascii=False, indent=2))