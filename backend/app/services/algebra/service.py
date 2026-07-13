from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import replace

import sympy as sp

from app.core.config import Settings, get_settings
from app.schemas.algebra import AlgebraInterval, AlgebraSolveOptions, AlgebraSolveRequest, AlgebraSolveResponse, AlgebraVerificationReport
from app.services.algebra.ai_explainer import explain_algebra_response_with_ai
from app.services.algebra.ai_extraction import extract_algebra_request_with_ai
from app.services.algebra.classifier import classify_algebra_problem
from app.services.algebra.interpreter import interpret_algebra_input
from app.services.algebra.normalizer import normalize_algebra_input
from app.services.algebra.load_gate import AlgebraSlot, algebra_load_gate
from app.services.algebra.parser import AlgebraParseError, ParsedAlgebraProblem, parse_algebra_problem, parse_interval_bound
from app.services.algebra.process_worker import solve_algebra_in_process
from app.services.algebra.solvers.arithmetic_solver import solve_arithmetic
from app.services.algebra.solvers.calculus_solver import solve_calculus
from app.services.algebra.solvers.combinatorics_probability_solver import solve_combinatorics_probability
from app.services.algebra.solvers.complex_solver import solve_complex
from app.services.algebra.solvers.equation_solver import solve_equation
from app.services.algebra.solvers.exp_log_solver import solve_exp_log
from app.services.algebra.solvers.inequality_solver import solve_inequality
from app.services.algebra.solvers.parameter_solver import solve_parameter
from app.services.algebra.solvers.sequence_solver import solve_sequence
from app.services.algebra.solvers.statistics_solver import solve_statistics
from app.services.algebra.solvers.system_solver import solve_system
from app.services.algebra.solvers.trig_solver import solve_trigonometry
from app.services.algebra.solvers.expression_solver import solve_expression
from app.services.math_capabilities import resolve_algebra_capability
from app.services.nlp.grounding import build_algebra_explanation_plan


def solve_algebra(request: AlgebraSolveRequest) -> AlgebraSolveResponse:
    return solve_algebra_deterministic(request)


def _run_deterministic_tracked(request: AlgebraSolveRequest, slot: AlgebraSlot | None) -> AlgebraSolveResponse:
    """In-thread solve; capacity reserved until leave_worker (timeout orphans keep slot)."""
    algebra_load_gate.enter_worker(slot)
    try:
        return solve_algebra_deterministic(request)
    finally:
        algebra_load_gate.leave_worker(slot)


def _run_deterministic_isolated(request: AlgebraSolveRequest, timeout: float, slot: AlgebraSlot | None) -> AlgebraSolveResponse:
    """Process-isolated solve; hard-kill on timeout so capacity frees immediately."""
    algebra_load_gate.enter_worker(slot)
    try:
        return solve_algebra_in_process(request, timeout)
    finally:
        algebra_load_gate.leave_worker(slot)


async def _run_deterministic_with_timeout(
    request: AlgebraSolveRequest,
    timeout: float,
    slot: AlgebraSlot | None,
    *,
    process_isolation: bool = True,
) -> AlgebraSolveResponse:
    if process_isolation:
        # Child process is killable; TimeoutError surfaces from the worker helper.
        return await asyncio.to_thread(_run_deterministic_isolated, request, timeout, slot)
    # Fallback: wait_for does not kill the thread; slot stays reserved until thread ends.
    return await asyncio.wait_for(
        asyncio.to_thread(_run_deterministic_tracked, request, slot),
        timeout=timeout,
    )


