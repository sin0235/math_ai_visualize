from __future__ import annotations

import sympy as sp
from sympy.solvers.inequalities import solve_univariate_inequality

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolveResponse, AlgebraSolveStep
from app.services.algebra.domain import domain_assumptions_from_expression
from app.services.algebra.formatting import format_interval_set
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.sign_chart import sign_chart_summary
from app.services.algebra.steps import conclusion_step, domain_step, normalize_step
from app.services.algebra.verifier import verify_solution_set


def solve_inequality(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    if problem.relation is None or isinstance(problem.relation, sp.Equality):
        return _unsupported(problem, "Đầu vào không phải bất phương trình.")
    variable = problem.variable
    expression = sp.simplify(problem.relation.lhs - problem.relation.rhs)
    assumptions = domain_assumptions_from_expression(expression, variable)
    steps: list[AlgebraSolveStep] = [normalize_step(problem), domain_step(2, assumptions)]
    try:
        result_set = solve_univariate_inequality(problem.relation, variable, relational=False)
    except Exception as exc:
        return _unsupported(problem, f"SymPy chưa giải được bất phương trình này: {exc}")
    steps.append(AlgebraSolveStep(
        index=3,
        title="Giải bất phương trình symbolic",
        explanation="Hệ thống giải bất phương trình một biến và biểu diễn kết quả dưới dạng tập nghiệm/ khoảng nghiệm.",
        expression=sp.sstr(problem.relation),
        expression_latex=sp.latex(problem.relation),
        result=sp.sstr(result_set),
        result_latex=sp.latex(result_set),
        kind="solve",
        confidence="symbolic",
    ))
    sign_summary = sign_chart_summary(expression, variable)
    if sign_summary:
        steps.append(AlgebraSolveStep(
            index=4,
            title="Xét dấu biểu thức",
            explanation=sign_summary,
            expression=sp.sstr(sp.factor(expression)),
            expression_latex=sp.latex(sp.factor(expression)),
            result=sp.sstr(result_set),
            result_latex=sp.latex(result_set),
            kind="verify",
            confidence="symbolic",
        ))
    verification = verify_solution_set(problem, result_set if isinstance(result_set, sp.Set) else sp.S.UniversalSet)
    answer = format_interval_set(result_set)
    steps.append(conclusion_step(5 if sign_summary else 4, answer, sp.latex(result_set)))
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="inequality",
        problem_type="solve_inequality",
        status="solved" if verification.status in {"verified", "partially_verified"} else "partial",
        answer=answer,
        answer_latex=sp.latex(result_set),
        solution_set=AlgebraSolutionSet(kind="empty" if result_set is sp.EmptySet else "interval", text=answer, latex=sp.latex(result_set)),
        steps=steps,
        verification=verification,
        assumptions=assumptions,
        warnings=[] if sign_summary else ["Bất phương trình được kiểm chứng ở mức tập nghiệm symbolic; chưa tạo được bảng xét dấu chi tiết cho dạng này."],
        errors=[],
    )


def _domain_assumptions(relation: sp.Relational, variable: sp.Symbol) -> list[str]:
    expression = sp.simplify(relation.lhs - relation.rhs)
    assumptions: list[str] = []
    denominator = sp.denom(expression)
    if denominator != 1 and denominator.has(variable):
        assumptions.append(f"{sp.sstr(denominator)} khác 0")
    for log_expr in expression.atoms(sp.log):
        arg = log_expr.args[0]
        if arg.has(variable):
            assumptions.append(f"{sp.sstr(arg)} > 0")
    return assumptions


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="inequality", problem_type="solve_inequality", status="unsupported", answer=message, errors=[message])
