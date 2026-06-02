from __future__ import annotations

import sympy as sp

from app.core.config import Settings, get_settings
from app.schemas.algebra import AlgebraSolveRequest, AlgebraSolveResponse
from app.services.algebra.ai_explainer import explain_algebra_response_with_ai
from app.services.algebra.ai_extraction import extract_algebra_request_with_ai
from app.services.algebra.classifier import classify_algebra_problem
from app.services.algebra.interpreter import interpret_algebra_input
from app.services.algebra.normalizer import normalize_algebra_input
from app.services.algebra.parser import AlgebraParseError, ParsedAlgebraProblem, parse_algebra_problem
from app.services.algebra.solvers.calculus_solver import solve_calculus
from app.services.algebra.solvers.combinatorics_probability_solver import solve_combinatorics_probability
from app.services.algebra.solvers.complex_solver import solve_complex
from app.services.algebra.solvers.equation_solver import solve_equation
from app.services.algebra.solvers.exp_log_solver import solve_exp_log
from app.services.algebra.solvers.inequality_solver import solve_inequality
from app.services.algebra.solvers.parameter_solver import solve_parameter
from app.services.algebra.solvers.sequence_solver import solve_sequence
from app.services.algebra.solvers.system_solver import solve_system
from app.services.algebra.solvers.trig_solver import solve_trigonometry


def solve_algebra(request: AlgebraSolveRequest) -> AlgebraSolveResponse:
    return solve_algebra_deterministic(request)


async def solve_algebra_with_optional_ai(request: AlgebraSolveRequest, settings: Settings | None = None) -> AlgebraSolveResponse:
    settings = settings or get_settings()
    extraction_warnings: list[str] = []
    deterministic_request = request
    if request.options.use_ai_extraction:
        try:
            deterministic_request, extraction_warnings = await extract_algebra_request_with_ai(request.input, request, settings)
        except Exception as error:
            extraction_warnings = [f"Không gọi được AI extraction, đang dùng rule-based interpreter: {error}"]
    response = solve_algebra_deterministic(deterministic_request)
    if deterministic_request.input != request.input:
        response.input = request.input
        response.normalized_input = deterministic_request.input
    if extraction_warnings:
        response.warnings = [*extraction_warnings, *response.warnings]
    if request.options.ai_explanation:
        response = await explain_algebra_response_with_ai(response, settings)
    return response


def solve_algebra_deterministic(request: AlgebraSolveRequest) -> AlgebraSolveResponse:
    interpretation = interpret_algebra_input(request)
    requested_topic = _resolve_requested_topic(request.topic, interpretation.topic_hint, interpretation.canonical_input)
    variables = request.variables or interpretation.variables or ["x"]
    domain = interpretation.domain if request.domain == "R" and interpretation.domain != "R" else request.domain
    if requested_topic == "combinatorics_probability":
        problem = _raw_problem(request, interpretation.canonical_input, variables, domain, requested_topic)
        return _with_interpretation(solve_combinatorics_probability(problem), request.input, interpretation)
    if requested_topic == "sequence":
        problem = _raw_problem(request, interpretation.canonical_input, variables, domain, requested_topic)
        return _with_interpretation(solve_sequence(problem), request.input, interpretation)
    if requested_topic == "parameter":
        problem = _raw_problem(request, interpretation.canonical_input, variables, domain, requested_topic)
        return _with_interpretation(solve_parameter(problem), request.input, interpretation)
    if requested_topic in {"calculus_derivative", "calculus_limit", "calculus_integral"}:
        problem = _raw_problem(request, interpretation.canonical_input, variables, domain, requested_topic)
        return _with_interpretation(solve_calculus(problem), request.input, interpretation)
    try:
        problem = parse_algebra_problem(interpretation.canonical_input, topic=requested_topic, variables=variables, domain=domain)
    except AlgebraParseError as exc:
        return AlgebraSolveResponse(
            input=request.input,
            normalized_input=interpretation.canonical_input,
            input_interpretation=interpretation,
            topic=requested_topic,
            problem_type="parse_error",
            status="error",
            answer="Không thể đọc đề bài đại số này.",
            warnings=interpretation.warnings,
            errors=[str(exc)],
        )
    topic = classify_algebra_problem(problem)
    if topic == "equation":
        return _with_interpretation(solve_equation(problem), request.input, interpretation)
    if topic == "inequality":
        return _with_interpretation(solve_inequality(problem), request.input, interpretation)
    if topic == "exponential_log":
        return _with_interpretation(solve_exp_log(problem), request.input, interpretation)
    if topic == "trigonometry":
        return _with_interpretation(solve_trigonometry(problem), request.input, interpretation)
    if topic == "complex":
        return _with_interpretation(solve_complex(problem), request.input, interpretation)
    if topic == "system":
        return _with_interpretation(solve_system(problem), request.input, interpretation)
    if topic == "combinatorics_probability":
        return _with_interpretation(solve_combinatorics_probability(problem), request.input, interpretation)
    if topic == "sequence":
        return _with_interpretation(solve_sequence(problem), request.input, interpretation)
    if topic == "parameter":
        return _with_interpretation(solve_parameter(problem), request.input, interpretation)
    if topic in {"calculus_derivative", "calculus_limit", "calculus_integral"}:
        return _with_interpretation(solve_calculus(problem), request.input, interpretation)
    return _with_interpretation(AlgebraSolveResponse(
        input=request.input,
        normalized_input=problem.normalized_input,
        topic=topic,
        problem_type="unsupported",
        status="unsupported",
        answer="Dạng bài này chưa được hỗ trợ trong phase đầu. Hiện hệ thống ưu tiên phương trình và bất phương trình một biến.",
        warnings=["Các nhóm tham số và các dạng đề tự nhiên dài sẽ được bổ sung ở các phase sau."],
    ), request.input, interpretation)


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


def _raw_problem(request: AlgebraSolveRequest, canonical_input: str, variables: list[str], domain: str, topic: str) -> ParsedAlgebraProblem:
    symbols = [sp.Symbol(name, real=(domain != "C")) for name in variables]
    return ParsedAlgebraProblem(
        raw_input=canonical_input,
        normalized_input=canonical_input.strip().replace("^", "**"),
        topic=topic,
        variable=symbols[0],
        variables=symbols,
        domain=domain,
    )


def _with_interpretation(response: AlgebraSolveResponse, raw_input: str, interpretation) -> AlgebraSolveResponse:
    response.input = raw_input
    response.input_interpretation = interpretation
    if interpretation.warnings:
        response.warnings = [*interpretation.warnings, *response.warnings]
    return response
