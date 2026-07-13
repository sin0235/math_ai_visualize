from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.math_curriculum.registry import (
    CURRICULUM_VERSION,
    SKILLS,
    skills_for_algebra_problem,
    skills_for_function_problem,
    skills_for_geometry_problem,
    skills_for_legacy_intent,
)

_TEST_FILE_HINTS = {
    "equation": ("algebra.linear_equation", "algebra.quadratic_equation", "algebra.polynomial_rational_equation"),
    "inequality": ("algebra.linear_inequality", "algebra.absolute_radical"),
    "system": ("algebra.linear_system", "algebra.nonlinear_system"),
    "exp_log": ("algebra.exponential_logarithm",),
    "trig": ("algebra.trigonometry",),
    "sequence": ("algebra.sequence",),
    "combinatorics": ("combinatorics.counting", "probability.classical", "probability.rules"),
    "statistics": ("statistics.descriptive_raw", "statistics.grouped_data"),
    "parameter": ("algebra.parameter",),
    "calculus": ("calculus.derivative", "calculus.limit_continuity", "calculus.integral"),
    "complex": ("algebra.complex_numbers",),
    "algebra_lower_secondary": (
        "number.integer_arithmetic",
        "number.rational_arithmetic",
        "number.divisibility",
        "number.ratio_percent",
        "algebra.expression_transform",
        "algebra.polynomial_operations",
        "algebra.linear_equation",
        "algebra.linear_inequality",
        "algebra.linear_system",
        "algebra.absolute_radical",
    ),
    "function_analyzer": ("function.linear_quadratic", "function.analysis"),
    "geometry_engine": ("geometry.basic_measurement", "geometry.coordinate_2d", "geometry.coordinate_3d", "geometry.solid_metric"),
    "geometry_lower_secondary": ("geometry.basic_measurement", "geometry.triangle_congruence", "geometry.similarity_pythagoras", "geometry.quadrilateral", "geometry.circle_basic"),
    "geometry_kernel": ("geometry.circle_basic", "geometry.solid_relations", "geometry.coordinate_3d"),
    "geometry_facts": ("geometry.triangle_congruence", "geometry.similarity_pythagoras", "geometry.solid_relations"),
    "geometry_reasoning": ("geometry.triangle_congruence", "geometry.similarity_pythagoras", "geometry.solid_relations"),
    "geometry_solver": ("geometry.solid_metric", "geometry.coordinate_3d"),
}


def build_coverage_report(corpus_path: Path, tests_dir: Path) -> dict[str, Any]:
    corpus_cases = _load_corpus(corpus_path)
    corpus_counts: Counter[str] = Counter()
    unmapped_intents: Counter[str] = Counter()
    for case in corpus_cases:
        expected = case.get("expected") or {}
        target = str(case.get("target") or "")
        topic = str(expected.get("topic") or "")
        task = str(expected.get("task") or "")
        canonical = str(expected.get("canonical") or "")
        if target == "algebra":
            skill_ids = skills_for_algebra_problem(topic, task, canonical)
        elif target == "analyzer":
            skill_ids = skills_for_function_problem(canonical, task)
        elif target == "geometry_solve":
            skill_ids = skills_for_geometry_problem(topic, task)
        else:
            skill_ids = skills_for_legacy_intent(target, topic, task)
        if not skill_ids:
            unmapped_intents[f"{target}:{topic}:{task}"] += 1
        for skill_id in skill_ids:
            corpus_counts[skill_id] += 1

    test_files = sorted(tests_dir.glob("test_*.py"))
    test_counts: Counter[str] = Counter()
    test_sources: dict[str, list[str]] = defaultdict(list)
    for path in test_files:
        name = path.stem.removeprefix("test_")
        matched_skills = {
            skill_id
            for hint, skill_ids in _TEST_FILE_HINTS.items()
            if hint in name
            for skill_id in skill_ids
        }
        test_count = _count_tests(path)
        for skill_id in matched_skills:
            test_counts[skill_id] += test_count
            test_sources[skill_id].append(path.name)

    skill_rows = []
    for skill in SKILLS.values():
        corpus_case_count = corpus_counts[skill.skill_id]
        test_case_count = test_counts[skill.skill_id]
        evidence = _evidence_level(corpus_case_count, test_case_count)
        skill_rows.append({
            "skill_id": skill.skill_id,
            "grades": list(skill.grades),
            "strand": skill.strand.value,
            "status": skill.status,
            "current_engines": list(skill.current_engines),
            "corpus_case_count": corpus_case_count,
            "test_case_count": test_case_count,
            "test_sources": sorted(test_sources.get(skill.skill_id, [])),
            "evidence": evidence,
        })

    evidence_counts = Counter(str(row["evidence"]) for row in skill_rows)
    status_counts = Counter(skill.status for skill in SKILLS.values())
    return {
        "curriculum_version": CURRICULUM_VERSION,
        "corpus": corpus_path.name,
        "corpus_case_count": len(corpus_cases),
        "test_file_count": len(test_files),
        "status_counts": dict(sorted(status_counts.items())),
        "evidence_counts": dict(sorted(evidence_counts.items())),
        "unmapped_intents": dict(sorted(unmapped_intents.items())),
        "skills": skill_rows,
    }


def _load_corpus(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _count_tests(path: Path) -> int:
    return sum(
        line.lstrip().startswith(("def test_", "async def test_"))
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def _evidence_level(corpus_count: int, test_count: int) -> str:
    if corpus_count > 0 and test_count > 0:
        return "corpus_and_tests"
    if test_count > 0:
        return "tests_only"
    if corpus_count > 0:
        return "corpus_only"
    return "none"


def main() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Báo cáo baseline độ phủ curriculum theo corpus và test hiện có.")
    parser.add_argument("--corpus", type=Path, default=backend_root.parent / "data/nlp/corpus/v2.jsonl")
    parser.add_argument("--tests", type=Path, default=backend_root / "tests")
    args = parser.parse_args()
    print(json.dumps(build_coverage_report(args.corpus, args.tests), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()