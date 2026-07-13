from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolveResponse, AlgebraSolveStep, AlgebraVerificationCheck, AlgebraVerificationReport
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step


def solve_expression(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    if problem.expression is None:
        return _unsupported(problem, "Không tìm thấy biểu thức hợp lệ.")

    expression = problem.expression
    expanded = sp.expand(expression)
    factored = sp.factor(expression)

    if problem.expression_action == "expand":
        result, action, method = expanded, "khai triển", "expand"
    elif problem.expression_action == "factor":
        result, action, method = factored, "phân tích nhân tử", "factor"
    elif problem.expression_action == "simplify":
        result, action, method = sp.simplify(expression), "rút gọn", "simplify"
    elif expression != expanded and factored == expression:
        result, action, method = expanded, "khai triển", "expand"
    elif expression != factored and expanded == expression:
        result, action, method = factored, "phân tích nhân tử", "factor"
    else:
        result, action, method = sp.simplify(expression), "rút gọn", "simplify"

    verification_passed = sp.simplify(expression - result) == 0

    milestones: list[str] = [
        f"Biểu thức gốc: {sp.latex(expression)}",
        f"Kết quả {action}: {sp.latex(result)}"
    ]

    steps = [
        AlgebraSolveStep(
            index=1,
            title=f"Biến đổi biểu thức",
            explanation=f"Thực hiện {action} biểu thức.",
            goal=f"Đưa biểu thức về dạng {action} tối ưu.",
            why=f"Dạng {action} giúp biểu thức dễ tính toán hoặc phân tích hơn.",
            rule=action.capitalize(),
            operation=f"Sử dụng các quy tắc đại số để {action}.",
            before_latex=sp.latex(expression),
            after_latex=sp.latex(result),
            expression=sp.sstr(expression),
            expression_latex=sp.latex(expression),
            result=sp.sstr(result),
            result_latex=sp.latex(result),
            kind="transform",
            confidence="symbolic",
        )
    ]

    answer = f"Kết quả: {sp.sstr(result)}"
    steps.append(conclusion_step(2, answer, sp.latex(result)))

    verification = AlgebraVerificationReport(
        status="verified" if verification_passed else "failed",
        checks=[AlgebraVerificationCheck(
            name="symbolic_equivalence",
            status="pass" if verification_passed else "fail",
            detail=(
                f"Hiệu giữa biểu thức gốc và kết quả {method} rút gọn về 0."
                if verification_passed
                else f"Kết quả {method} không tương đương biểu thức gốc."
            ),
            latex=sp.latex(sp.simplify(expression - result)),
        )],
        method=["symbolic_difference"],
    )

    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="expression",
        problem_type=f"transform_{method}",
        status="solved" if verification_passed else "error",
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


def _unsupported(problem: ParsedAlgebraProblem, reason: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="expression",
        problem_type="unknown",
        status="unsupported",
        answer="Chưa hỗ trợ biểu thức này.",
        warnings=[],
        errors=[reason],
    )
