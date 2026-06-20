from __future__ import annotations

from typing import Any

from app.schemas.advisory import AdvisoryFactor, QualityRiskAdvisory
from app.schemas.scene import CasIssueResponse, MathScene, RenderPayload
from app.services.problem_classifier import classify_render_problem, classify_solve_question


_WARNING_PATTERNS = (
    ("mock_fallback", "risk", "Có fallback/mock trong pipeline; kết quả chỉ nên dùng để tham khảo.", 25, ("mock", "fallback")),
    ("validator_warning", "warning", "Validator đã cảnh báo hoặc sửa dữ liệu scene.", 15, ("[validator]", "validator")),
    ("cas_warning", "risk", "Scene có cảnh báo CAS ảnh hưởng đến độ tin cậy hình học.", 15, ("[cas]", "cảnh báo cas", "canh bao cas")),
    ("ai_provider_warning", "warning", "Provider AI có cảnh báo hoặc fallback trong quá trình xử lý.", 10, ("ai fallback", "không gọi được", "khong goi duoc")),
    ("dimension_renderer_warning", "risk", "Có cảnh báo liên quan đến renderer hoặc số chiều của scene.", 20, ("dimension", "renderer", "2d", "3d")),
)
_SOLVE_ISSUE_MARKERS = (
    "không đủ dữ kiện",
    "khong du du kien",
    "không nhận diện",
    "khong nhan dien",
    "cần chỉ rõ",
    "can chi ro",
    "không có trong scene",
    "khong co trong scene",
    "không dùng tọa độ minh họa",
    "khong dung toa do minh hoa",
)


def build_render_advisory(
    problem_text: str,
    grade: int | None,
    scene: MathScene,
    warnings: list[str],
    cas_issues: list[CasIssueResponse],
    payload: RenderPayload | None = None,
) -> QualityRiskAdvisory:
    classification = classify_render_problem(problem_text, grade, scene)
    factors: list[AdvisoryFactor] = []

    if scene.topic == "unknown":
        factors.append(_factor("unknown_topic", "risk", "Chưa nhận diện được dạng toán từ scene.", 25))
    if not scene.objects:
        factors.append(_factor("empty_scene", "critical", "Scene không có object hình học để render hoặc giải.", 35))
    if not scene.relations and scene.topic in {"solid_geometry", "coordinate_3d"} and len(scene.objects) >= 4:
        factors.append(_factor("sparse_relations", "warning", "Scene hình học có ít quan hệ, lời giải có thể thiếu căn cứ từ đề.", 8))

    factors.extend(_warning_factors(warnings))
    factors.extend(_cas_factors(cas_issues))
    factors.extend(_payload_warning_factors(payload))

    return _build_advisory(classification, factors, _render_recommendations(factors))


def build_scene_advisory(
    scene: MathScene,
    warnings: list[str],
    payload: RenderPayload | None = None,
) -> QualityRiskAdvisory:
    return build_render_advisory(scene.problem_text, scene.grade, scene, warnings, scene.cas_issues, payload)


def build_solve_advisory(question: str, scene: dict[str, Any], deterministic_result: Any) -> QualityRiskAdvisory:
    classification = classify_solve_question(question, scene, deterministic_result)
    factors: list[AdvisoryFactor] = []
    answer = str(getattr(deterministic_result, "answer", "") or "")
    steps = list(getattr(deterministic_result, "steps", []) or [])
    warnings = list(getattr(deterministic_result, "warnings", []) or [])
    data_issues = list(getattr(deterministic_result, "data_issues", []) or [])
    confidence = str(getattr(deterministic_result, "confidence", "") or "")

    if answer in {"Không xác định", "Không đủ dữ kiện"}:
        factors.append(_factor("solver_unsupported", "critical", "Solver hiện chưa đủ dữ kiện hoặc chưa nhận diện được câu hỏi.", 40))
    if not steps:
        factors.append(_factor("solver_no_steps", "risk", "Solver không tạo được các bước giải deterministic.", 25))
    if confidence == "insufficient":
        factors.append(_factor("solver_insufficient", "critical", "Độ tin cậy solver là insufficient.", 30))
    elif confidence == "partial":
        factors.append(_factor("solver_partial", "warning", "Độ tin cậy solver là partial do có cảnh báo dữ liệu.", 15))

    for warning in warnings:
        lower = warning.lower()
        if any(marker in lower for marker in _SOLVE_ISSUE_MARKERS):
            factors.append(_factor("solve_warning", "risk", warning, 18))
    for issue in data_issues:
        factors.append(_factor("solve_data_issue", "risk", issue, 18))

    if classification.supported_by_current_solver is False:
        factors.append(_factor("classification_unsupported", "risk", "Classifier nhận thấy dạng câu hỏi chưa được solver hiện tại hỗ trợ chắc chắn.", 15))

    return _build_advisory(classification, factors, _solve_recommendations(factors))


