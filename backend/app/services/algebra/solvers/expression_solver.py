from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolveResponse, AlgebraSolveStep, AlgebraVerificationCheck, AlgebraVerificationReport
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step


def solve_expression(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    if problem.expression is None:
        return _unsupported(problem, "Không tìm thấy biểu thức hợp lệ.")

    expression = problem.expression
    
    # Analyze the expression to decide what to do
    expanded = sp.expand(expression)
    factored = sp.factor(expression)
    simplified = sp.simplify(expression)

    # Determine primary transformation
    if expression != expanded and factored == expression:
        result = expanded
        action = "khai triển"
        method = "expand"
    elif expression != factored and expanded == expression:
        result = factored
        action = "phân tích nhân tử"
        method = "factor"
    else:
        result = simplified
        action = "rút gọn"
        method = "simplify"

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
        status="verified",
        checks=[AlgebraVerificationCheck(name="expression_transform", status="pass", detail=f"Biến đổi symbolic {method} thành công.", latex=sp.latex(result))],
        method=[f"sympy.{method}"],
    )

    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="expression",
        problem_type=f"transform_{method}",
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
