from pathlib import Path
from typing import get_args

from app.math_curriculum import (
    ALGEBRA_TOPIC_SKILLS,
    CURRICULUM_VERSION,
    SKILLS,
    registry_snapshot,
    skills_for_grade,
    skills_for_legacy_intent,
)
from app.math_curriculum.coverage import build_coverage_report
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
    assert rows["algebra.trigonometry"]["corpus_case_count"] == 0
    assert rows["algebra.trigonometry"]["evidence"] == "tests_only"
    assert rows["geometry.solid_metric"]["test_case_count"] > 0
    assert rows["statistics.grouped_data"]["status"] == "planned"
    assert report["unmapped_intents"]