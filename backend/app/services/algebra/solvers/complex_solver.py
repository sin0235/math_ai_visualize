from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolutionValue, AlgebraSolveResponse, AlgebraSolveStep
from app.services.algebra.formatting import format_solution_set, solution_values
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step, normalize_step
from app.services.algebra.verifier import verify_finite_solutions, verify_solution_set


def solve_complex(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    if problem.relation is not None:
        return _solve_complex_equation(problem)
    if problem.expression is not None:
        return _evaluate_complex_expression(problem)
    return _unsupported(problem, "Không có biểu thức số phức để xử lý.")


def _solve_complex_equation(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    variable = problem.variable
    expression = sp.simplify(problem.relation.lhs - problem.relation.rhs)
    steps = [normalize_step(problem)]
    try:
        solution_set = sp.solveset(expression, variable, domain=sp.S.Complexes)
    except Exception as exc:
        return _unsupported(problem, f"SymPy chưa giải được phương trình số phức này: {exc}")
    steps.append(AlgebraSolveStep(
        index=2,
        title="Giải phương trình trên miền phức",
        explanation="Hệ thống giải phương trình với miền nghiệm là số phức.",
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
    steps.append(conclusion_step(3, answer, sp.latex(solution_set)))
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="complex",
        problem_type="solve_complex_equation",
        status=status,
        answer=answer,
        answer_latex=sp.latex(solution_set),
        solution_set=solution,
        steps=steps,
        verification=verification,
        assumptions=[],
        warnings=[] if values is not None else ["Tập nghiệm phức symbolic không hữu hạn nên chỉ kiểm chứng ở mức biểu diễn tập nghiệm."],
        errors=[] if status == "solved" else ["Kiểm chứng nghiệm phức thất bại."],
    )


def _evaluate_complex_expression(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    expression = sp.simplify(problem.expression)
    result = sp.simplify(expression)
    steps = [normalize_step(problem), AlgebraSolveStep(
        index=2,
        title="Tính biểu thức số phức",
        explanation="Hệ thống rút gọn biểu thức số phức bằng symbolic engine.",
        expression=sp.sstr(expression),
        expression_latex=sp.latex(expression),
        result=sp.sstr(result),
        result_latex=sp.latex(result),
        kind="solve",
        confidence="symbolic",
    )]
    answer = f"Kết quả: {sp.sstr(result)}"
    steps.append(conclusion_step(3, answer, sp.latex(result)))
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="complex",
        problem_type="evaluate_complex_expression",
        status="solved",
        answer=answer,
        answer_latex=sp.latex(result),
        solution_set=AlgebraSolutionSet(kind="expression", text=sp.sstr(result), latex=sp.latex(result)),
        steps=steps,
        verification=verify_solution_set(problem, sp.FiniteSet(result)),
        assumptions=[],
        warnings=[],
        errors=[],
    )


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="complex", problem_type="complex", status="unsupported", answer=message, errors=[message])