def _warning_factors(warnings: list[str]) -> list[AdvisoryFactor]:
    factors: list[AdvisoryFactor] = []
    seen_codes: set[str] = set()
    for warning in warnings:
        lower = warning.lower()
        for code, severity, message, weight, markers in _WARNING_PATTERNS:
            if code in seen_codes:
                continue
            if any(marker in lower for marker in markers):
                factors.append(_factor(code, severity, message, weight))
                seen_codes.add(code)
    return factors


def _cas_factors(cas_issues: list[CasIssueResponse]) -> list[AdvisoryFactor]:
    unresolved = 0
    auto_fixed = 0
    for issue in cas_issues:
        if issue.auto_fixed:
            auto_fixed += 1
        else:
            unresolved += 1
    factors: list[AdvisoryFactor] = []
    if unresolved:
        factors.append(_factor("cas_unresolved", "risk", f"Còn {unresolved} cảnh báo CAS chưa tự sửa.", min(45, unresolved * 15)))
    if auto_fixed:
        factors.append(_factor("cas_auto_fixed", "warning", f"CAS đã tự sửa {auto_fixed} quan hệ; nên kiểm tra lại dữ kiện hình.", min(20, auto_fixed * 5)))
    return factors


def _payload_warning_factors(payload: RenderPayload | None) -> list[AdvisoryFactor]:
    if payload is None or not payload.three_scene:
        return []
    computed = payload.three_scene.get("computed") if isinstance(payload.three_scene, dict) else None
    if not isinstance(computed, dict):
        return []
    warnings = [warning for warning in computed.get("warnings", []) if isinstance(warning, str)]
    if not warnings:
        return []
    return [_factor("computed_warnings", "warning", f"Renderer sinh {len(warnings)} cảnh báo computed geometry.", min(20, 10 + len(warnings) * 2))]


def _build_advisory(classification, factors: list[AdvisoryFactor], recommendations: list[str]) -> QualityRiskAdvisory:
    risk_score = _clamp_int(sum(max(0.0, factor.weight) for factor in factors))
    quality_score = _clamp_int(100 - risk_score)
    return QualityRiskAdvisory(
        classification=classification,
        quality_score=quality_score,
        risk_score=risk_score,
        risk_level=_risk_level(risk_score),
        factors=_dedupe_factors(factors),
        recommendations=_dedupe_text(recommendations),
    )


def _render_recommendations(factors: list[AdvisoryFactor]) -> list[str]:
    codes = {factor.code for factor in factors}
    recommendations: list[str] = []
    if "unknown_topic" in codes:
        recommendations.append("Viết đề cụ thể hơn hoặc bổ sung loại hình/toạ độ để hệ thống nhận diện dạng toán.")
    if "cas_unresolved" in codes:
        recommendations.append("Kiểm tra lại các quan hệ hình học đang bị CAS cảnh báo trước khi dùng kết quả giải.")
    if "empty_scene" in codes:
        recommendations.append("Bổ sung dữ kiện điểm, đoạn hoặc mặt phẳng để tạo scene có thể render.")
    return recommendations


def _solve_recommendations(factors: list[AdvisoryFactor]) -> list[str]:
    codes = {factor.code for factor in factors}
    recommendations: list[str] = []
    if {"solver_unsupported", "classification_unsupported"}.intersection(codes):
        recommendations.append("Hỏi cụ thể hơn, ví dụ d(A,B), d(A,(BCD)), góc giữa AB và CD, S(ABC) hoặc V(S.ABCD).")
    if "solve_data_issue" in codes or "solve_warning" in codes:
        recommendations.append("Kiểm tra lại scene và các dữ kiện đã cho trước khi dùng lời giải cuối cùng.")
    return recommendations


def _factor(code: str, severity: str, message: str, weight: float) -> AdvisoryFactor:
    return AdvisoryFactor(code=code, severity=severity, message=message, weight=weight)


def _risk_level(score: int) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def _clamp_int(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _dedupe_factors(factors: list[AdvisoryFactor]) -> list[AdvisoryFactor]:
    result: list[AdvisoryFactor] = []
    seen: set[tuple[str, str]] = set()
    for factor in factors:
        key = (factor.code, factor.message)
        if key in seen:
            continue
        seen.add(key)
        result.append(factor)
    return result


def _dedupe_text(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
