from __future__ import annotations

from dataclasses import replace

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
    if not any(expression.has(func) for func in TRIG_FUNCTIONS):
        return _unsupported(problem, "Phương trình không chứa hàm lượng giác được hỗ trợ.")
    angle_unit = getattr(problem, "angle_unit", "radian") or "radian"
    work_expression = expression
    if angle_unit == "degree":
        # Interpret variable as degrees: solve f(x·π/180)=0 so solutions are in degrees.
        work_expression = expression.subs(variable, variable * sp.pi / 180)
    simplified_expression = sp.simplify(work_expression)
    assumptions = _unique(domain_assumptions_from_expression(expression, variable) + trig_domain_assumptions(expression, variable))
    if angle_unit == "degree":
        assumptions = [*assumptions, "Góc tính theo độ (°); biến được quy đổi x·π/180 khi giải."]

    milestones: list[str] = []
    if problem.relation is not None:
        milestones.append(f"Phương trình gốc: {sp.latex(problem.relation)}")

    steps: list[AlgebraSolveStep] = []
    if assumptions:
        steps.append(domain_step(len(steps) + 1, assumptions))

    # Default: general solution on R. When solve_interval is set, solve/filter on that interval.
    # Interval bounds are interpreted in the same unit as angle_unit (degrees if degree mode).
    try:
        if problem.solve_interval is not None and isinstance(problem.solve_interval, sp.Interval):
            solution_set = sp.solveset(simplified_expression, variable, domain=problem.solve_interval)
        else:
            solution_set = sp.solveset(simplified_expression, variable, domain=sp.S.Reals)
            if problem.solve_interval is not None:
                solution_set = solution_set.intersect(problem.solve_interval)
    except Exception as exc:
        return _unsupported(problem, f"SymPy chưa giải được phương trình lượng giác này: {exc}")
    if isinstance(solution_set, sp.ConditionSet):
        return _unsupported(problem, "Phương trình lượng giác này chưa được rút gọn thành tập nghiệm tường minh (ConditionSet).")

    if problem.solve_interval is not None:
        solve_explanation = "Hệ thống giải phương trình lượng giác trên khoảng người dùng chọn và liệt kê nghiệm trong khoảng đó."
        assumptions.append(f"Khoảng nghiệm: {sp.latex(problem.solve_interval)}")
    else:
        solve_explanation = "Hệ thống giải phương trình lượng giác trên miền số thực và trả nghiệm tổng quát (theo chu kỳ) khi có."
    values = solution_values(solution_set)
    method_steps = build_trig_steps(problem, expression, solution_set, values, len(steps) + 1)
    if method_steps:
        steps.extend(method_steps)
    else:
        steps.append(AlgebraSolveStep(
            index=len(steps) + 1,
            title="Giải phương trình lượng giác",
            explanation=solve_explanation,
            goal="Tìm các góc thỏa phương trình trên miền R.",
            why="Phương trình lượng giác thường có nghiệm theo chu kỳ.",
            rule="Giải lượng giác một biến trên R",
            operation="Biểu diễn nghiệm tổng quát hoặc tập nghiệm symbolic.",
            expression=sp.sstr(simplified_expression),
            expression_latex=sp.latex(simplified_expression),
            result=sp.sstr(solution_set),
            result_latex=sp.latex(solution_set),
            kind="solve",
            confidence="symbolic",
        ))
    answer = format_solution_set(solution_set)
    solution_kind = _solution_kind(solution_set, values)
    solution = AlgebraSolutionSet(
        kind=solution_kind,
        text=answer,
        latex=sp.latex(solution_set),
        values=[AlgebraSolutionValue(text=sp.sstr(value), latex=sp.latex(value), approximate=str(sp.N(value, 8))) for value in values or []],
    )
    verify_problem = _degree_aware_verify_problem(problem, variable, angle_unit)
    verification = (
        verify_finite_solutions(verify_problem, values)
        if values is not None
        else verify_solution_set(verify_problem, solution_set)
    )
    status = "solved" if verification.status in {"verified", "partially_verified"} else "error"
    steps.append(conclusion_step(len(steps) + 1, answer, sp.latex(solution_set)))
    if values is not None and len(values) > 0:
        roots_latex = ", ".join(sp.latex(sp.Eq(variable, val, evaluate=False)) for val in values)
        milestones.append(f"Tập nghiệm: {roots_latex}")
    else:
        milestones.append(f"Tập nghiệm: {sp.latex(solution_set)}")

    warnings: list[str] = []
    if angle_unit == "degree":
        warnings.append("Đang giải theo đơn vị độ (°); nghiệm x là số đo góc theo độ.")
    if values is None and problem.solve_interval is None:
        warnings.append("Nghiệm lượng giác trên R được biểu diễn dạng tổng quát/symbolic; kiểm chứng ở mức tập nghiệm.")
    if problem.solve_interval is not None and values is not None:
        warnings.append("Nghiệm đã được lọc theo khoảng người dùng chọn (không phải nghiệm tổng quát trên R).")
    if solution_set == sp.S.Reals:
        warnings.append("Phương trình đúng với mọi x thuộc miền xác định trên R.")

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
        milestones=milestones,
        verification=verification,
        assumptions=assumptions,
        warnings=warnings,
        errors=[] if status == "solved" else ["Kiểm chứng nghiệm lượng giác thất bại."],
    )


def _degree_aware_verify_problem(
    problem: ParsedAlgebraProblem,
    variable: sp.Symbol,
    angle_unit: str,
) -> ParsedAlgebraProblem:
    """Rewrite relations so degree-valued roots substitute as radians into trig functions."""
    if angle_unit != "degree":
        return problem
    scale = variable * sp.pi / 180

    def _scale_rel(rel: sp.Relational | None) -> sp.Relational | None:
        if rel is None:
            return None
        return rel.subs(variable, scale)

    relations = [_scale_rel(rel) for rel in problem.relations]
    relations = [rel for rel in relations if rel is not None]
    return replace(
        problem,
        relation=_scale_rel(problem.relation),
        relations=relations or problem.relations,
    )


def _solution_kind(solution_set: sp.Set, values: list[sp.Expr] | None) -> str:
    if solution_set is sp.EmptySet:
        return "empty"
    if values is not None:
        return "finite"
    if solution_set == sp.S.Reals:
        return "set"
    if isinstance(solution_set, sp.Interval):
        return "interval"
    if isinstance(solution_set, (sp.ImageSet, sp.Union)):
        return "periodic"
    return "periodic"


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
