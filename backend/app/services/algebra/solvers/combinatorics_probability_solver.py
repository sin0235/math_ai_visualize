from __future__ import annotations

import math
import re

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolveResponse, AlgebraSolveStep, AlgebraVerificationCheck, AlgebraVerificationReport
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step, normalize_step


def solve_combinatorics_probability(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    normalized = problem.normalized_input.strip()
    steps = [normalize_step(problem)]
    try:
        result, explanation, latex = _evaluate(normalized)
    except ValueError as exc:
        return _unsupported(problem, str(exc))
    steps.append(AlgebraSolveStep(
        index=2,
        title="Tính toán tổ hợp",
        explanation=explanation,
        expression=normalized,
        expression_latex=latex,
        result=sp.sstr(result),
        result_latex=sp.latex(result),
        kind="solve",
        confidence="symbolic",
    ))
    answer = f"Kết quả: {sp.sstr(result)}"
    steps.append(conclusion_step(3, answer, sp.latex(result)))
    verification = AlgebraVerificationReport(
        status="verified",
        checks=[AlgebraVerificationCheck(name="combinatorics_constraints_valid", status="pass", detail="Các tham số tổ hợp thỏa điều kiện nguyên không âm trong phạm vi hỗ trợ.")],
        method=["rule_based"],
    )
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="combinatorics_probability",
        problem_type="calculate_combinatorics",
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
    permutation = re.fullmatch(r"A\((\d+)\s*,\s*(\d+)\)", text)
    if permutation:
        n, k = _parse_pair(permutation)
        _validate_n_k(n, k)
        return sp.Integer(math.perm(n, k)), f"Tính chỉnh hợp A({n}, {k}) = n!/(n-k)!.", f"A_{{{n}}}^{{{k}}}"
    combination = re.fullmatch(r"(?:C|binomial)\((\d+)\s*,\s*(\d+)\)", text)
    if combination:
        n, k = _parse_pair(combination)
        _validate_n_k(n, k)
        return sp.Integer(math.comb(n, k)), f"Tính tổ hợp C({n}, {k}) = n!/(k!(n-k)!).", f"C_{{{n}}}^{{{k}}}"
    factorial = re.fullmatch(r"(?:factorial\((\d+)\)|(\d+)!)", text)
    if factorial:
        n = int(factorial.group(1) or factorial.group(2))
        if n < 0:
            raise ValueError("Giai thừa chỉ hỗ trợ số nguyên không âm.")
        return sp.Integer(math.factorial(n)), f"Tính giai thừa {n}!.", f"{n}!"
    coefficient = re.fullmatch(r"coefficient\((.+),\s*([A-Za-z])\s*,\s*(-?\d+)\)", text)
    if coefficient:
        expr_text, variable_name, power_text = coefficient.groups()
        variable = sp.Symbol(variable_name, real=True)
        expression = sp.sympify(expr_text, locals={variable_name: variable})
        power = int(power_text)
        result = sp.expand(expression).coeff(variable, power)
        return result, f"Khai triển biểu thức và lấy hệ số của {variable_name}^{power}.", sp.latex(expression)
    raise ValueError("Dạng tổ hợp-xác suất này chưa được hỗ trợ. Hãy dùng C(n,k), A(n,k), n! hoặc coefficient(expr,x,k).")


def _parse_pair(match: re.Match[str]) -> tuple[int, int]:
    return int(match.group(1)), int(match.group(2))


def _validate_n_k(n: int, k: int) -> None:
    if n < 0 or k < 0:
        raise ValueError("n và k phải là số nguyên không âm.")
    if k > n:
        raise ValueError("Cần có k <= n trong tổ hợp/chỉnh hợp.")


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="combinatorics_probability", problem_type="calculate_combinatorics", status="unsupported", answer=message, errors=[message])
