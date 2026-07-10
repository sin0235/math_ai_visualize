from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraVerificationCheck, AlgebraVerificationReport
from app.services.algebra.parser import ParsedAlgebraProblem


def verify_finite_solutions(problem: ParsedAlgebraProblem, solutions: list[sp.Expr]) -> AlgebraVerificationReport:
    checks: list[AlgebraVerificationCheck] = []
    if problem.relation is None:
        return AlgebraVerificationReport(
            status="skipped",
            checks=[AlgebraVerificationCheck(name="relation_present", status="skip", detail="Không có phương trình/bất phương trình để kiểm chứng.")],
            method=[],
        )
    checks.extend(_domain_checks(problem, solutions))
    relation = problem.relation
    variable = problem.variable
    for solution in solutions:
        outcome = _check_relation(relation, variable, solution)
        if outcome is None:
            checks.append(AlgebraVerificationCheck(
                name="candidate_substitution",
                status="warn",
                detail=f"Không kiểm chứng được {variable} = {sp.sstr(solution)} (lỗi engine/biểu thức chưa xác định).",
                latex=f"{sp.latex(variable)} = {sp.latex(solution)}",
            ))
        else:
            checks.append(AlgebraVerificationCheck(
                name="candidate_substitution",
                status="pass" if outcome else "fail",
                detail=f"Thay {variable} = {sp.sstr(solution)} vào biểu thức gốc {'đúng' if outcome else 'không đúng'}.",
                latex=f"{sp.latex(variable)} = {sp.latex(solution)}",
            ))
    if not solutions:
        empty_checks = _empty_set_independent_checks(problem)
        checks.extend(empty_checks)
        if any(check.status == "fail" for check in checks):
            status = "failed"
        elif empty_checks and all(check.status == "pass" for check in empty_checks if check.name.startswith("empty_")):
            # Sample corroboration only — not a full algebraic proof of unsatisfiability.
            status = "partially_verified"
        else:
            status = "partially_verified"
        return AlgebraVerificationReport(status=status, checks=checks, method=["domain", "substitution", "empty_set_samples"])
    if any(check.status == "fail" for check in checks):
        status = "failed"
    elif any(check.status == "warn" for check in checks):
        status = "partially_verified"
    elif checks and all(check.status == "pass" for check in checks):
        status = "verified"
    else:
        status = "partially_verified"
    return AlgebraVerificationReport(status=status, checks=checks, method=["domain", "substitution"])


def verify_solution_set(problem: ParsedAlgebraProblem, solution_set: sp.Set) -> AlgebraVerificationReport:
    """Symbolic set check — never claim fully verified solely because the set is non-empty."""
    if problem.relation is None:
        return AlgebraVerificationReport(status="skipped", checks=[], method=[])
    checks: list[AlgebraVerificationCheck] = []
    if isinstance(solution_set, sp.ConditionSet):
        checks.append(AlgebraVerificationCheck(
            name="condition_set_detected",
            status="warn",
            detail="Kết quả còn dạng ConditionSet (chưa rút gọn tường minh); không coi là đã kiểm chứng đầy đủ.",
            latex=sp.latex(solution_set),
        ))
        return AlgebraVerificationReport(status="partially_verified", checks=checks, method=["solveset"])
    if solution_set is sp.EmptySet:
        empty_checks = _empty_set_independent_checks(problem)
        checks.extend(empty_checks)
        if any(check.status == "fail" for check in checks):
            status = "failed"
        else:
            status = "partially_verified"
        return AlgebraVerificationReport(status=status, checks=checks, method=["solveset", "empty_set_samples"])
    if _is_unevaluated_set(solution_set):
        checks.append(AlgebraVerificationCheck(
            name="unevaluated_solution_set",
            status="warn",
            detail="Tập nghiệm symbolic chưa evaluate đầy đủ; chỉ kiểm chứng một phần.",
            latex=sp.latex(solution_set),
        ))
        return AlgebraVerificationReport(status="partially_verified", checks=checks, method=["solveset"])
    checks.append(AlgebraVerificationCheck(
        name="symbolic_solution_set",
        status="warn",
        detail="SymPy trả tập nghiệm symbolic; chưa thay số/chứng minh độc lập — đánh dấu partially_verified.",
        latex=sp.latex(solution_set),
    ))
    return AlgebraVerificationReport(status="partially_verified", checks=checks, method=["solveset"])