async def solve_algebra_with_optional_ai(
    request: AlgebraSolveRequest,
    settings: Settings | None = None,
    load_slot: AlgebraSlot | None = None,
) -> AlgebraSolveResponse:
    settings = settings or get_settings()
    extraction_warnings: list[str] = []
    deterministic_request = request
    isolation = bool(settings.algebra_process_isolation)
    # Single wall-clock budget shared across sequential deterministic attempts.
    total_budget = max(0.5, float(settings.algebra_solve_timeout_seconds))
    deadline = time.perf_counter() + total_budget
    # Never stack a second solve after timeout.

    def _remaining_budget() -> float:
        return max(0.0, deadline - time.perf_counter())

    if request.options.use_ai_extraction:
        # Rule-based first: only call AI when deterministic path fails or is unsupported.
        first_timeout = _remaining_budget()
        if first_timeout < 0.5:
            return _timeout_response(
                request,
                request.input,
                str(request.topic),
                extra_warnings=["Hết ngân sách thời gian trước khi giải deterministic."],
            )
        try:
            rule_based = await _run_deterministic_with_timeout(
                request,
                first_timeout,
                load_slot,
                process_isolation=isolation,
            )
        except (asyncio.TimeoutError, TimeoutError):
            return _timeout_response(
                request,
                request.input,
                str(request.topic),
                extra_warnings=[
                    "Timeout trên lần giải rule-based; không gọi AI và không chạy lại solve."
                    + (" Worker process đã bị terminate." if isolation else " Worker thread có thể còn chạy tới khi xong.")
                ],
            )
        if rule_based.status in {"solved", "partial"}:
            rule_based.warnings = [
                "Đã dùng interpreter rule-based; không cần AI diễn giải cho đề này.",
                *rule_based.warnings,
            ]
            if request.options.ai_explanation:
                rule_based = await explain_algebra_response_with_ai(rule_based, settings)
            return rule_based
        try:
            deterministic_request, extraction_warnings = await extract_algebra_request_with_ai(request.input, request, settings)
            deterministic_request = _preserve_explicit_request_contract(request, deterministic_request)
        except Exception:
            extraction_warnings = ["Không gọi được AI extraction, đang dùng rule-based interpreter."]
            rule_based.warnings = [*extraction_warnings, *rule_based.warnings]
            return rule_based

    second_timeout = _remaining_budget() if request.options.use_ai_extraction else total_budget
    if second_timeout < 0.5:
        return _timeout_response(
            request,
            deterministic_request.input,
            str(deterministic_request.topic),
            extra_warnings=[
                *extraction_warnings,
                "Hết ngân sách thời gian deterministic sau lần giải rule-based / AI extraction; không chạy solve thứ hai.",
            ],
        )
    try:
        response = await _run_deterministic_with_timeout(
            deterministic_request,
            second_timeout,
            load_slot,
            process_isolation=isolation,
        )
    except (asyncio.TimeoutError, TimeoutError):
        return _timeout_response(
            request,
            deterministic_request.input,
            str(deterministic_request.topic),
            extra_warnings=[
                *extraction_warnings,
                "Timeout deterministic solve."
                + (" Worker process đã bị terminate." if isolation else " Worker thread có thể còn chạy tới khi xong."),
            ],
        )
    if deterministic_request.input != request.input:
        response.input = request.input
        response.normalized_input = deterministic_request.input
    if extraction_warnings:
        response.warnings = [*extraction_warnings, *response.warnings]
    if request.options.ai_explanation:
        response = await explain_algebra_response_with_ai(response, settings)
    return response


def _preserve_explicit_request_contract(
    original: AlgebraSolveRequest,
    extracted: AlgebraSolveRequest,
) -> AlgebraSolveRequest:
    protected_fields = {
        **({"topic": original.topic} if original.topic != "auto" else {}),
        **({"expression_action": original.expression_action} if original.expression_action else {}),
        **({"domain": original.domain, "domain_source": original.domain_source} if original.domain_source == "user" else {}),
        **({"variables": original.variables} if original.variables else {}),
        **({"parameters": original.parameters} if original.parameters else {}),
    }
    return extracted.model_copy(update=protected_fields) if protected_fields else extracted


