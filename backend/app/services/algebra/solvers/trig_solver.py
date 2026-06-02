from __future__ import annotations

import sympy as sp

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolutionValue, AlgebraSolveResponse, AlgebraSolveStep, AlgebraVerificationCheck, AlgebraVerificationReport
from app.services.algebra.domain import domain_assumptions_from_expression
from app.services.algebra.formatting import format_solution_set, solution_values
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step, domain_step
from app.services.algebra.trig_transformations import build_trig_steps, trig_domain_assumptions
from app.services.algebra.verifier import verify_finite_solutions, verify_solution_set

TRIG_FUNCTIONS = (sp.sin, sp.cos, sp.tan, sp.cot)
INVERSE_TRIG_FUNCTIONS = (sp.asin, sp.acos, sp.atan, sp.acot)


def solve_trigonometry(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    if problem.relation is None and problem.expression is not None:
        return _solve_trig_expression(problem)
    if problem.relation is None or not isinstance(problem.relation, sp.Equality):
        return _unsupported(problem, "Đầu vào không phải phương trình lượng giác.")
    variable = problem.variable
    expression = problem.relation.lhs - problem.relation.rhs
    simplified_expression = sp.simplify(expression)
    if not any(expression.has(func) for func in TRIG_FUNCTIONS):
        return _unsupported(problem, "Phương trình không chứa hàm lượng giác được hỗ trợ.")
    assumptions = _unique(domain_assumptions_from_expression(expression, variable) + trig_domain_assumptions(expression, variable))
    steps: list[AlgebraSolveStep] = []
    if assumptions:
        steps.append(domain_step(len(steps) + 1, assumptions))
    solution_set = _solve_on_default_interval(simplified_expression, variable)
    if solution_set is None:
        try:
            solution_set = sp.solveset(simplified_expression, variable, domain=sp.S.Reals)
        except Exception as exc:
            return _unsupported(problem, f"SymPy chưa giải được phương trình lượng giác này: {exc}")
        solve_explanation = "Hệ thống giải phương trình lượng giác trên miền số thực. Với nghiệm tuần hoàn, kết quả có thể ở dạng tập symbolic."
    else:
        solve_explanation = "Hệ thống giải phương trình lượng giác trên khoảng chuẩn [0, 2*pi) để tạo nghiệm hữu hạn dễ kiểm chứng."
    values = solution_values(solution_set)
    method_steps = build_trig_steps(problem, expression, solution_set, values, len(steps) + 1)
    if method_steps:
        steps.extend(method_steps)
    else:
        steps.append(AlgebraSolveStep(
            index=len(steps) + 1,
            title="Giải phương trình lượng giác",
            explanation=solve_explanation,
            goal="Tìm các góc thỏa phương trình.",
            why="Phương trình lượng giác thường có nghiệm theo chu kỳ.",
            rule="Giải lượng giác một biến",
            operation="Giải trên khoảng chuẩn hoặc biểu diễn nghiệm tuần hoàn.",
            expression=sp.sstr(simplified_expression),
            expression_latex=sp.latex(simplified_expression),
            result=sp.sstr(solution_set),
            result_latex=sp.latex(solution_set),
            kind="solve",
            confidence="symbolic",
        ))
    answer = format_solution_set(solution_set)
    solution = AlgebraSolutionSet(
        kind="empty" if solution_set is sp.EmptySet else "finite" if values is not None else "periodic",
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


def _basic_trig_steps(problem: ParsedAlgebraProblem, expression: sp.Expr, variable: sp.Symbol, solution_set: sp.Set, values: list[sp.Expr] | None, start_index: int) -> list[AlgebraSolveStep]:
    parsed = _basic_trig_relation(problem, variable)
    if parsed is None or values is None:
        return []
    func, argument, target = parsed
    function_name = func.__name__
    general_latex = _basic_trig_general_latex(func, argument, target)
    return [
        AlgebraSolveStep(
            index=start_index,
            title="Đưa về phương trình lượng giác cơ bản",
            explanation=f"Nhận dạng phương trình dạng {function_name}(u) = a.",
            goal="Tách phần góc và giá trị lượng giác cần đạt.",
            why="Các phương trình lượng giác cơ bản có công thức nghiệm theo chu kỳ.",
            rule="Phương trình lượng giác cơ bản",
            operation="Đặt u bằng biểu thức trong hàm lượng giác.",
            before_latex=sp.latex(problem.relation),
            after_latex=rf"u={sp.latex(argument)}" + "\n" + sp.latex(sp.Eq(func(sp.Symbol("u")), target, evaluate=False)),
            pitfall="Nếu góc là 2x hoặc x+a, phải giải tiếp phương trình theo x.",
            check="Thay u ngược lại phải ra phương trình ban đầu.",
            expression=sp.sstr(expression),
            expression_latex=sp.latex(expression),
            result_latex=sp.latex(sp.Eq(func(argument), target, evaluate=False)),
            kind="transform",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 1,
            title="Viết nghiệm theo chu kỳ",
            explanation="Dùng nghiệm cơ bản của hàm lượng giác và chu kỳ để mô tả các nghiệm có thể có.",
            goal="Không bỏ sót nghiệm do tính tuần hoàn.",
            why="Sin, cos, tan lặp lại giá trị theo chu kỳ nên thường có nhiều nghiệm.",
            rule="Chu kỳ lượng giác",
            operation="Viết nghiệm tổng quát rồi lọc theo khoảng chuẩn.",
            before_latex=sp.latex(sp.Eq(func(argument), target, evaluate=False)),
            after_latex=general_latex,
            pitfall="Không chỉ lấy một góc đặc biệt khi còn nghiệm đối xứng hoặc nghiệm theo chu kỳ.",
            check="Các nghiệm đại diện phải cho đúng giá trị lượng giác ban đầu.",
            result_latex=general_latex,
            kind="solve",
            confidence="symbolic",
        ),
        AlgebraSolveStep(
            index=start_index + 2,
            title="Lọc nghiệm trên khoảng chuẩn",
            explanation="Giữ các nghiệm thuộc khoảng [0, 2π) để có tập nghiệm hữu hạn dễ kiểm tra.",
            goal="Viết nghiệm cụ thể trên khoảng đang xét.",
            why="Nếu không giới hạn khoảng, nghiệm lượng giác thường là vô hạn theo chu kỳ.",
            rule="Lọc nghiệm theo khoảng",
            operation="Chọn các nghiệm x thỏa 0 <= x < 2π.",
            before_latex=general_latex,
            after_latex=sp.latex(solution_set),
            pitfall="Điểm 2π không thuộc khoảng [0, 2π).",
            check="Từng nghiệm giữ lại phải nằm trong khoảng và thỏa phương trình gốc.",
            result="; ".join(sp.sstr(value) for value in values),
            result_latex=sp.latex(solution_set),
            kind="verify",
            confidence="verified",
        ),
    ]


def _basic_trig_relation(problem: ParsedAlgebraProblem, variable: sp.Symbol) -> tuple[object, sp.Expr, sp.Expr] | None:
    if problem.relation is None:
        return None
    lhs, rhs = problem.relation.lhs, problem.relation.rhs
    for func in TRIG_FUNCTIONS:
        if lhs.func is func and not rhs.has(variable):
            return func, lhs.args[0], rhs
        if rhs.func is func and not lhs.has(variable):
            return func, rhs.args[0], lhs
    return None


def _basic_trig_general_latex(func, argument: sp.Expr, target: sp.Expr) -> str:
    k = sp.Symbol("k", integer=True)
    if func is sp.sin:
        alpha = sp.asin(target)
        return "\n".join([
            sp.latex(sp.Eq(argument, alpha + 2 * k * sp.pi, evaluate=False)),
            sp.latex(sp.Eq(argument, sp.pi - alpha + 2 * k * sp.pi, evaluate=False)),
        ])
    if func is sp.cos:
        alpha = sp.acos(target)
        return "\n".join([
            sp.latex(sp.Eq(argument, alpha + 2 * k * sp.pi, evaluate=False)),
            sp.latex(sp.Eq(argument, -alpha + 2 * k * sp.pi, evaluate=False)),
        ])
    if func is sp.tan:
        alpha = sp.atan(target)
        return sp.latex(sp.Eq(argument, alpha + k * sp.pi, evaluate=False))
    return sp.latex(sp.Eq(func(argument), target, evaluate=False))


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(input=problem.raw_input, normalized_input=problem.normalized_input, topic="trigonometry", problem_type="solve_trigonometric_equation", status="unsupported", answer=message, errors=[message])


def _solve_trig_expression(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    expression = problem.expression
    if expression is None:
        return _unsupported(problem, "Không có biểu thức lượng giác để tính.")
    result = sp.simplify(expression)
    expression_latex = _inverse_trig_latex(expression)
    result_latex = _inverse_trig_latex(result)
    steps = [
        AlgebraSolveStep(
            index=1,
            title="Nhận dạng biểu thức lượng giác",
            explanation="Đầu vào là biểu thức lượng giác, không phải phương trình cần tìm nghiệm.",
            short_explanation="Tính giá trị/rút gọn biểu thức lượng giác.",
            detail_level="brief",
            method="trig_expression_value",
            goal="Tính giá trị chính xác của biểu thức.",
            why="Các biểu thức như arctan(1) có thể tính trực tiếp bằng giá trị lượng giác đặc biệt.",
            rule="Giá trị lượng giác đặc biệt",
            operation="Đọc biểu thức và xác định công thức cần dùng.",
            before_latex=expression_latex,
            after_latex=result_latex,
            check="Kết quả phải là giá trị chính xác nếu có thể.",
            expression=sp.sstr(expression),
            expression_latex=expression_latex,
            result=sp.sstr(result),
            result_latex=result_latex,
            kind="solve",
            confidence="verified",
        )
    ]
    answer = f"Giá trị: {sp.sstr(result)}"
    verification = AlgebraVerificationReport(
        status="verified",
        checks=[AlgebraVerificationCheck(name="trig_expression_symbolic", status="pass", detail="Biểu thức lượng giác được rút gọn symbolic.", latex=result_latex)],
        method=["sympy.simplify"],
    )
    steps.append(conclusion_step(2, answer, result_latex))
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="trigonometry",
        problem_type="evaluate_trigonometric_expression",
        status="solved",
        answer=answer,
        answer_latex=result_latex,
        solution_set=AlgebraSolutionSet(kind="expression", text=sp.sstr(result), latex=result_latex),
        steps=steps,
        verification=verification,
    )


def _inverse_trig_latex(expression: sp.Expr) -> str:
    return sp.latex(expression, inv_trig_style="full")


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
