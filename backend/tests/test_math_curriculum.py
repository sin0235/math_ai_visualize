from pathlib import Path
from typing import get_args

from app.math_curriculum import (
    ALGEBRA_TOPIC_SKILLS,
    CURRICULUM_VERSION,
    SKILLS,
    registry_snapshot,
    skills_for_algebra_problem,
    skills_for_function_problem,
    skills_for_grade,
    skills_for_legacy_intent,
)
from app.math_curriculum.coverage import build_coverage_report
from app.math_curriculum.quality import build_quality_report
from app.schemas.algebra import AlgebraTopic


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_curriculum_registry_covers_all_grades_and_validates_references():
    assert CURRICULUM_VERSION == "vn-k12-math-v1"
    assert set(grade for skill in SKILLS.values() for grade in skill.grades) == set(range(6, 13))
    assert all(skills_for_grade(grade) for grade in range(6, 13))
    assert len(SKILLS) == len(set(SKILLS))

    for skill in SKILLS.values():
        assert skill.skill_id.startswith(f"{skill.strand.value}.") or skill.skill_id.startswith(("combinatorics.",))
        assert skill.problem_forms
        assert set(skill.prerequisites) <= set(SKILLS)
        if skill.status in {"supported", "partial"}:
            assert skill.current_engines


def test_all_current_algebra_topics_map_to_curriculum_skills():
    current_topics = set(get_args(AlgebraTopic)) - {"auto"}

    assert current_topics == set(ALGEBRA_TOPIC_SKILLS)
    assert all(set(skill_ids) <= set(SKILLS) for skill_ids in ALGEBRA_TOPIC_SKILLS.values())
    assert skills_for_legacy_intent("algebra", "calculus_limit", "limit") == ("calculus.limit_continuity",)
    assert skills_for_legacy_intent("geometry_solve", "solid_geometry", "volume") == ("geometry.solid_metric",)
    assert skills_for_legacy_intent("render", "function_graph", "render_scene") == ("function.analysis",)
    assert skills_for_legacy_intent("ocr", "equation", "solve") == ALGEBRA_TOPIC_SKILLS["equation"]


def test_registry_snapshot_is_machine_readable_and_status_explicit():
    snapshot = registry_snapshot()

    assert snapshot["version"] == CURRICULUM_VERSION
    assert snapshot["grades"] == list(range(6, 13))
    assert sum(snapshot["status_counts"].values()) == len(SKILLS)
    assert {row["status"] for row in snapshot["skills"]} <= {"supported", "partial", "planned", "unsupported"}


def test_coverage_report_uses_corpus_and_test_evidence():
    report = build_coverage_report(
        BACKEND_ROOT / "tests/nlp/corpus/v1.jsonl",
        BACKEND_ROOT / "tests",
    )
    rows = {row["skill_id"]: row for row in report["skills"]}

    assert report["curriculum_version"] == CURRICULUM_VERSION
    assert report["corpus_case_count"] >= 42
    assert report["test_file_count"] >= 80
    assert rows["algebra.trigonometry"]["test_case_count"] > 0
    assert rows["algebra.trigonometry"]["corpus_case_count"] == 1
    assert rows["algebra.trigonometry"]["evidence"] == "corpus_and_tests"
    assert rows["number.divisibility"]["evidence"] == "corpus_and_tests"
    assert rows["number.divisibility"]["corpus_case_count"] == 3
    assert "test_algebra_lower_secondary.py" in rows["number.divisibility"]["test_sources"]
    assert rows["number.ratio_percent"]["evidence"] == "corpus_and_tests"
    assert rows["number.ratio_percent"]["corpus_case_count"] == 4
    assert rows["algebra.expression_transform"]["corpus_case_count"] == 3
    assert rows["algebra.expression_transform"]["evidence"] == "corpus_and_tests"
    assert rows["algebra.polynomial_operations"]["corpus_case_count"] == 2
    assert rows["algebra.polynomial_operations"]["evidence"] == "corpus_and_tests"
    assert rows["algebra.absolute_radical"]["corpus_case_count"] == 2
    assert rows["algebra.absolute_radical"]["evidence"] == "corpus_and_tests"
    assert rows["geometry.quadrilateral"]["evidence"] == "corpus_and_tests"
    assert rows["geometry.circle_basic"]["evidence"] == "corpus_and_tests"
    assert rows["algebra.exponential_logarithm"]["evidence"] == "corpus_and_tests"
    assert rows["algebra.sequence"]["evidence"] == "corpus_and_tests"
    assert rows["algebra.nonlinear_system"]["evidence"] == "corpus_and_tests"
    assert rows["function.linear_quadratic"]["evidence"] == "corpus_and_tests"
    assert rows["geometry.coordinate_2d"]["evidence"] == "corpus_and_tests"
    assert rows["geometry.coordinate_3d"]["evidence"] == "corpus_and_tests"
    assert rows["combinatorics.counting"]["evidence"] == "corpus_and_tests"
    assert rows["probability.classical"]["evidence"] == "corpus_and_tests"
    assert rows["probability.rules"]["evidence"] == "corpus_and_tests"
    assert rows["statistics.descriptive_raw"]["evidence"] == "corpus_and_tests"
    assert rows["statistics.grouped_data"]["evidence"] == "corpus_and_tests"
    assert rows["calculus.integral"]["evidence"] == "corpus_and_tests"
    assert rows["number.rational_arithmetic"]["evidence"] == "corpus_and_tests"
    assert rows["algebra.linear_inequality"]["evidence"] == "corpus_and_tests"
    assert rows["algebra.complex_numbers"]["evidence"] == "corpus_and_tests"
    assert rows["geometry.basic_measurement"]["evidence"] == "corpus_and_tests"
    assert rows["geometry.basic_measurement"]["corpus_case_count"] == 2
    assert "test_geometry_lower_secondary.py" in rows["geometry.basic_measurement"]["test_sources"]
    assert rows["geometry.solid_metric"]["test_case_count"] > 0
    assert rows["statistics.grouped_data"]["status"] == "partial"
    assert report["unmapped_intents"]


def test_quality_dashboard_closes_static_and_mutation_gates():
    report = build_quality_report(
        BACKEND_ROOT / "tests/nlp/corpus/v1.jsonl",
        BACKEND_ROOT / "tests",
    )

    assert report["ready"] is True
    assert report["public_blockers"] == []
    assert report["mutation"]["catch_rate"] == 1.0
    assert report["coverage"]["evidence_counts"] == {"corpus_and_tests": len(SKILLS)}
    assert report["rollout_stage_counts"]["public"] > 0
    assert report["rollout_stage_counts"]["internal_beta"] > 0


def test_upper_secondary_resolvers_do_not_overclaim_neighboring_skills():
    assert skills_for_algebra_problem("equation", "solve_equation", "2*x+3=7") == (
        "algebra.linear_equation",
    )
    assert skills_for_algebra_problem("equation", "solve_equation", "x^2-5*x+6=0") == (
        "algebra.quadratic_equation",
    )
    assert skills_for_algebra_problem("equation", "solve_equation", "(x^2-1)/(x-1)=0") == (
        "algebra.polynomial_rational_equation",
    )
    assert skills_for_algebra_problem("system", "solve_system", "x+y=3;x-y=1") == (
        "algebra.linear_system",
    )
    assert skills_for_algebra_problem("system", "solve_system", "x^2+y^2=5;x-y=1") == (
        "algebra.nonlinear_system",
    )
    assert skills_for_function_problem("x^2-4*x+3") == ("function.linear_quadratic",)
    assert skills_for_function_problem("x^3-3*x+1") == ("function.analysis",)