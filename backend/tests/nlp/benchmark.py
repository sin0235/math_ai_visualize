from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from app.schemas.algebra import AlgebraSolveRequest
from app.schemas.nlp import InputEnvelope
from app.services.algebra.interpreter import interpret_algebra_input
from app.services.nlp import interpret_input
from app.services.problem_classifier import classify_render_problem, classify_solve_question

# Repo data/ — corpus product/eval, not pytest fixtures.
_REPO_ROOT = Path(__file__).resolve().parents[3]
NLP_DATA_DIR = _REPO_ROOT / "data" / "nlp"
CORPUS_PATH = NLP_DATA_DIR / "corpus" / "v2.jsonl"
EVAL_DIR = NLP_DATA_DIR / "eval"
ABSTENTION_STATUSES = {"abstained", "needs_confirmation"}


@dataclass(frozen=True)
class Prediction:
    domain: str
    topic: str
    task: str
    canonical: str | None
    entities: tuple[str, ...]
    constraints: tuple[str, ...]
    status: str
    confidence: float

    @property
    def intent(self) -> str:
        return "/".join((self.domain, self.topic, self.task))


def load_cases(path: Path = CORPUS_PATH, *, expand_paraphrases: bool = True) -> list[dict[str, Any]]:
    source_cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    cases: list[dict[str, Any]] = []
    for case in source_cases:
        cases.append(case)
        if not expand_paraphrases:
            continue
        for index, text in enumerate(case["input"].get("paraphrases", []), start=1):
            variant = {
                **case,
                "case_id": f"{case['case_id']}-p{index:02d}",
                "input": {**case["input"], "text": text},
                "tags": [*case["tags"], "paraphrase"],
            }
            variant["input"].pop("paraphrases", None)
            cases.append(variant)
    case_ids = [case["case_id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("case_id trong corpus phải duy nhất")
    return cases


def validate_case(case: dict[str, Any]) -> None:
    required = {"case_id", "target", "input", "expected", "tags"}
    if set(case) != required:
        raise ValueError(f"{case.get('case_id', '<unknown>')}: schema cấp cao không hợp lệ")
    if case["target"] not in {"algebra", "render", "geometry_solve", "analyzer", "ocr"}:
        raise ValueError(f"{case['case_id']}: target không hợp lệ")
    expected = case["expected"]
    expected_required = {"domain", "topic", "task", "canonical", "entities", "constraints", "status"}
    if set(expected) != expected_required:
        raise ValueError(f"{case['case_id']}: expected schema không hợp lệ")
    if expected["status"] not in {"accepted", "needs_confirmation", "abstained", "unsupported"}:
        raise ValueError(f"{case['case_id']}: status không hợp lệ")
    if not isinstance(case["input"].get("text"), str):
        raise ValueError(f"{case['case_id']}: input.text phải là chuỗi")
    if not all(isinstance(value, str) for value in (*expected["entities"], *expected["constraints"], *case["tags"])):
        raise ValueError(f"{case['case_id']}: entities/constraints/tags phải là danh sách chuỗi")


def legacy_predict(case: dict[str, Any]) -> Prediction:
    target = case["target"]
    text = case["input"]["text"]
    if target == "algebra":
        interpretation = interpret_algebra_input(AlgebraSolveRequest(input=text or " ")) if text else None
        if interpretation is None:
            return _empty_prediction("abstained")
        topic = interpretation.topic_hint
        return Prediction(
            domain="algebra" if topic != "auto" else "unknown",
            topic=topic if topic != "auto" else "unknown",
            task=interpretation.expression_action or _algebra_task(topic),
            canonical=interpretation.canonical_input or None,
            entities=tuple(f"variable:{value}" for value in interpretation.variables),
            constraints=(),
            status="accepted",
            confidence=0.75 if topic != "auto" else 0.25,
        )
    if target == "render":
        result = classify_render_problem(text)
        return Prediction(
            domain=result.domain,
            topic=result.topic,
            task=result.task_type or "unknown",
            canonical=None,
            entities=(),
            constraints=(),
            status="accepted" if result.topic != "unknown" else "abstained",
            confidence=result.confidence,
        )
    if target == "geometry_solve":
        scene_topic = case["input"].get("context", {}).get("scene_topic", "unknown")
        result = classify_solve_question(text, {"topic": scene_topic})
        return Prediction(
            domain=result.domain,
            topic=result.topic,
            task=result.task_type or "unknown",
            canonical=None,
            entities=(),
            constraints=(),
            status="accepted" if result.task_type != "unknown" else "abstained",
            confidence=result.confidence,
        )
    if target == "analyzer":
        # Route hiện tại chuyển nguyên chuỗi vào analyzer; không có natural-language interpreter.
        expression_like = bool(re.fullmatch(r"[\d\sA-Za-z_+\-*/^().]+", text)) and not _looks_like_instruction(text)
        return Prediction(
            domain="function" if expression_like else "unknown",
            topic="function_analysis" if expression_like else "unknown",
            task="analyze" if expression_like else "unknown",
            canonical=re.sub(r"\s+", "", text) if expression_like else None,
            entities=("variable:x",) if expression_like and re.search(r"\bx\b", text) else (),
            constraints=(),
            status="accepted" if text else "abstained",
            confidence=0.9 if expression_like else 0.2,
        )
    # OCR hiện chỉ trả merged text/provider/model; chưa có downstream interpretation contract.
    return Prediction(
        domain="unknown",
        topic="unknown",
        task="unknown",
        canonical=None,
        entities=(),
        constraints=(),
        status="accepted" if text else "abstained",
        confidence=0.0,
    )


def pipeline_predict(case: dict[str, Any]) -> Prediction:
    if not case["input"]["text"]:
        return _empty_prediction("abstained")
    response = interpret_input(InputEnvelope(
        text=case["input"]["text"],
        target=case["target"],
        input_mode=case["input"].get("input_mode", "natural"),
        input_format=case["input"].get("input_format", "auto"),
        context=case["input"].get("context", {}),
    ))
    candidate = next(
        (item for item in response.candidates if item.candidate_id == response.selected_candidate_id),
        response.candidates[0] if response.candidates else None,
    )
    if candidate is None:
        return _empty_prediction(response.status.value)
    return Prediction(
        domain=candidate.intent.domain,
        topic=candidate.intent.topic,
        task=candidate.intent.task,
        canonical=candidate.canonical_text,
        entities=tuple(f"{item.kind}:{item.name}" for item in candidate.entities),
        constraints=tuple(
            f"{item.kind}:{','.join(item.arguments)}" if item.arguments else item.kind
            for item in candidate.constraints
        ),
        status=response.status.value,
        confidence=candidate.confidence,
    )


def evaluate(
    cases: Iterable[dict[str, Any]],
    *,
    predictor=legacy_predict,
) -> dict[str, Any]:
    rows = []
    for case in cases:
        validate_case(case)
        prediction = predictor(case)
        expected = case["expected"]
        gold_intent = "/".join((expected["domain"], expected["topic"], expected["task"]))
        rows.append((case, prediction, gold_intent))

    by_target: dict[str, list[tuple[dict[str, Any], Prediction, str]]] = defaultdict(list)
    for row in rows:
        by_target[row[0]["target"]].append(row)
    geometry_rows = [row for row in rows if row[0]["target"] == "geometry_solve"]
    geometry_by_subtype: dict[str, list[tuple[dict[str, Any], Prediction, str]]] = defaultdict(list)
    for row in geometry_rows:
        geometry_by_subtype[row[0]["expected"]["task"]].append(row)
    return {
        "schema_version": 1,
        "corpus": CORPUS_PATH.name,
        "case_count": len(rows),
        "overall": _metrics(rows),
        "targets": {target: _metrics(target_rows) for target, target_rows in sorted(by_target.items())},
        "geometry_subtypes": {
            subtype: _geometry_goal_metrics(subtype_rows)
            for subtype, subtype_rows in sorted(geometry_by_subtype.items())
        },
    }


def _metrics(rows: list[tuple[dict[str, Any], Prediction, str]]) -> dict[str, float | int]:
    if not rows:
        return {"case_count": 0}
    gold_labels = [gold for _case, _prediction, gold in rows]
    predicted_labels = [prediction.intent for _case, prediction, _gold in rows]
    canonical_rows = [row for row in rows if row[0]["expected"]["canonical"] is not None]
    unsupported_rows = [row for row in rows if row[0]["expected"]["status"] == "unsupported"]
    predicted_abstentions = [row for row in rows if row[1].status in ABSTENTION_STATUSES]
    intent_correctness = [float(gold == prediction.intent) for _case, prediction, gold in rows]
    confidences = [prediction.confidence for _case, prediction, _gold in rows]
    return {
        "case_count": len(rows),
        "intent_macro_f1": round(_macro_f1(gold_labels, predicted_labels), 6),
        "canonical_exact_match": round(_canonical_score(canonical_rows, semantic=False), 6),
        "canonical_semantic_match": round(_canonical_score(canonical_rows, semantic=True), 6),
        "entity_f1": round(_set_f1(rows, "entities"), 6),
        "constraint_f1": round(_set_f1(rows, "constraints"), 6),
        "unsupported_recall": round(
            sum(row[1].status == "unsupported" for row in unsupported_rows) / len(unsupported_rows)
            if unsupported_rows else 1.0,
            6,
        ),
        "abstention_precision": round(
            sum(row[0]["expected"]["status"] in ABSTENTION_STATUSES for row in predicted_abstentions)
            / len(predicted_abstentions)
            if predicted_abstentions else 1.0,
            6,
        ),
        "brier_score": round(sum((confidence - correct) ** 2 for confidence, correct in zip(confidences, intent_correctness)) / len(rows), 6),
        "ece_10": round(_ece(confidences, intent_correctness), 6),
    }


def _geometry_goal_metrics(rows: list[tuple[dict[str, Any], Prediction, str]]) -> dict[str, float | int]:
    if not rows:
        return {"case_count": 0, "goal_exact_match": 1.0, "entity_f1": 1.0}
    exact = sum(
        prediction.task == case["expected"]["task"]
        and set(prediction.entities) == set(case["expected"]["entities"])
        and prediction.status == case["expected"]["status"]
        for case, prediction, _gold in rows
    )
    return {
        "case_count": len(rows),
        "goal_exact_match": round(exact / len(rows), 6),
        "entity_f1": round(_set_f1(rows, "entities"), 6),
    }


def _macro_f1(gold: list[str], predicted: list[str]) -> float:
    labels = sorted(set(gold) | set(predicted))
    scores = []
    for label in labels:
        true_positive = sum(g == label and p == label for g, p in zip(gold, predicted))
        false_positive = sum(g != label and p == label for g, p in zip(gold, predicted))
        false_negative = sum(g == label and p != label for g, p in zip(gold, predicted))
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append((2 * true_positive / denominator) if denominator else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def _canonical_score(rows: list[tuple[dict[str, Any], Prediction, str]], *, semantic: bool) -> float:
    if not rows:
        return 1.0
    normalize = _semantic_canonical if semantic else lambda value: value
    return sum(normalize(row[1].canonical) == normalize(row[0]["expected"]["canonical"]) for row in rows) / len(rows)


def _semantic_canonical(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", "", value).replace("**", "^").replace("−", "-")
    return normalized.lower()


def _set_f1(rows: list[tuple[dict[str, Any], Prediction, str]], field: str) -> float:
    true_positive = false_positive = false_negative = 0
    for case, prediction, _gold in rows:
        expected = set(case["expected"][field])
        actual = set(getattr(prediction, field))
        true_positive += len(expected & actual)
        false_positive += len(actual - expected)
        false_negative += len(expected - actual)
    denominator = 2 * true_positive + false_positive + false_negative
    return (2 * true_positive / denominator) if denominator else 1.0


def _ece(confidences: list[float], correctness: list[float], bins: int = 10) -> float:
    total = len(confidences)
    error = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        members = [
            (confidence, correct)
            for confidence, correct in zip(confidences, correctness)
            if lower <= confidence < upper or (index == bins - 1 and math.isclose(confidence, 1.0))
        ]
        if not members:
            continue
        mean_confidence = sum(item[0] for item in members) / len(members)
        mean_accuracy = sum(item[1] for item in members) / len(members)
        error += len(members) / total * abs(mean_confidence - mean_accuracy)
    return error


def _algebra_task(topic: str) -> str:
    return {
        "calculus_derivative": "differentiate",
        "calculus_limit": "limit",
        "calculus_integral": "integrate",
        "parameter": "solve_parameter",
        "combinatorics_probability": "evaluate_probability",
    }.get(topic, "solve" if topic != "auto" else "unknown")


def _looks_like_instruction(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("khảo sát", "khao sat", "tìm ", "tim ", "vẽ ", "ve ", "select ", " hay "))


def _empty_prediction(status: str) -> Prediction:
    return Prediction("unknown", "unknown", "unknown", None, (), (), status, 0.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Đo baseline NLP legacy theo corpus versioned.")
    parser.add_argument("--corpus", type=Path, default=CORPUS_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--predictor", choices=("legacy", "pipeline"), default="legacy")
    args = parser.parse_args()
    predictor = pipeline_predict if args.predictor == "pipeline" else legacy_predict
    report = evaluate(load_cases(args.corpus), predictor=predictor)
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()