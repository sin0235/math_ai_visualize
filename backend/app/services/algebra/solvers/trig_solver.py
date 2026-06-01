from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolutionValue, AlgebraSolveResponse, AlgebraSolveStep
from app.services.algebra.domain import domain_assumptions_from_expression
from app.services.algebra.formatting import format_solution_set, solution_values
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step, domain_step, normalize_step
from app.services.algebra.verifier import verify_finite_solutions, verify_solution_set

TRIG_FUNCTIONS = (sp.sin, sp.cos, sp.tan, sp.cot)


def solve_trigonometry(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    if problem.relation is None or not isinstance(problem.relation, sp.Equality):
        return _unsupported(problem, "Đầu vào không phải phương trình lượng giác.")
    variable = problem.variable
    expression = sp.simplify(problem.relation.lhs - problem.relation.rhs)
    if not any(expression.has(func) for func in TRIG_FUNCTIONS):
        return _unsupported(problem, "Phương trình không chứa hàm lượng giác được hỗ trợ.")
    assumptions = domain_assumptions_from_expression(expression, variable)
    steps: list[AlgebraSolveStep] = [normalize_step(problem), domain_step(2, assumptions)]
    solution_set = _solve_on_default_interval(expression, variable)
    if solution_set is None:
        try:
            solution_set = sp.solveset(expression, variable, domain=sp.S.Reals)
        except Exception as exc:
            return _unsupported(problem, f"SymPy chưa giải được phương trình lượng giác này: {exc}")
        solve_explanation = "Hệ thống giải phương trình lượng giác trên miền số thực. Với nghiệm tuần hoàn, kết quả có thể ở dạng tập symbolic."
    else:
        solve_explanation = "Hệ thống giải phương trình lượng giác trên khoảng chuẩn [0, 2*pi) để tạo nghiệm hữu hạn dễ kiểm chứng."
    steps.append(AlgebraSolveStep(
        index=3,
        title="Giải phương trình lượng giác symbolic",
        explanation=solve_explanation,
        expression=sp.sstr(expression),
        expression_latex=sp.latex(expression),
        result=sp.sstr(solution_set),
        result_latex=sp.latex(solution_set),
        kind="solve",
        confidence="symbolic",
    ))
    values = solution_values(solution_set)
    answer = format_solution_set(solution_set)
    solution = AlgebraSolutionSet(
        kind="empty" if solution_set is sp.EmptySet else "finite" if values is not None else "periodic",
        text=answer,
        latex=sp.latex(solution_set),
        values=[AlgebraSolutionValue(text=sp.sstr(value), latex=sp.latex(value), approximate=str(sp.N(value, 8))) for value in values or []],
    )
    verification = verify_finite_solutions(problem, values) if values is not None else verify_solution_set(problem, solution_set)
    status = "solved" if verification.status in {"verified", "partially_verified"} else "error"
    steps.append(conclusion_step(4, answer, sp.latex(solution_set)))
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="trigonometry",
        problem_type="solve_trigonometric_equation",
        status=status,
        answer=answer,
        answer_latex=sp.latex(solution_set),
        solution_set=solution,
        steps=steps,
        verification=verification,
        assumptions=assumptions,
        warnings=[] if values is not None else ["Nghiệm lượng giác tuần hoàn được biểu diễn symbolic nên chỉ kiểm chứng ở mức tập nghiệm."],
        errors=[] if status == "solved" else ["Kiểm chứng nghiệm lượng giác thất bại."],
    )


def _solve_on_default_interval(expression: sp.Expr, variable: sp.Symbol) -> sp.Set | None:
    try:
        solution = sp.solveset(expression, variable, domain=sp.Interval.Ropen(0, 2 * sp.pi))
    except Exception:
        return None
    if isinstance(solution, sp.ConditionSet):
        return None
    return solution


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="trigonometry", problem_type="solve_trigonometric_equation", status="unsupported", answer=message, errors=[message])
