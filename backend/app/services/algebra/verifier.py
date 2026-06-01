from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraVerificationCheck, AlgebraVerificationReport
from app.services.algebra.parser import ParsedAlgebraProblem


def verify_finite_solutions(problem: ParsedAlgebraProblem, solutions: list[sp.Expr]) -> AlgebraVerificationReport:
    domain_checks = _domain_checks(problem, solutions)
    checks: list[AlgebraVerificationCheck] = []
    if problem.relation is None:
        return AlgebraVerificationReport(status="skipped", checks=[AlgebraVerificationCheck(name="relation_present", status="skip", detail="Không có phương trình/bất phương trình để kiểm chứng.")], method=[])
    checks.extend(domain_checks)
    relation = problem.relation
    variable = problem.variable
    for solution in solutions:
        ok = _check_relation(relation, variable, solution)
        checks.append(AlgebraVerificationCheck(
            name="candidate_substitution",
            status="pass" if ok else "fail",
            detail=f"Thay {variable} = {sp.sstr(solution)} vào biểu thức gốc {'đúng' if ok else 'không đúng'}.",
            latex=f"{sp.latex(variable)} = {sp.latex(solution)}",
        ))
    if not solutions:
        checks.append(AlgebraVerificationCheck(name="empty_solution_set", status="warn", detail="Không có nghiệm hữu hạn để thay ngược; kết quả dựa trên solver symbolic."))
        status = "partially_verified"
    else:
        status = "verified" if checks and all(check.status == "pass" for check in checks) else "failed"
    return AlgebraVerificationReport(status=status, checks=checks, method=["domain", "substitution"])


def verify_solution_set(problem: ParsedAlgebraProblem, solution_set: sp.Set) -> AlgebraVerificationReport:
    if problem.relation is None:
        return AlgebraVerificationReport(status="skipped", checks=[], method=[])
    checks = [AlgebraVerificationCheck(
        name="symbolic_solution_set",
        status="pass" if solution_set is not sp.EmptySet else "warn",
        detail="SymPy đã trả về tập nghiệm symbolic; kiểm chứng bằng biểu diễn tập nghiệm.",
        latex=sp.latex(solution_set),
    )]
    return AlgebraVerificationReport(status="verified" if solution_set is not sp.EmptySet else "partially_verified", checks=checks, method=["solveset"])


def _domain_checks(problem: ParsedAlgebraProblem, solutions: list[sp.Expr]) -> list[AlgebraVerificationCheck]:
    if problem.relation is None:
        return []
    expression = sp.simplify(problem.relation.lhs - problem.relation.rhs)
    variable = problem.variable
    checks: list[AlgebraVerificationCheck] = []
    domain_expressions = _domain_expressions(expression, variable)
    for solution in solutions:
        ok = all(_check_domain_expression(item, variable, solution) for item in domain_expressions)
        if domain_expressions:
            checks.append(AlgebraVerificationCheck(
                name="domain_constraints_valid",
                status="pass" if ok else "fail",
                detail=f"Nghiệm {sp.sstr(solution)} {'thỏa' if ok else 'không thỏa'} điều kiện xác định.",
                latex=f"{sp.latex(variable)} = {sp.latex(solution)}",
            ))
    return checks


def _domain_expressions(expression: sp.Expr, variable: sp.Symbol) -> list[tuple[sp.Expr, str]]:
    expressions: list[tuple[sp.Expr, str]] = []
    denominator = sp.denom(expression)
    if denominator != 1 and denominator.has(variable):
        expressions.append((denominator, "nonzero"))
    for power in expression.atoms(sp.Pow):
        if power.base.has(variable) and power.exp.is_Rational and power.exp.q % 2 == 0:
            expressions.append((power.base, "nonnegative"))
    for log_expr in expression.atoms(sp.log):
        arg = log_expr.args[0]
        if arg.has(variable):
            expressions.append((arg, "positive"))
        if len(log_expr.args) > 1:
            base = log_expr.args[1]
            if base.has(variable):
                expressions.append((base, "positive"))
                expressions.append((base - 1, "nonzero"))
    return expressions


def _check_domain_expression(constraint: tuple[sp.Expr, str], variable: sp.Symbol, value: sp.Expr) -> bool:
    expression, kind = constraint
    try:
        checked = sp.simplify(expression.subs(variable, value))
        if kind == "positive":
            return bool(checked > 0)
        if kind == "nonnegative":
            return bool(checked >= 0)
        return checked != 0
    except Exception:
        return False


def _check_relation(relation: sp.Relational, variable: sp.Symbol, value: sp.Expr) -> bool:
    try:
        substituted = relation.subs(variable, value)
        simplified = sp.simplify(substituted)
        if simplified is sp.S.true:
            return True
        if simplified is sp.S.false:
            return False
        return bool(simplified)
    except Exception:
        return False
