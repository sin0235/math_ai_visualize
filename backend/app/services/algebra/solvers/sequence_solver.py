from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolveResponse, AlgebraSolveStep, AlgebraVerificationCheck, AlgebraVerificationReport
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step


def solve_sequence(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    normalized = problem.normalized_input.strip()
    try:
        calculation = _evaluate(normalized)
    except ValueError as exc:
        return _unsupported(problem, str(exc))
    result = calculation.result
    steps = [
        AlgebraSolveStep(
            index=1,
            title="Viết công thức",
            explanation=calculation.formula_explanation,
            before_latex=calculation.formula_latex,
            after_latex=calculation.substitution_latex,
            expression=calculation.formula_text,
            expression_latex=calculation.formula_latex,
            result=calculation.substitution_text,
            result_latex=calculation.substitution_latex,
            kind="transform",
            confidence="verified",
        ),
        AlgebraSolveStep(
            index=2,
            title="Tính kết quả",
            explanation=calculation.result_explanation,
            before_latex=calculation.substitution_latex,
            after_latex=calculation.result_latex,
            expression=calculation.substitution_text,
            expression_latex=calculation.substitution_latex,
            result=sp.sstr(result),
            result_latex=calculation.result_latex,
            kind="solve",
            confidence="verified",
        ),
    ]
    answer = f"Kết quả: {sp.sstr(result)}"
    steps.append(conclusion_step(3, answer, sp.latex(result)))
    
    milestones = [
        f"Công thức: {calculation.formula_latex}",
        f"Thay số: {calculation.substitution_latex}",
        f"Kết quả: {calculation.result_latex}"
    ]
    
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
        milestones=milestones,
        verification=verification,
        assumptions=[],
        warnings=[],
        errors=[],
    )


@dataclass(frozen=True)
class SequenceCalculation:
    result: sp.Expr
    formula_text: str
    formula_latex: str
    substitution_text: str
    substitution_latex: str
    result_latex: str
    formula_explanation: str
    result_explanation: str


