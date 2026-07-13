"""Offline Scene v3 fidelity eval (contract + kernel + optional solver).

Golden fixtures ship as MathSceneV3 JSON (no live LLM). CI fails when rates
drop below thresholds in tests/fixtures/scene_v3_fidelity/thresholds.json.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.schemas.scene_v3 import MathSceneV3
from app.services.downstream_scene_v3 import scene_v3_to_solver_input
from app.services.scene_pipeline_v3 import run_scene_pipeline_v3
from app.services.solver_service import solve

DEFAULT_CORPUS = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "scene_v3_fidelity"
    / "corpus.jsonl"
)
DEFAULT_THRESHOLDS = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "scene_v3_fidelity"
    / "thresholds.json"
)


@dataclass
class CaseResult:
    case_id: str
    tags: list[str]
    ok: bool
    pipeline_ok: bool
    can_project_ok: bool
    solve_ok: bool | None
    issues: list[str] = field(default_factory=list)
    pipeline_status: str | None = None
    answer: str | None = None


@dataclass
class FidelityReport:
    total: int
    pipeline_pass: int
    can_project_match: int
    solve_total: int
    solve_pass: int
    unexpected_issues: int
    negative_cases: int
    positive_cases: int
    results: list[CaseResult]

    @property
    def pipeline_pass_rate(self) -> float:
        return self.pipeline_pass / self.total if self.total else 0.0

    @property
    def can_project_match_rate(self) -> float:
        return self.can_project_match / self.total if self.total else 0.0

    @property
    def solve_accuracy(self) -> float:
        return self.solve_pass / self.solve_total if self.solve_total else 1.0

    @property
    def unexpected_issue_rate(self) -> float:
        return self.unexpected_issues / self.total if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "pipeline_pass": self.pipeline_pass,
            "pipeline_pass_rate": round(self.pipeline_pass_rate, 4),
            "can_project_match": self.can_project_match,
            "can_project_match_rate": round(self.can_project_match_rate, 4),
            "solve_total": self.solve_total,
            "solve_pass": self.solve_pass,
            "solve_accuracy": round(self.solve_accuracy, 4),
            "unexpected_issues": self.unexpected_issues,
            "unexpected_issue_rate": round(self.unexpected_issue_rate, 4),
            "negative_cases": self.negative_cases,
            "positive_cases": self.positive_cases,
            "failures": [
                {
                    "case_id": item.case_id,
                    "issues": item.issues,
                    "pipeline_status": item.pipeline_status,
                    "answer": item.answer,
                }
                for item in self.results
                if not item.ok
            ],
        }


def load_corpus(path: Path | None = None) -> list[dict[str, Any]]:
    corpus_path = path or DEFAULT_CORPUS
    cases: list[dict[str, Any]] = []
    with corpus_path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                cases.append(json.loads(text))
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSONL at {corpus_path}:{line_no}: {error}") from error
    return cases


def load_thresholds(path: Path | None = None) -> dict[str, Any]:
    threshold_path = path or DEFAULT_THRESHOLDS
    return json.loads(threshold_path.read_text(encoding="utf-8"))


def evaluate_case(case: dict[str, Any]) -> CaseResult:
    case_id = str(case.get("case_id") or "unknown")
    tags = [str(tag) for tag in case.get("tags") or []]
    expect = case.get("expect") if isinstance(case.get("expect"), dict) else {}
    issues: list[str] = []

    try:
        scene = MathSceneV3.model_validate(case["scene"])
    except Exception as error:  # noqa: BLE001 — fidelity report collects failures
        return CaseResult(
            case_id=case_id,
            tags=tags,
            ok=False,
            pipeline_ok=False,
            can_project_ok=False,
            solve_ok=None,
            issues=[f"scene_invalid: {error}"],
        )

    pipeline = run_scene_pipeline_v3(scene)
    status_ok = pipeline.status in set(expect.get("pipeline_status_in") or [pipeline.status])
    if not status_ok:
        issues.append(f"pipeline_status={pipeline.status} not in {expect.get('pipeline_status_in')}")

    expected_project = expect.get("can_project")
    project_ok = expected_project is None or bool(pipeline.can_project) is bool(expected_project)
    if not project_ok:
        issues.append(f"can_project={pipeline.can_project} expected={expected_project}")

    issue_codes = {item.code for item in pipeline.issues}
    if expect.get("require_no_constraint_failed") and "CONSTRAINT_FAILED" in issue_codes:
        issues.append("unexpected CONSTRAINT_FAILED")
    if expect.get("require_constraint_failed") and "CONSTRAINT_FAILED" not in issue_codes:
        # Some failures surface before verify (contract); accept listed codes if provided.
        required_any = set(expect.get("require_issue_codes_any") or [])
        if not (required_any & issue_codes):
            issues.append(f"expected CONSTRAINT_FAILED or {sorted(required_any)}, got {sorted(issue_codes)}")
    required_any = set(expect.get("require_issue_codes_any") or [])
    if required_any and not (required_any & issue_codes):
        issues.append(f"missing issue codes {sorted(required_any)}, got {sorted(issue_codes)}")

    solve_ok: bool | None = None
    answer: str | None = None
    solve_spec = expect.get("solve")
    if isinstance(solve_spec, dict):
        try:
            solver_input = scene_v3_to_solver_input(pipeline.scene, pipeline.verification)
            result = solve(
                solver_input,
                str(solve_spec.get("question") or ""),
                str(solve_spec.get("geometry_method") or "oxyz"),
            )
            answer = result.answer
            contains = [str(item) for item in solve_spec.get("answer_contains") or []]
            confidences = set(solve_spec.get("confidence_in") or [])
            text_ok = all(token in result.answer for token in contains) if contains else True
            conf_ok = (result.confidence in confidences) if confidences else True
            solve_ok = text_ok and conf_ok
            if not text_ok:
                issues.append(f"answer={result.answer!r} missing {contains}")
            if not conf_ok:
                issues.append(f"confidence={result.confidence} not in {sorted(confidences)}")
        except Exception as error:  # noqa: BLE001
            solve_ok = False
            issues.append(f"solve_error: {error}")

    ok = not issues
    return CaseResult(
        case_id=case_id,
        tags=tags,
        ok=ok,
        pipeline_ok=status_ok and project_ok and not any(
            item.startswith("unexpected") or item.startswith("expected CONSTRAINT") or item.startswith("missing issue")
            for item in issues
        ),
        can_project_ok=project_ok,
        solve_ok=solve_ok,
        issues=issues,
        pipeline_status=pipeline.status,
        answer=answer,
    )


def run_fidelity(
    corpus_path: Path | None = None,
    *,
    limit: int | None = None,
) -> FidelityReport:
    cases = load_corpus(corpus_path)
    if limit is not None:
        cases = cases[:limit]
    results = [evaluate_case(case) for case in cases]

    pipeline_pass = sum(1 for item in results if item.pipeline_ok and item.can_project_ok and not any(
        msg.startswith("scene_invalid") for msg in item.issues
    ))
    # pipeline_ok already combines status+project for most; count status+project match separately
    pipeline_pass = sum(
        1
        for item in results
        if item.pipeline_status is not None
        and not any(msg.startswith("pipeline_status=") or msg.startswith("scene_invalid") for msg in item.issues)
    )
    can_project_match = sum(
        1
        for item in results
        if not any(msg.startswith("can_project=") for msg in item.issues)
    )
    solve_items = [item for item in results if item.solve_ok is not None]
    solve_pass = sum(1 for item in solve_items if item.solve_ok)
    unexpected_issues = sum(
        1
        for item in results
        if any(msg.startswith("unexpected") for msg in item.issues)
    )
    negative_cases = sum(1 for item in results if "negative" in item.tags)
    positive_cases = len(results) - negative_cases

    # Recompute pipeline_pass more accurately: no pipeline_status / can_project / contract issues
    def _pipeline_clean(item: CaseResult) -> bool:
        return not any(
            msg.startswith("pipeline_status=")
            or msg.startswith("can_project=")
            or msg.startswith("expected CONSTRAINT")
            or msg.startswith("missing issue")
            or msg.startswith("scene_invalid")
            for msg in item.issues
        )

    pipeline_pass = sum(1 for item in results if _pipeline_clean(item))

    return FidelityReport(
        total=len(results),
        pipeline_pass=pipeline_pass,
        can_project_match=can_project_match,
        solve_total=len(solve_items),
        solve_pass=solve_pass,
        unexpected_issues=unexpected_issues,
        negative_cases=negative_cases,
        positive_cases=positive_cases,
        results=results,
    )


def assert_thresholds(report: FidelityReport, thresholds: dict[str, Any] | None = None) -> None:
    limits = thresholds or load_thresholds()
    errors: list[str] = []
    min_cases = int(limits.get("min_cases") or 1)
    if report.total < min_cases:
        errors.append(f"total cases {report.total} < min_cases {min_cases}")
    if report.pipeline_pass_rate < float(limits.get("min_pipeline_pass_rate", 1.0)):
        errors.append(
            f"pipeline_pass_rate {report.pipeline_pass_rate:.3f} < "
            f"{limits.get('min_pipeline_pass_rate')}"
        )
    if report.can_project_match_rate < float(limits.get("min_can_project_match_rate", 1.0)):
        errors.append(
            f"can_project_match_rate {report.can_project_match_rate:.3f} < "
            f"{limits.get('min_can_project_match_rate')}"
        )
    if report.solve_accuracy < float(limits.get("min_solve_accuracy", 1.0)):
        errors.append(
            f"solve_accuracy {report.solve_accuracy:.3f} < {limits.get('min_solve_accuracy')}"
        )
    if report.unexpected_issue_rate > float(limits.get("max_unexpected_issue_rate", 0.0)):
        errors.append(
            f"unexpected_issue_rate {report.unexpected_issue_rate:.3f} > "
            f"{limits.get('max_unexpected_issue_rate')}"
        )
    if limits.get("require_positive_and_negative"):
        if report.negative_cases < 1 or report.positive_cases < 1:
            errors.append(
                f"need both positive and negative cases "
                f"(pos={report.positive_cases}, neg={report.negative_cases})"
            )
    if errors:
        failure_preview = report.to_dict().get("failures") or []
        raise AssertionError(
            "Scene v3 fidelity gate failed:\n- "
            + "\n- ".join(errors)
            + f"\nFailures ({len(failure_preview)}): {json.dumps(failure_preview[:8], ensure_ascii=False)}"
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run Scene v3 offline fidelity corpus")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run_fidelity(args.corpus, limit=args.limit)
    payload = report.to_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"cases={payload['total']} pipeline={payload['pipeline_pass_rate']:.1%} "
            f"can_project={payload['can_project_match_rate']:.1%} "
            f"solve={payload['solve_accuracy']:.1%} ({payload['solve_pass']}/{payload['solve_total']}) "
            f"unexpected={payload['unexpected_issue_rate']:.1%}"
        )
        if payload["failures"]:
            print("failures:")
            for item in payload["failures"][:15]:
                print(f"  - {item['case_id']}: {item['issues']}")
    assert_thresholds(report, load_thresholds(args.thresholds))


if __name__ == "__main__":
    main()