def verify_inequality_solution_set(problem: ParsedAlgebraProblem, solution_set: sp.Set, samples: list[sp.Expr]) -> AlgebraVerificationReport:
    if problem.relation is None:
        return AlgebraVerificationReport(status="skipped", checks=[], method=[])
    checks: list[AlgebraVerificationCheck] = []
    if isinstance(solution_set, sp.ConditionSet):
        checks.append(AlgebraVerificationCheck(
            name="condition_set_detected",
            status="warn",
            detail="Bất phương trình còn ConditionSet; chưa kiểm chứng độc lập.",
            latex=sp.latex(solution_set),
        ))
        return AlgebraVerificationReport(status="partially_verified", checks=checks, method=["solveset"])

    checks.append(AlgebraVerificationCheck(
        name="symbolic_solution_set",
        status="pass" if solution_set is not None else "warn",
        detail="Đã có tập nghiệm symbolic từ solver bất phương trình.",
        latex=sp.latex(solution_set),
    ))
    relations = _problem_relations(problem)
    sample_checked = 0
    for sample in samples[:8]:
        try:
            in_set = _point_in_solution_set(solution_set, sample)
            relation_ok = _check_all_relations(relations, problem.variable, sample)
        except Exception:
            checks.append(AlgebraVerificationCheck(
                name="inequality_sample",
                status="warn",
                detail=f"Không kiểm chứng được điểm {problem.variable} = {sp.sstr(sample)}.",
                latex=rf"{sp.latex(problem.variable)}={sp.latex(sample)}",
            ))
            continue
        if relation_ok is None:
            checks.append(AlgebraVerificationCheck(
                name="inequality_sample",
                status="warn",
                detail=f"Không xác định quan hệ tại {problem.variable} = {sp.sstr(sample)}.",
                latex=rf"{sp.latex(problem.variable)}={sp.latex(sample)}",
            ))
            continue
        sample_checked += 1
        checks.append(AlgebraVerificationCheck(
            name="inequality_sample",
            status="pass" if in_set == relation_ok else "fail",
            detail=(
                f"Thử {problem.variable} = {sp.sstr(sample)}: "
                f"{'thuộc' if in_set else 'không thuộc'} tập nghiệm và "
                f"bất phương trình gốc {'đúng' if relation_ok else 'sai'}."
            ),
            latex=rf"{sp.latex(problem.variable)}={sp.latex(sample)}",
        ))
    if any(check.status == "fail" for check in checks):
        status = "failed"
    elif sample_checked >= 2 and all(check.status != "fail" for check in checks) and not any(check.status == "warn" and check.name == "inequality_sample" for check in checks):
        # Sample cross-check only — not independent proof; never claim full verified.
        status = "partially_verified"
        checks.append(AlgebraVerificationCheck(
            name="sample_only_scope",
            status="warn",
            detail="Kiểm chứng bằng điểm mẫu; không thay thế bảng xét dấu/chứng minh đầy đủ.",
        ))
    else:
        status = "partially_verified"
    return AlgebraVerificationReport(status=status, checks=checks, method=["solveset", "sample_substitution"])


def _problem_relations(problem: ParsedAlgebraProblem) -> list[sp.Relational]:
    if problem.relations:
        return [rel for rel in problem.relations if rel is not None]
    if problem.relation is not None:
        return [problem.relation]
    return []