def _timeout_response(
    request: AlgebraSolveRequest,
    normalized_input: str,
    topic: str,
    *,
    extra_warnings: list[str] | None = None,
) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(
        input=request.input,
        normalized_input=normalized_input,
        topic=topic,
        problem_type="timeout",
        status="error",
        answer="Phép giải vượt quá thời gian cho phép. Hãy rút gọn biểu thức hoặc chia nhỏ bài.",
        errors=["ALGEBRA_TIMEOUT: deterministic solve exceeded time limit"],
        warnings=list(extra_warnings or []),
    )


def solve_algebra_deterministic(request: AlgebraSolveRequest) -> AlgebraSolveResponse:
    started = time.perf_counter()
    response, interval_warning, stage_ms = _solve_algebra_core(request)
    options_started = time.perf_counter()
    response = _apply_response_options(response, request.options)
    options_ms = int((time.perf_counter() - options_started) * 1000)
    if interval_warning:
        response.warnings = [interval_warning, *response.warnings]
    response = _annotate_empty_solution_semantics(response)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if not response.request_id:
        response.request_id = f"alg_{uuid.uuid4().hex[:12]}"
    response.timings_ms = {
        **response.timings_ms,
        **stage_ms,
        "options_ms": options_ms,
        "total_ms": elapsed_ms,
        "solve_ms": stage_ms.get("solve_ms", max(0, elapsed_ms - stage_ms.get("interpret_ms", 0) - stage_ms.get("parse_ms", 0))),
    }
    response.grounding = build_algebra_explanation_plan(response)
    return response


