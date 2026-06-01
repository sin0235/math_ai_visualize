from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolveResponse, AlgebraSolveStep, AlgebraVerificationCheck, AlgebraVerificationReport
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step, normalize_step


def solve_system(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    if len(problem.relations) < 2:
        return _unsupported(problem, "Đầu vào chưa phải hệ phương trình.")
    if any(not isinstance(relation, sp.Equality) for relation in problem.relations):
        return _unsupported(problem, "Phase này chỉ hỗ trợ hệ phương trình.")
    variables = problem.variables or _infer_variables(problem.relations)
    expressions = [sp.simplify(relation.lhs - relation.rhs) for relation in problem.relations]
    steps = [normalize_step(problem)]
    try:
        solution_set = sp.linsolve(expressions, variables)
        method = "linsolve"
    except Exception:
        try:
            solution_set = sp.nonlinsolve(expressions, variables)
            method = "nonlinsolve"
        except Exception as exc:
            return _unsupported(problem, f"SymPy chưa giải được hệ này: {exc}")
    steps.append(AlgebraSolveStep(
        index=2,
        title="Giải hệ phương trình symbolic",
        explanation=f"Hệ thống dùng {method} để giải hệ theo các biến {', '.join(sp.sstr(variable) for variable in variables)}.",
        expression="; ".join(sp.sstr(expr) for expr in expressions),
        expression_latex="; ".join(sp.latex(expr) for expr in expressions),
        result=sp.sstr(solution_set),
        result_latex=sp.latex(solution_set),
        kind="solve",
        confidence="symbolic",
    ))
    verification = _verify_system(problem.relations, variables, solution_set)
    answer = _format_system_solution(solution_set, variables)
    steps.append(conclusion_step(3, answer, sp.latex(solution_set)))
    status = "solved" if verification.status in {"verified", "partially_verified"} else "error"
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="system",
        problem_type="solve_system",
        status=status,
        answer=answer,
        answer_latex=sp.latex(solution_set),
        solution_set=AlgebraSolutionSet(kind="finite" if isinstance(solution_set, sp.FiniteSet) else "set", text=answer, latex=sp.latex(solution_set)),
        steps=steps,
        verification=verification,
        assumptions=[],
        warnings=[] if verification.status == "verified" else ["Hệ có nghiệm symbolic hoặc vô nghiệm nên chỉ kiểm chứng một phần."],
        errors=[] if status == "solved" else ["Kiểm chứng nghiệm hệ phương trình thất bại."],
    )


def _infer_variables(relations: list[sp.Relational]) -> list[sp.Symbol]:
    symbols = sorted(set().union(*(relation.free_symbols for relation in relations)), key=sp.default_sort_key)
    return list(symbols)


def _format_system_solution(solution_set: sp.Set, variables: list[sp.Symbol]) -> str:
    if solution_set is sp.EmptySet:
        return "Hệ vô nghiệm."
    if isinstance(solution_set, sp.FiniteSet):
        tuples = list(solution_set)
        if len(tuples) == 1:
            values = tuples[0]
            if not isinstance(values, sp.Tuple):
                values = sp.Tuple(values)
            parts = [f"{sp.sstr(variable)} = {sp.sstr(value)}" for variable, value in zip(variables, values)]
            return "Nghiệm hệ: " + "; ".join(parts)
    return f"Tập nghiệm hệ: {sp.sstr(solution_set)}"


def _verify_system(relations: list[sp.Relational], variables: list[sp.Symbol], solution_set: sp.Set) -> AlgebraVerificationReport:
    checks: list[AlgebraVerificationCheck] = []
    if solution_set is sp.EmptySet:
        return AlgebraVerificationReport(status="partially_verified", checks=[AlgebraVerificationCheck(name="empty_system_solution", status="warn", detail="Solver symbolic trả hệ vô nghiệm.")], method=["substitution"])
    if not isinstance(solution_set, sp.FiniteSet):
        return AlgebraVerificationReport(status="partially_verified", checks=[AlgebraVerificationCheck(name="symbolic_system_solution", status="warn", detail="Tập nghiệm hệ ở dạng symbolic, chưa thay được từng nghiệm hữu hạn.", latex=sp.latex(solution_set))], method=["symbolic"])
    for solution in solution_set:
        values = solution if isinstance(solution, sp.Tuple) else sp.Tuple(solution)
        substitutions = dict(zip(variables, values))
        ok = all(_check_relation(relation, substitutions) for relation in relations)
        checks.append(AlgebraVerificationCheck(
            name="system_tuple_substitution",
            status="pass" if ok else "fail",
            detail=f"Thay {', '.join(f'{sp.sstr(key)} = {sp.sstr(value)}' for key, value in substitutions.items())} vào hệ {'đúng' if ok else 'không đúng'}.",
            latex=", ".join(f"{sp.latex(key)} = {sp.latex(value)}" for key, value in substitutions.items()),
        ))
    return AlgebraVerificationReport(status="verified" if checks and all(check.status == "pass" for check in checks) else "failed", checks=checks, method=["substitution"])


def _check_relation(relation: sp.Relational, substitutions: dict[sp.Symbol, sp.Expr]) -> bool:
    try:
        checked = sp.simplify(relation.subs(substitutions))
        if checked is sp.S.true:
            return True
        if checked is sp.S.false:
            return False
        return bool(checked)
    except Exception:
        return False


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="system", problem_type="solve_system", status="unsupported", answer=message, errors=[message])
