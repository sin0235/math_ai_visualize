from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolveResponse, AlgebraSolveStep, AlgebraVerificationCheck, AlgebraVerificationReport
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step


def solve_system(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    if len(problem.relations) < 2:
        return _unsupported(problem, "Đầu vào chưa phải hệ phương trình.")
    if any(not isinstance(relation, sp.Equality) for relation in problem.relations):
        return _unsupported(problem, "Phase này chỉ hỗ trợ hệ phương trình.")
    variables = problem.variables or _infer_variables(problem.relations)
    expressions = [sp.simplify(relation.lhs - relation.rhs) for relation in problem.relations]
    steps: list[AlgebraSolveStep] = []
    try:
        solution_set = sp.linsolve(expressions, variables)
        method = "linsolve"
    except Exception:
        try:
            solution_set = sp.nonlinsolve(expressions, variables)
            method = "nonlinsolve"
        except Exception as exc:
            return _unsupported(problem, f"SymPy chưa giải được hệ này: {exc}")
    steps.extend(_linear_two_by_two_steps(problem.relations, expressions, variables, solution_set, len(steps) + 1))
    if not steps:
        steps.append(AlgebraSolveStep(
            index=len(steps) + 1,
            title="Giải hệ phương trình",
            explanation=f"Giải hệ theo các biến {', '.join(sp.sstr(variable) for variable in variables)}.",
            goal="Tìm bộ giá trị thỏa tất cả phương trình trong hệ.",
            why="Một nghiệm của hệ phải làm đúng từng phương trình cùng lúc.",
            rule="Giải hệ symbolic",
            operation=f"Dùng phương pháp {method} cho hệ chưa nhận ra dạng giải tay đơn giản.",
            expression="; ".join(sp.sstr(expr) for expr in expressions),
            expression_latex="; ".join(sp.latex(expr) for expr in expressions),
            result=sp.sstr(solution_set),
            result_latex=sp.latex(solution_set),
            kind="solve",
            confidence="symbolic",
        ))
    verification = _verify_system(problem.relations, variables, solution_set)
    answer = _format_system_solution(solution_set, variables)
    steps.append(conclusion_step(len(steps) + 1, answer, sp.latex(solution_set)))
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


def _linear_two_by_two_steps(relations: list[sp.Relational], expressions: list[sp.Expr], variables: list[sp.Symbol], solution_set: sp.Set, start_index: int) -> list[AlgebraSolveStep]:
    if len(relations) != 2 or len(variables) != 2 or not isinstance(solution_set, sp.FiniteSet) or len(solution_set) != 1:
        return []
    x, y = variables
    try:
        rows = [sp.Poly(expression, x, y) for expression in expressions]
    except sp.PolynomialError:
        return []
    if any(row.total_degree() > 1 for row in rows):
        return []
    a1, b1, c1 = _linear_coefficients(rows[0], x, y)
    a2, b2, c2 = _linear_coefficients(rows[1], x, y)
    if sp.simplify(a1 * b2 - a2 * b1) == 0:
        return []

    solution_tuple = next(iter(solution_set))
    if not isinstance(solution_tuple, sp.Tuple):
        solution_tuple = sp.Tuple(solution_tuple)
    x_value, y_value = solution_tuple
    standard_lines = [
        sp.latex(sp.Eq(a1 * x + b1 * y, -c1, evaluate=False)),
        sp.latex(sp.Eq(a2 * x + b2 * y, -c2, evaluate=False)),
    ]
    eliminated_left = sp.expand((a1 * b2 - a2 * b1) * x)
    eliminated_right = sp.expand((-c1 * b2) - (-c2 * b1))
    return [
        AlgebraSolveStep(
            index=start_index,
            title="Viết hệ dạng chuẩn",
            explanation="Đưa mỗi phương trình về dạng ax + by = c để chuẩn bị khử ẩn.",
            goal="Nhìn rõ hệ số của từng ẩn.",
            why="Khi các hệ số rõ ràng, ta có thể chọn nhân hai phương trình để cộng đại số.",
            rule="Dạng chuẩn hệ tuyến tính",
            operation="Chuyển hằng số sang vế phải và đọc hệ số của x, y.",
            before_latex="\n".join(sp.latex(relation) for relation in relations),
            after_latex="\n".join(standard_lines),
            pitfall="Phải giữ đúng dấu khi chuyển hằng số sang vế phải.",
            check="Chuyển ngược lại phải ra hệ ban đầu.",
            expression="; ".join(sp.sstr(expression) for expression in expressions),
            expression_latex="\n".join(standard_lines),
            result_latex="\n".join(standard_lines),
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 1,
            title="Khử một ẩn",
            explanation="Nhân hai phương trình với hệ số phù hợp rồi cộng lại để khử y.",
            goal="Tìm giá trị của một ẩn trước.",
            why="Nếu hệ số của y đối nhau, khi cộng hai phương trình thì y biến mất.",
            rule="Phương pháp cộng đại số",
            operation=f"Nhân phương trình đầu với {sp.sstr(b2)} và phương trình sau với {sp.sstr(-b1)}, rồi cộng hai phương trình.",
            before_latex="\n".join(standard_lines),
            after_latex=sp.latex(sp.Eq(eliminated_left, eliminated_right, evaluate=False)) + "\n" + sp.latex(sp.Eq(x, x_value, evaluate=False)),
            pitfall="Nếu nhân cả hai vế của một phương trình, phải nhân toàn bộ vế.",
            check="Sau khi cộng, hệ số của y phải bằng 0.",
            result=sp.sstr(x_value),
            result_latex=sp.latex(sp.Eq(x, x_value, evaluate=False)),
            kind="solve",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 2,
            title="Thế ngược tìm ẩn còn lại",
            explanation="Thay giá trị x vừa tìm được vào một phương trình ban đầu để tìm y.",
            goal="Hoàn tất nghiệm của hệ.",
            why="Một nghiệm hệ cần đủ giá trị của cả hai ẩn.",
            rule="Phương pháp thế",
            operation="Thay x vào phương trình đầu của hệ dạng chuẩn.",
            before_latex=standard_lines[0],
            after_latex=sp.latex(sp.Eq(a1 * x_value + b1 * y, -c1, evaluate=False)) + "\n" + sp.latex(sp.Eq(y, y_value, evaluate=False)),
            pitfall="Không được dừng sau khi tìm một ẩn.",
            check="Thay cả x và y vào cả hai phương trình của hệ.",
            result=f"{sp.sstr(x)}={sp.sstr(x_value)}; {sp.sstr(y)}={sp.sstr(y_value)}",
            result_latex=rf"{sp.latex(x)}={sp.latex(x_value)},\quad {sp.latex(y)}={sp.latex(y_value)}",
            kind="solve",
            confidence="symbolic",
        ),
    ]


def _linear_coefficients(poly: sp.Poly, x: sp.Symbol, y: sp.Symbol) -> tuple[sp.Expr, sp.Expr, sp.Expr]:
    return (
        poly.coeff_monomial(x),
        poly.coeff_monomial(y),
        poly.coeff_monomial(1),
    )


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