def _solve_algebra_core(request: AlgebraSolveRequest) -> tuple[AlgebraSolveResponse, str | None, dict[str, int]]:
    stage_ms: dict[str, int] = {}
    interpret_started = time.perf_counter()
    interpretation = interpret_algebra_input(request)
    stage_ms["interpret_ms"] = int((time.perf_counter() - interpret_started) * 1000)
    requested_topic = _resolve_requested_topic(request.topic, interpretation.topic_hint, interpretation.canonical_input)
    if request.variables:
        variables: list[str] | None = list(request.variables)
    elif interpretation.variables:
        variables = list(interpretation.variables)
    else:
        variables = None
    domain = interpretation.domain if request.domain == "R" and interpretation.domain != "R" else request.domain
    solve_interval, interval_warning = _algebra_interval_to_set(request.interval)

    def _done(response: AlgebraSolveResponse, *, parse_ms: int = 0, solve_ms: int = 0) -> tuple[AlgebraSolveResponse, str | None, dict[str, int]]:
        stage_ms["parse_ms"] = parse_ms
        stage_ms["solve_ms"] = solve_ms
        return response, interval_warning, stage_ms

    def _timed_solve(solver_fn, problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
        started = time.perf_counter()
        result = solver_fn(problem)
        stage_ms["solve_ms"] = int((time.perf_counter() - started) * 1000)
        return result

    if requested_topic != "auto":
        capability = resolve_algebra_capability(
            original=request.input,
            canonical=interpretation.canonical_input,
            topic=requested_topic,
            task=interpretation.expression_action or "solve",
            variables=variables or [],
            parameters=list(request.parameters),
            domain=domain,
        )
        if not capability.accepted:
            return _done(AlgebraSolveResponse(
                input=request.input,
                normalized_input=interpretation.canonical_input,
                input_interpretation=interpretation,
                topic=requested_topic,
                problem_type="capability_unsupported",
                status="unsupported",
                answer=capability.reason or "Dạng bài chưa có capability phù hợp.",
                warnings=interpretation.warnings,
            ))

    if requested_topic == "arithmetic":
        problem = _raw_problem(request, interpretation.canonical_input, variables, domain, requested_topic, solve_interval)
        return _done(
            _with_interpretation(_timed_solve(solve_arithmetic, problem), request.input, interpretation),
            solve_ms=stage_ms.get("solve_ms", 0),
        )
    if requested_topic == "combinatorics_probability":
        problem = _raw_problem(request, interpretation.canonical_input, variables, domain, requested_topic, solve_interval)
        return _done(
            _with_interpretation(_timed_solve(solve_combinatorics_probability, problem), request.input, interpretation),
            solve_ms=stage_ms.get("solve_ms", 0),
        )
    if requested_topic == "statistics":
        problem = _raw_problem(request, interpretation.canonical_input, variables, domain, requested_topic, solve_interval)
        return _done(
            _with_interpretation(_timed_solve(solve_statistics, problem), request.input, interpretation),
            solve_ms=stage_ms.get("solve_ms", 0),
        )
    if requested_topic == "sequence":
        problem = _raw_problem(request, interpretation.canonical_input, variables, domain, requested_topic, solve_interval)
        return _done(
            _with_interpretation(_timed_solve(solve_sequence, problem), request.input, interpretation),
            solve_ms=stage_ms.get("solve_ms", 0),
        )
    if requested_topic == "parameter":
        problem = _raw_problem(request, interpretation.canonical_input, variables, domain, requested_topic, solve_interval)
        return _done(
            _with_interpretation(_timed_solve(solve_parameter, problem), request.input, interpretation),
            solve_ms=stage_ms.get("solve_ms", 0),
        )
    if requested_topic in {"calculus_derivative", "calculus_limit", "calculus_integral"}:
        problem = _raw_problem(request, interpretation.canonical_input, variables, domain, requested_topic, solve_interval)
        return _done(
            _with_interpretation(_timed_solve(solve_calculus, problem), request.input, interpretation),
            solve_ms=stage_ms.get("solve_ms", 0),
        )
    parse_started = time.perf_counter()
    try:
        problem = parse_algebra_problem(
            interpretation.canonical_input,
            topic=requested_topic,
            variables=variables,
            domain=domain,
            expression_action=interpretation.expression_action,
        )
        problem = replace(
            problem,
            solve_interval=solve_interval if solve_interval is not None else problem.solve_interval,
            angle_unit=request.angle_unit or "radian",
        )
    except AlgebraParseError as exc:
        parse_ms = int((time.perf_counter() - parse_started) * 1000)
        return _done(AlgebraSolveResponse(
            input=request.input,
            normalized_input=interpretation.canonical_input,
            input_interpretation=interpretation,
            topic=requested_topic,
            problem_type="parse_error",
            status="error",
            answer="Không thể đọc đề bài đại số này.",
            warnings=interpretation.warnings,
            errors=[str(exc)],
        ), parse_ms=parse_ms)
    parse_ms = int((time.perf_counter() - parse_started) * 1000)
    topic = classify_algebra_problem(problem)
    capability = resolve_algebra_capability(
        original=request.input,
        canonical=problem.normalized_input,
        topic=topic,
        task="solve",
        variables=[str(variable) for variable in problem.variables],
        parameters=list(request.parameters),
        domain=domain,
    )
    if not capability.accepted:
        return _done(_with_interpretation(AlgebraSolveResponse(
            input=request.input,
            normalized_input=problem.normalized_input,
            topic=topic,
            problem_type="capability_unsupported",
            status="unsupported",
            answer=capability.reason or "Dạng bài chưa có capability phù hợp.",
            warnings=interpretation.warnings,
        ), request.input, interpretation), parse_ms=parse_ms)
    solvers = {
        "arithmetic": solve_arithmetic,
        "equation": solve_equation,
        "inequality": solve_inequality,
        "exponential_log": solve_exp_log,
        "trigonometry": solve_trigonometry,
        "expression": solve_expression,
        "complex": solve_complex,
        "system": solve_system,
        "combinatorics_probability": solve_combinatorics_probability,
        "statistics": solve_statistics,
        "sequence": solve_sequence,
        "parameter": solve_parameter,
        "calculus_derivative": solve_calculus,
        "calculus_limit": solve_calculus,
        "calculus_integral": solve_calculus,
    }
    solver = solvers.get(topic)
    if solver is not None:
        return _done(
            _with_interpretation(_timed_solve(solver, problem), request.input, interpretation),
            parse_ms=parse_ms,
            solve_ms=stage_ms.get("solve_ms", 0),
        )
    return _done(_with_interpretation(AlgebraSolveResponse(
        input=request.input,
        normalized_input=problem.normalized_input,
        topic=topic,
        problem_type="unsupported",
        status="unsupported",
        answer="Dạng bài này chưa được hỗ trợ trong phase đầu. Hiện hệ thống ưu tiên phương trình và bất phương trình một biến.",
        warnings=["Các nhóm tham số và các dạng đề tự nhiên dài sẽ được bổ sung ở các phase sau."],
    ), request.input, interpretation), parse_ms=parse_ms)


def _annotate_empty_solution_semantics(response: AlgebraSolveResponse) -> AlgebraSolveResponse:
    """Clarify empty-set answers: partial verify is sample-backed, not full unsat proof."""
    if response.solution_set.kind != "empty":
        return response
    if response.verification.status == "failed":
        response.status = "error"
        response.warnings = [
            "Phát hiện mâu thuẫn khi kiểm chứng vô nghiệm (có điểm thỏa đề).",
            *response.warnings,
        ]
        return response
    if response.verification.status == "partially_verified" and response.status == "solved":
        # Keep status solved for pedagogically clear "vô nghiệm" but warn scope of proof.
        response.warnings = [
            "Kết luận vô nghiệm dựa trên solver + củng cố mẫu; chưa phải chứng minh đại số đầy đủ.",
            *response.warnings,
        ]
    return response


def _apply_response_options(response: AlgebraSolveResponse, options: AlgebraSolveOptions) -> AlgebraSolveResponse:
    if not options.verify:
        prior_verify_status = response.verification.status
        # Solvers may have already set status=error from failed verification; restore
        # a non-error outcome when the caller explicitly skipped verification.
        if response.status == "error" and prior_verify_status == "failed":
            if response.solution_set.kind != "unknown" or response.answer:
                response.status = "partial" if response.solution_set.kind in {"conditions", "unknown"} else "solved"
            response.errors = [
                err for err in response.errors
                if "kiểm chứng" not in err.lower() and "verification" not in err.lower() and "verify" not in err.lower()
            ]
        response.verification = AlgebraVerificationReport(
            status="skipped",
            checks=[],
            method=["skipped_by_option"],
        )
        response.warnings = [*response.warnings, "Đã bỏ qua kiểm chứng (options.verify=false)."]
    if not options.return_steps:
        response.steps = []
        response.milestones = []
    if options.max_solutions > 0 and response.solution_set.values:
        total = len(response.solution_set.values)
        if total > options.max_solutions:
            kept = response.solution_set.values[: options.max_solutions]
            response.solution_set.values = kept
            kept_text = "; ".join(item.text for item in kept)
            kept_latex_parts = [item.latex if item.latex else item.text for item in kept]
            kept_latex = ", ".join(kept_latex_parts)
            response.solution_set.kind = "finite"
            response.solution_set.text = f"Tập nghiệm (cắt {options.max_solutions}/{total}): {{{kept_text}}}"
            # Avoid f-string brace pitfalls: build \left\{ ... \right\} explicitly.
            response.solution_set.latex = (
                "\\left\\{" + kept_latex + "\\right\\}"
                + f" (cắt {options.max_solutions}/{total})"
            )
            response.answer = response.solution_set.text
            response.answer_latex = response.solution_set.latex
            response.warnings = [
                *response.warnings,
                f"Đã cắt danh sách nghiệm còn {options.max_solutions}/{total} (options.max_solutions); answer/latex/values đã đồng bộ.",
            ]
    if not options.prefer_exact and response.solution_set.values:
        for value in response.solution_set.values:
            if not value.approximate:
                try:
                    # Prefer numeric from latex/text without unrestricted user-string eval.
                    raw = (value.latex or value.text or "").replace("^", "**")
                    if raw:
                        from app.services.algebra.parser import parse_algebra_expr
                        value.approximate = str(sp.N(parse_algebra_expr(raw, variable_names=[]), 8))
                except Exception:
                    try:
                        value.approximate = str(sp.N(sp.sympify(value.text), 8)) if value.text else None
                    except Exception:
                        pass
    return response


_CALCULUS_PREFIX_BY_TOPIC = {
    "calculus_derivative": "derivative(",
    "calculus_limit": "limit(",
    "calculus_integral": "integral(",
}
_STRONG_FORMULA_TOPICS = {
    "inequality",
    "exponential_log",
    "trigonometry",
    "system",
    *_CALCULUS_PREFIX_BY_TOPIC.keys(),
}


def _resolve_requested_topic(requested_topic: str, detected_topic: str, canonical_input: str) -> str:
    if requested_topic == "auto":
        return detected_topic
    if detected_topic in {"auto", requested_topic}:
        return requested_topic
    normalized = normalize_algebra_input(canonical_input)
    if requested_topic in _CALCULUS_PREFIX_BY_TOPIC and not normalized.startswith(_CALCULUS_PREFIX_BY_TOPIC[requested_topic]):
        return detected_topic
    if detected_topic in _CALCULUS_PREFIX_BY_TOPIC and normalized.startswith(_CALCULUS_PREFIX_BY_TOPIC[detected_topic]):
        return detected_topic
    if requested_topic in _STRONG_FORMULA_TOPICS and detected_topic in _STRONG_FORMULA_TOPICS:
        return detected_topic
    return requested_topic


def _raw_problem(
    request: AlgebraSolveRequest,
    canonical_input: str,
    variables: list[str] | None,
    domain: str,
    topic: str,
    solve_interval: sp.Set | None = None,
) -> ParsedAlgebraProblem:
    raw_vars = list(variables) if variables else ["x"]
    symbols = [sp.Symbol(name, real=(domain != "C")) for name in raw_vars]
    return ParsedAlgebraProblem(
        raw_input=canonical_input,
        normalized_input=canonical_input.strip().replace("^", "**"),
        topic=topic,
        variable=symbols[0],
        variables=symbols,
        domain=domain,
        solve_interval=solve_interval,
        angle_unit=request.angle_unit or "radian",
    )


def _algebra_interval_to_set(interval: AlgebraInterval | None) -> tuple[sp.Set | None, str | None]:
    if interval is None:
        return None, None
    warning: str | None = None
    if interval.variable and interval.variable not in {"x", ""}:
        # Interval is applied to the primary solve variable; non-x names are advisory only.
        warning = (
            f"Khoảng được áp dụng cho biến giải chính (không lọc riêng '{interval.variable}'); "
            "schema interval.variable hiện chỉ mang tính gợi ý."
        )
    try:
        start = parse_interval_bound(interval.start) if interval.start not in (None, "") else -sp.oo
        end = parse_interval_bound(interval.end) if interval.end not in (None, "") else sp.oo
        return (
            sp.Interval(start, end, left_open=not interval.closed_start, right_open=not interval.closed_end),
            warning,
        )
    except Exception:
        return None, "Khoảng nghiệm không hợp lệ nên đã bỏ qua; giải trên miền đầy đủ."


def _with_interpretation(response: AlgebraSolveResponse, raw_input: str, interpretation) -> AlgebraSolveResponse:
    response.input = raw_input
    response.input_interpretation = interpretation
    if interpretation.warnings:
        response.warnings = [*interpretation.warnings, *response.warnings]
    return response