def _check_all_relations(relations: list[sp.Relational], variable: sp.Symbol, value: sp.Expr) -> bool | None:
    """All relations must hold (And) for multi/chained inequalities."""
    if not relations:
        return None
    outcomes: list[bool] = []
    for relation in relations:
        outcome = _check_relation(relation, variable, value)
        if outcome is None:
            return None
        outcomes.append(outcome)
    return all(outcomes)


def _is_unevaluated_set(solution_set: sp.Set) -> bool:
    # Reserved for future unevaluated-set detection beyond ConditionSet.
    return False


def _empty_set_independent_checks(problem: ParsedAlgebraProblem) -> list[AlgebraVerificationCheck]:
    """Corroborate EmptySet by sampling; never claim full algebraic unsat proof."""
    checks: list[AlgebraVerificationCheck] = [
        AlgebraVerificationCheck(
            name="empty_solution_set",
            status="pass",
            detail="Solver trả tập rỗng (vô nghiệm theo pipeline); kiểm chứng độc lập bằng mẫu.",
            latex=r"\emptyset",
        )
    ]
    relations = _problem_relations(problem)
    if not relations:
        checks.append(AlgebraVerificationCheck(
            name="empty_set_sample_corroboration",
            status="warn",
            detail="Không có quan hệ gốc để lấy mẫu kiểm chứng vô nghiệm.",
        ))
        return checks

    samples = _empty_set_probe_samples(problem)
    checked = 0
    for sample in samples:
        # Interval-filtered EmptySet is only contradicted by points inside the interval.
        in_interval = _sample_in_solve_interval(problem, sample)
        if in_interval is False:
            continue
        if in_interval is None:
            continue
        outcome = _check_all_relations(relations, problem.variable, sample)
        if outcome is None:
            continue
        checked += 1
        if outcome:
            checks.append(AlgebraVerificationCheck(
                name="empty_set_counterexample",
                status="fail",
                detail=(
                    f"Phát hiện điểm {problem.variable}={sp.sstr(sample)} thỏa đề gốc "
                    "nhưng solver báo vô nghiệm — kết quả không tin cậy."
                ),
                latex=rf"{sp.latex(problem.variable)}={sp.latex(sample)}",
            ))
            return checks

    if checked >= 3:
        checks.append(AlgebraVerificationCheck(
            name="empty_set_sample_corroboration",
            status="pass",
            detail=(
                f"Đã thử {checked} điểm mẫu; không điểm nào thỏa đề gốc. "
                "Đây là củng cố mẫu, chưa phải chứng minh đại số đầy đủ."
            ),
        ))
        checks.append(AlgebraVerificationCheck(
            name="empty_set_not_full_proof",
            status="warn",
            detail="Vô nghiệm được củng cố bằng mẫu; status kiểm chứng chỉ đạt partially_verified.",
        ))
    else:
        checks[0] = AlgebraVerificationCheck(
            name="empty_solution_set",
            status="warn",
            detail="Solver trả tập rỗng; chưa lấy được đủ mẫu độc lập để củng cố vô nghiệm.",
            latex=r"\emptyset",
        )
        checks.append(AlgebraVerificationCheck(
            name="empty_set_sample_corroboration",
            status="warn",
            detail="Mẫu kiểm chứng vô nghiệm chưa đủ (cần ≥3 điểm xác định được).",
        ))
    return checks


def _sample_in_solve_interval(problem: ParsedAlgebraProblem, sample: sp.Expr) -> bool | None:
    """True if sample is admissible under solve_interval (or no interval is set)."""
    if problem.solve_interval is None:
        return True
    try:
        return bool(problem.solve_interval.contains(sample))
    except Exception:
        return None


