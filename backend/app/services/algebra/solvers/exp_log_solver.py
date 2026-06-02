from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolutionValue, AlgebraSolveResponse, AlgebraSolveStep
from app.services.algebra.domain import domain_assumptions_from_expression
from app.services.algebra.formatting import format_solution_set, solution_values
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step, domain_step
from app.services.algebra.verifier import verify_finite_solutions, verify_solution_set


def solve_exp_log(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    if problem.relation is None or not isinstance(problem.relation, sp.Equality):
        return _unsupported(problem, "Đầu vào không phải phương trình mũ-log.")
    variable = problem.variable
    raw_expression = problem.relation.lhs - problem.relation.rhs
    expression = sp.simplify(raw_expression)
    if not _is_exp_log_expression(expression):
        return _unsupported(problem, "Phương trình không chứa thành phần mũ hoặc log.")
    assumptions = domain_assumptions_from_expression(raw_expression, variable)
    steps: list[AlgebraSolveStep] = []
    if assumptions:
        steps.append(domain_step(len(steps) + 1, assumptions))
    try:
        solution_set = sp.solveset(expression, variable, domain=sp.S.Reals if problem.domain == "R" else sp.S.Complexes)
    except Exception as exc:
        return _unsupported(problem, f"SymPy chưa giải được phương trình mũ-log này: {exc}")
    steps.extend(_log_transform_steps(problem, len(steps) + 1))
    steps.append(AlgebraSolveStep(
        index=len(steps) + 1,
        title="Giải phương trình còn lại",
        explanation="Giải phương trình sau khi đã bỏ log/mũ và giữ điều kiện xác định.",
        expression=sp.sstr(expression),
        expression_latex=sp.latex(expression),
        result=sp.sstr(solution_set),
        result_latex=sp.latex(solution_set),
        kind="solve",
        confidence="symbolic",
    ))
    values = solution_values(solution_set)
    if values is not None:
        values = [value for value in values if _is_valid_solution(problem.relation, variable, value)]
        solution_set = sp.FiniteSet(*values) if values else sp.EmptySet
    answer = format_solution_set(solution_set)
    solution = AlgebraSolutionSet(
        kind="empty" if solution_set is sp.EmptySet else "finite" if values is not None else "set",
        text=answer,
        latex=sp.latex(solution_set),
        values=[AlgebraSolutionValue(text=sp.sstr(value), latex=sp.latex(value), approximate=str(sp.N(value, 8))) for value in values or []],
    )
    verification = verify_finite_solutions(problem, values) if values is not None else verify_solution_set(problem, solution_set)
    status = "solved" if verification.status in {"verified", "partially_verified"} else "error"
    steps.append(conclusion_step(len(steps) + 1, answer, sp.latex(solution_set)))
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="exponential_log",
        problem_type="solve_exp_log_equation",
        status=status,
        answer=answer,
        answer_latex=sp.latex(solution_set),
        solution_set=solution,
        steps=steps,
        verification=verification,
        assumptions=assumptions,
        warnings=[] if values is not None else ["Tập nghiệm mũ-log symbolic không hữu hạn nên chỉ kiểm chứng ở mức biểu diễn tập nghiệm."],
        errors=[] if status == "solved" else ["Kiểm chứng nghiệm mũ-log thất bại."],
    )


def _is_valid_solution(relation: sp.Relational, variable: sp.Symbol, value: sp.Expr) -> bool:
    try:
        checked = sp.simplify(relation.subs(variable, value))
        if checked is sp.S.true:
            return True
        if checked is sp.S.false:
            return False
        return bool(checked)
    except Exception:
        return False


def _log_transform_steps(problem: ParsedAlgebraProblem, start_index: int) -> list[AlgebraSolveStep]:
    if problem.relation is None:
        return []
    lhs = problem.relation.lhs
    rhs = problem.relation.rhs
    numerator, denominator = lhs.as_numer_denom()
    if numerator.func is sp.log and denominator.func is sp.log and not rhs.has(problem.variable):
        arg = numerator.args[0]
        base = denominator.args[0]
        target = sp.Pow(base, rhs, evaluate=False)
        return [AlgebraSolveStep(
            index=start_index,
            title="Bỏ log",
            explanation=f"Dùng định nghĩa log: log cơ số {sp.sstr(base)} của A bằng {sp.sstr(rhs)} thì A = {sp.sstr(base)}^{sp.sstr(rhs)}.",
            before_latex=sp.latex(problem.relation),
            after_latex=sp.latex(sp.Eq(arg, target, evaluate=False)),
            expression=sp.sstr(arg),
            expression_latex=sp.latex(arg),
            result=sp.sstr(target),
            result_latex=sp.latex(sp.Eq(arg, target, evaluate=False)),
            kind="transform",
            confidence="symbolic",
        )]
    return []


def _is_exp_log_expression(expression: sp.Expr) -> bool:
    return expression.has(sp.log) or expression.has(sp.exp) or any(isinstance(power, sp.Pow) and power.exp.has(*expression.free_symbols) for power in expression.atoms(sp.Pow))


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="exponential_log", problem_type="solve_exp_log_equation", status="unsupported", answer=message, errors=[message])