def _evaluate(text: str) -> SequenceCalculation:
    match = re.fullmatch(r"(arithmetic|arithmetic_sum|geometric|geometric_sum)\((.*)\)", text)
    if not match:
        raise ValueError("Dạng cấp số này chưa được hỗ trợ. Hãy dùng arithmetic(...), arithmetic_sum(...), geometric(...) hoặc geometric_sum(...).")
    kind, args_text = match.groups()
    args = _parse_args(args_text)
    n = _parse_positive_integer_index(args.get("n"), field_name="n")
    u1 = args.get("u1")
    if u1 is None:
        raise ValueError("Cần nhập u1 cho cấp số.")
    if kind.startswith("arithmetic"):
        d = args.get("d")
        if d is None:
            raise ValueError("Cấp số cộng cần tham số d.")
        if kind == "arithmetic":
            result = u1 + (n - 1) * d
            return SequenceCalculation(
                result=_to_sympy(result),
                formula_text="u_n = u_1 + (n-1)d",
                formula_latex=r"u_n=u_1+(n-1)d",
                substitution_text=f"u_{n} = {u1} + ({n}-1)*{d}",
                substitution_latex=rf"u_{{{n}}}={_latex_fraction(u1)}+({n}-1)\cdot {_latex_fraction(d)}",
                result_latex=rf"u_{{{n}}}={sp.latex(_to_sympy(result))}",
                formula_explanation="Cấp số cộng dùng công thức số hạng tổng quát.",
                result_explanation=f"Thay n = {n} rồi tính ra số hạng cần tìm.",
            )
        result = Fraction(n, 2) * (2 * u1 + (n - 1) * d)
        return SequenceCalculation(
            result=_to_sympy(result),
            formula_text="S_n = n(2u_1+(n-1)d)/2",
            formula_latex=r"S_n=\frac{n(2u_1+(n-1)d)}{2}",
            substitution_text=f"S_{n} = {n}*(2*{u1}+({n}-1)*{d})/2",
            substitution_latex=rf"S_{{{n}}}=\frac{{{n}\left(2\cdot {_latex_fraction(u1)}+({n}-1)\cdot {_latex_fraction(d)}\right)}}{{2}}",
            result_latex=rf"S_{{{n}}}={sp.latex(_to_sympy(result))}",
            formula_explanation="Tổng n số hạng đầu của cấp số cộng dùng công thức tổng.",
            result_explanation=f"Thay n = {n} rồi rút gọn tổng.",
        )
    q = args.get("q")
    if q is None:
        raise ValueError("Cấp số nhân cần tham số q.")
    if kind == "geometric":
        result = u1 * (q ** (n - 1))
        return SequenceCalculation(
            result=_to_sympy(result),
            formula_text="u_n = u_1*q^(n-1)",
            formula_latex=r"u_n=u_1q^{n-1}",
            substitution_text=f"u_{n} = {u1}*{q}^({n}-1)",
            substitution_latex=rf"u_{{{n}}}={_latex_fraction(u1)}\cdot ({_latex_fraction(q)})^{{{n}-1}}",
            result_latex=rf"u_{{{n}}}={sp.latex(_to_sympy(result))}",
            formula_explanation="Cấp số nhân dùng công thức số hạng tổng quát.",
            result_explanation=f"Thay n = {n} rồi tính lũy thừa.",
        )
    if q == 1:
        result = u1 * n
        formula_latex = r"S_n=n u_1"
        substitution_latex = rf"S_{{{n}}}={n}\cdot {_latex_fraction(u1)}"
    else:
        result = u1 * (q ** n - 1) / (q - 1)
        formula_latex = r"S_n=\frac{u_1(q^n-1)}{q-1}"
        substitution_latex = rf"S_{{{n}}}=\frac{{{_latex_fraction(u1)}\left(({_latex_fraction(q)})^{n}-1\right)}}{{{_latex_fraction(q)}-1}}"
    return SequenceCalculation(
        result=_to_sympy(result),
        formula_text="S_n = u_1(q^n-1)/(q-1)",
        formula_latex=formula_latex,
        substitution_text=f"S_{n} = {u1}*({q}^{n}-1)/({q}-1)",
        substitution_latex=substitution_latex,
        result_latex=rf"S_{{{n}}}={sp.latex(_to_sympy(result))}",
        formula_explanation="Tổng n số hạng đầu của cấp số nhân dùng công thức tổng.",
        result_explanation=f"Thay n = {n} rồi rút gọn tổng.",
    )


def _parse_args(text: str) -> dict[str, Fraction]:
    result: dict[str, Fraction] = {}
    for part in text.split(","):
        if "=" not in part:
            raise ValueError("Tham số cấp số cần ở dạng key=value.")
        key, value = part.split("=", 1)
        result[key.strip()] = Fraction(value.strip())
    return result


def _parse_positive_integer_index(value: Fraction | None, *, field_name: str) -> int:
    if value is None:
        raise ValueError(f"Cần nhập {field_name} cho cấp số.")
    if value.denominator != 1:
        raise ValueError(f"SEQUENCE_N_NOT_INTEGER: tham số {field_name} phải là số nguyên dương, không được là phân số/thập phân.")
    n = value.numerator
    if n <= 0:
        raise ValueError(f"Tham số {field_name} phải là số nguyên dương.")
    if n > 1_000_000:
        raise ValueError(f"Tham số {field_name} quá lớn để tính an toàn.")
    return n


def _to_sympy(value: Fraction) -> sp.Expr:
    return sp.Rational(value.numerator, value.denominator)


def _latex_fraction(value: Fraction) -> str:
    return sp.latex(_to_sympy(value))


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="sequence", problem_type="calculate_sequence", status="unsupported", answer=message, errors=[message])
