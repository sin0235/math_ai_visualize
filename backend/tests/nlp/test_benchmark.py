from __future__ import annotations

import json
from pathlib import Path

from tests.nlp.benchmark import CORPUS_PATH, evaluate, load_cases, pipeline_predict

THRESHOLDS_PATH = Path(__file__).with_name("thresholds.json")
PIPELINE_THRESHOLDS_PATH = Path(__file__).with_name("pipeline-thresholds.json")
PIPELINE_BASELINE_PATH = Path(__file__).with_name("pipeline-baseline-v1.json")


def test_corpus_schema_and_slice_coverage():
    cases = load_cases(CORPUS_PATH)

    assert len(cases) >= 120
    geometry_cases = [case for case in cases if case["target"] == "geometry_solve"]
    assert len(geometry_cases) >= 100
    assert sum("paraphrase" in case["tags"] for case in geometry_cases) >= 80
    assert {case["target"] for case in cases} == {
        "algebra",
        "render",
        "geometry_solve",
        "analyzer",
        "ocr",
    }
    assert {tag for case in cases for tag in case["tags"]} >= {
        "natural_vi",
        "no_diacritics",
        "ocr_noise",
        "mixed_notation",
        "missing_data",
        "unsupported",
        "adversarial",
    }


def test_geometry_metrics_are_reported_per_subtype():
    report = evaluate(load_cases(CORPUS_PATH), predictor=pipeline_predict)

    assert {"distance", "angle", "proof", "volume"} <= set(report["geometry_subtypes"])
    for metrics in report["geometry_subtypes"].values():
        assert "goal_exact_match" in metrics
        assert "entity_f1" in metrics


def test_legacy_nlp_metrics_do_not_regress_below_versioned_thresholds():
    _assert_thresholds(evaluate(load_cases(CORPUS_PATH, expand_paraphrases=False)), THRESHOLDS_PATH)


def test_pipeline_nlp_metrics_do_not_regress_below_measured_thresholds():
    report = evaluate(load_cases(CORPUS_PATH), predictor=pipeline_predict)

    _assert_thresholds(report, PIPELINE_THRESHOLDS_PATH)
    baseline = json.loads(PIPELINE_BASELINE_PATH.read_text(encoding="utf-8"))
    assert report["schema_version"] == baseline["schema_version"]
    assert report["case_count"] >= baseline["case_count"]


def _assert_thresholds(report: dict, thresholds_path: Path):
    thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))

    for scope, expected_metrics in thresholds.items():
        if scope == "overall":
            _assert_metric_thresholds(report["overall"], expected_metrics, scope)
            continue
        if scope == "geometry_subtypes":
            for subtype, subtype_thresholds in expected_metrics.items():
                _assert_metric_thresholds(
                    report["geometry_subtypes"][subtype],
                    subtype_thresholds,
                    f"geometry_subtypes.{subtype}",
                )
            continue
        _assert_metric_thresholds(report["targets"][scope], expected_metrics, scope)


def _assert_metric_thresholds(actual_metrics: dict, expected_metrics: dict, scope: str):
    for metric, minimum in expected_metrics.get("minimum", {}).items():
        assert actual_metrics[metric] >= minimum, f"{scope}.{metric} giảm dưới {minimum}"
    for metric, maximum in expected_metrics.get("maximum", {}).items():
        assert actual_metrics[metric] <= maximum, f"{scope}.{metric} vượt {maximum}"