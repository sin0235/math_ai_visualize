"""CI gate: offline Scene v3 fidelity corpus (contract + kernel + solver)."""
from __future__ import annotations

from pathlib import Path

from app.math_curriculum.scene_fidelity import (
    assert_thresholds,
    load_corpus,
    load_thresholds,
    run_fidelity,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "scene_v3_fidelity"


def test_fidelity_corpus_file_exists_and_meets_size():
    corpus = load_corpus(FIXTURE_DIR / "corpus.jsonl")
    thresholds = load_thresholds(FIXTURE_DIR / "thresholds.json")
    assert len(corpus) >= int(thresholds.get("min_cases") or 30)
    assert any("negative" in (case.get("tags") or []) for case in corpus)
    assert any("solid_geometry" in (case.get("tags") or []) for case in corpus)
    assert any("plane_geometry" in (case.get("tags") or []) for case in corpus)


def test_scene_v3_fidelity_gate_passes_thresholds():
    report = run_fidelity(FIXTURE_DIR / "corpus.jsonl")
    thresholds = load_thresholds(FIXTURE_DIR / "thresholds.json")
    assert_thresholds(report, thresholds)
    # Sanity: report aggregates
    assert report.total == len(load_corpus(FIXTURE_DIR / "corpus.jsonl"))
    assert report.solve_total >= 10
