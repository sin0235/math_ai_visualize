from __future__ import annotations

import re
from fractions import Fraction

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolveResponse, AlgebraSolveStep, AlgebraVerificationCheck, AlgebraVerificationReport
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step, normalize_step


def solve_sequence(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    normalized = problem.normalized_input.strip()
    steps = [normalize_step(problem)]
    try:
        result, explanation, latex = _evaluate(normalized)
    except ValueError as exc:
        return _unsupported(problem, str(exc))
    steps.append(AlgebraSolveStep(
        index=2,
        title="Tính cấp số structured",
        explanation=explanation,
        expression=normalized,
        expression_latex=latex,
        result=sp.sstr(result),
        result_latex=sp.latex(result),
        kind="solve",
        confidence="verified",
    ))
    answer = f"Kết quả: {sp.sstr(result)}"
    steps.append(conclusion_step(3, answer, sp.latex(result)))
    verification = AlgebraVerificationReport(
        status="verified",
        checks=[AlgebraVerificationCheck(name="sequence_formula_checked", status="pass", detail="Kết quả được tính bằng công thức cấp số chuẩn và kiểm tra tham số structured.")],
        method=["rule_based"],
    )
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="sequence",
        problem_type="calculate_sequence",
        status="solved",
        answer=answer,
        answer_latex=sp.latex(result),
        solution_set=AlgebraSolutionSet(kind="expression", text=sp.sstr(result), latex=sp.latex(result)),
        steps=steps,
        verification=verification,
        assumptions=[],
        warnings=[],
        errors=[],
    )


def _evaluate(text: str) -> tuple[sp.Expr, str, str]:
    match = re.fullmatch(r"(arithmetic|arithmetic_sum|geometric|geometric_sum)\((.*)\)", text)
    if not match:
        raise ValueError("Dạng cấp số này chưa được hỗ trợ. Hãy dùng arithmetic(...), arithmetic_sum(...), geometric(...) hoặc geometric_sum(...).")
    kind, args_text = match.groups()
    args = _parse_args(args_text)
    n = int(args.get("n", 0))
    if n <= 0:
        raise ValueError("Tham số n phải là số nguyên dương.")
    u1 = args.get("u1")
    if u1 is None:
        raise ValueError("Cần nhập u1 cho cấp số.")
    if kind.startswith("arithmetic"):
        d = args.get("d")
        if d is None:
            raise ValueError("Cấp số cộng cần tham số d.")
        if kind == "arithmetic":
            result = u1 + (n - 1) * d
            return _to_sympy(result), f"Dùng công thức cấp số cộng u_n = u1 + (n-1)d với n = {n}.", "u_n = u_1 + (n-1)d"
        result = Fraction(n, 2) * (2 * u1 + (n - 1) * d)
        return _to_sympy(result), f"Dùng công thức tổng cấp số cộng S_n = n(2u1+(n-1)d)/2 với n = {n}.", "S_n = \\frac{n(2u_1 + (n-1)d)}{2}"
    q = args.get("q")
    if q is None:
        raise ValueError("Cấp số nhân cần tham số q.")
    if kind == "geometric":
        result = u1 * (q ** (n - 1))
        return _to_sympy(result), f"Dùng công thức cấp số nhân u_n = u1*q^(n-1) với n = {n}.", "u_n = u_1q^{n-1}"
    if q == 1:
        result = u1 * n
    else:
        result = u1 * (q ** n - 1) / (q - 1)
    return _to_sympy(result), f"Dùng công thức tổng cấp số nhân S_n = u1(q^n-1)/(q-1) với n = {n}.", "S_n = \\frac{u_1(q^n-1)}{q-1}"


def _parse_args(text: str) -> dict[str, Fraction]:
    result: dict[str, Fraction] = {}
    for part in text.split(","):
        if "=" not in part:
            raise ValueError("Tham số cấp số cần ở dạng key=value.")
        key, value = part.split("=", 1)
        result[key.strip()] = Fraction(value.strip())
    return result


def _to_sympy(value: Fraction) -> sp.Expr:
    return sp.Rational(value.numerator, value.denominator)


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="sequence", problem_type="calculate_sequence", status="unsupported", answer=message, errors=[message])