def _empty_set_probe_samples(problem: ParsedAlgebraProblem) -> list[sp.Expr]:
    """Deterministic probe points for empty-set corroboration.

    When solve_interval is set, only probe inside that interval so roots outside
    the interval cannot falsely contradict an interval-filtered empty answer.
    """
    global_base = [
        sp.Integer(0),
        sp.Integer(1),
        sp.Integer(-1),
        sp.Integer(2),
        sp.Integer(-2),
        sp.Rational(1, 2),
        sp.Rational(-1, 2),
        sp.Integer(3),
        sp.Integer(5),
        sp.Integer(10),
    ]
    base: list[sp.Expr]
    if problem.solve_interval is not None:
        interval = problem.solve_interval
        base = []
        try:
            if isinstance(interval, sp.Interval):
                start, end = interval.start, interval.end
                if start.is_finite and end.is_finite:
                    mid = sp.simplify((start + end) / 2)
                    # Interior probes; avoid endpoints if open.
                    candidates = [mid, sp.simplify((start + mid) / 2), sp.simplify((mid + end) / 2)]
                    if not interval.left_open and start.is_finite:
                        candidates.insert(0, start)
                    if not interval.right_open and end.is_finite:
                        candidates.append(end)
                    # Dense-ish grid for wider intervals
                    try:
                        width = sp.simplify(end - start)
                        if width.is_number and width > 0:
                            for k in range(1, 6):
                                candidates.append(sp.simplify(start + width * sp.Rational(k, 6)))
                    except Exception:
                        pass
                    base = candidates
                elif start.is_finite:
                    base = [start + i for i in (0, 1, 2, 3, 5, 10)]
                elif end.is_finite:
                    base = [end - i for i in (0, 1, 2, 3, 5, 10)]
        except Exception:
            base = []
        if not base:
            # Fallback: filter global probes to those inside the interval.
            base = [s for s in global_base if _sample_in_solve_interval(problem, s) is True]
    else:
        base = list(global_base)
    # Deduplicate while preserving order
    seen: set[str] = set()
    out: list[sp.Expr] = []
    for sample in base:
        key = sp.sstr(sample)
        if key in seen:
            continue
        seen.add(key)
        out.append(sample)
    return out[:12]


def _domain_checks(problem: ParsedAlgebraProblem, solutions: list[sp.Expr]) -> list[AlgebraVerificationCheck]:
    if problem.relation is None:
        return []
    expression = problem.relation.lhs - problem.relation.rhs
    variable = problem.variable
    checks: list[AlgebraVerificationCheck] = []
    domain_expressions = _domain_expressions(expression, variable)
    for solution in solutions:
        outcomes = [_check_domain_expression(item, variable, solution) for item in domain_expressions]
        if not domain_expressions:
            continue
        if any(outcome is None for outcome in outcomes):
            checks.append(AlgebraVerificationCheck(
                name="domain_constraints_valid",
                status="warn",
                detail=f"Không kiểm tra đủ điều kiện xác định cho nghiệm {sp.sstr(solution)}.",
                latex=f"{sp.latex(variable)} = {sp.latex(solution)}",
            ))
        else:
            ok = all(outcomes)
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


def _check_domain_expression(constraint: tuple[sp.Expr, str], variable: sp.Symbol, value: sp.Expr) -> bool | None:
    expression, kind = constraint
    try:
        checked = sp.simplify(expression.subs(variable, value))
        if kind == "positive":
            return bool(checked > 0)
        if kind == "nonnegative":
            return bool(checked >= 0)
        return checked != 0
    except Exception:
        return None


def _check_relation(relation: sp.Relational, variable: sp.Symbol, value: sp.Expr) -> bool | None:
    try:
        substituted = relation.subs(variable, value)
        simplified = sp.simplify(substituted)
        if simplified is sp.S.true:
            return True
        if simplified is sp.S.false:
            return False
        return bool(simplified)
    except Exception:
        return None


def _point_in_solution_set(solution_set: sp.Set, point: sp.Expr) -> bool:
    try:
        return bool(solution_set.contains(point))
    except Exception:
        return False
