from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolutionValue, AlgebraSolveResponse, AlgebraSolveStep
from app.services.algebra.domain import domain_assumptions_from_expression
from app.services.algebra.formatting import format_solution_set, solution_values
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step, domain_step, normalize_step
from app.services.algebra.verifier import verify_finite_solutions, verify_solution_set


def solve_equation(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    if problem.relation is None or not isinstance(problem.relation, sp.Equality):
        return _unsupported(problem, "Đầu vào không phải phương trình.")
    variable = problem.variable
    expression = sp.simplify(problem.relation.lhs - problem.relation.rhs)
    assumptions = domain_assumptions_from_expression(expression, variable)
    steps: list[AlgebraSolveStep] = [normalize_step(problem), domain_step(2, assumptions)]
    try:
        solution_set = sp.solveset(expression, variable, domain=sp.S.Reals if problem.domain == "R" else sp.S.Complexes)
    except Exception as exc:
        return _unsupported(problem, f"SymPy chưa giải được phương trình này: {exc}")
    steps.append(AlgebraSolveStep(
        index=3,
        title="Giải phương trình symbolic",
        explanation="Chuyển tất cả về một vế và giải phương trình bằng engine symbolic.",
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
        kind="empty" if solution_set is sp.EmptySet else "finite" if values is not None else "set",
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
        topic="equation",
        problem_type="solve_equation",
        status=status,
        answer=answer,
        answer_latex=sp.latex(solution_set),
        solution_set=solution,
        steps=steps,
        verification=verification,
        assumptions=assumptions,
        warnings=[] if values is not None else ["Tập nghiệm symbolic không hữu hạn nên chỉ kiểm chứng ở mức biểu diễn tập nghiệm."],
        errors=[] if status == "solved" else ["Kiểm chứng nghiệm thất bại."],
    )


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="equation", problem_type="solve_equation", status="unsupported", answer=message, errors=[message])
