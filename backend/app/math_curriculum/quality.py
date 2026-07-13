from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import sympy as sp

from app.math_curriculum import CAPABILITY_REGISTRY_VERSION, CURRICULUM_VERSION, SKILLS
from app.math_curriculum.rollout import ROLLOUT_VERSION, rollout_stage
from app.math_curriculum.coverage import build_coverage_report
from app.schemas.geometry_reasoning import GeometryProofPlan
from app.schemas.math_solution import VerificationEvidence
from app.services.algebra.parser import parse_algebra_problem
from app.services.algebra.verifier import verify_finite_solutions
from app.services.geometry.proof_search import replay_proof_plan
from app.services.math_verification import evaluate_verification_contract

def build_quality_report(corpus_path: Path, tests_dir: Path) -> dict[str, Any]:
    coverage = build_coverage_report(corpus_path, tests_dir)
    rows = {str(row["skill_id"]): row for row in coverage["skills"]}
    capabilities: list[dict[str, Any]] = []
    blockers: list[str] = []
    for skill in SKILLS.values():
        row = rows[skill.skill_id]
        stage = rollout_stage(skill.status)
        static_checks = {
            "corpus_and_tests": row["evidence"] == "corpus_and_tests",
            "solver_registered": bool(skill.current_engines),
            "verifier_policy_registered": bool(skill.verification.methods),
            "public_status": skill.status == "supported",
        }
        if stage == "public":
            failures = [name for name, passed in static_checks.items() if name != "public_status" and not passed]
            blockers.extend(f"{skill.skill_id}:{failure}" for failure in failures)
        capabilities.append({
            "skill_id": skill.skill_id,
            "strand": skill.strand.value,
            "status": skill.status,
            "rollout_stage": stage,
            "evidence": row["evidence"],
            "minimum_exactness": skill.verification.minimum_exactness,
            "verifier_methods": list(skill.verification.methods),
            "limits_profile": "geometry_scene" if skill.strand.value == "geometry" else "function_analysis" if skill.strand.value == "function" else "expression",
            "static_checks": static_checks,
        })

    mutations = run_mutation_checks()
    stages = Counter(str(item["rollout_stage"]) for item in capabilities)
    mutation_rate = sum(bool(item["caught"]) for item in mutations) / len(mutations)
    return {
        "rollout_version": ROLLOUT_VERSION,
        "curriculum_version": CURRICULUM_VERSION,
        "capability_registry_version": CAPABILITY_REGISTRY_VERSION,
        "coverage": {
            "corpus_case_count": coverage["corpus_case_count"],
            "evidence_counts": coverage["evidence_counts"],
        },
        "rollout_stage_counts": dict(sorted(stages.items())),
        "mutation": {
            "cases": len(mutations),
            "caught": sum(bool(item["caught"]) for item in mutations),
            "catch_rate": mutation_rate,
            "checks": mutations,
        },
        "public_blockers": blockers,
        "ready": not blockers and mutation_rate == 1.0,
        "capabilities": capabilities,
    }


def run_mutation_checks() -> list[dict[str, object]]:
    equation = parse_algebra_problem("2*x + 3 = 7", topic="equation", variables=["x"])
    wrong_root = verify_finite_solutions(equation, [sp.Integer(3)])
    verification_contract = evaluate_verification_contract(
        ["probability.classical"],
        "partial",
        [
            VerificationEvidence(
                policy_methods=["stdlib_fraction_recompute"],
                status="fail",
                method="stdlib_fraction_recompute",
            )
        ],
    )
    proof = GeometryProofPlan.model_validate({
        "goal": {
            "task": "distance",
            "subtype": "point_plane",
            "target_object_ids": ["S", "ABC"],
            "method": "classical",
        },
        "facts": [{
            "fact_id": "mutated-length",
            "type": "length",
            "object_ids": ["S", "A"],
            "provenance": "given",
            "evidence": [{"source": "annotation", "ref_id": "mutated-length", "status": "given"}],
        }],
        "steps": [{
            "index": 1,
            "title": "Mutation premise",
            "explanation": "Đổi fact vuông góc thành fact độ dài.",
            "claim": {
                "claim_id": "mutated-claim",
                "text": "d(S,(ABC)) = SA",
                "fact_ids": ["mutated-length"],
                "theorem_id": "distance.point_plane.perpendicular_segment",
            },
        }],
        "answer": "d(S,(ABC)) = SA",
        "verification_state": "verified",
    })
    proof_replay = replay_proof_plan(proof)
    return [
        {
            "id": "algebra_wrong_root",
            "caught": wrong_root.status == "failed" and any(check.status == "fail" for check in wrong_root.checks),
        },
        {
            "id": "verification_failed_evidence",
            "caught": not verification_contract.accepted,
        },
        {
            "id": "geometry_missing_premise",
            "caught": not proof_replay.accepted,
        },
    ]


def main() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Dashboard quality và rollout capability toán.")
    parser.add_argument("--corpus", type=Path, default=backend_root.parent / "data/nlp/corpus/v2.jsonl")
    parser.add_argument("--tests", type=Path, default=backend_root / "tests")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = build_quality_report(args.corpus, args.tests)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.strict and not report["ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()