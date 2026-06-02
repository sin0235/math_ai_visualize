from __future__ import annotations

import sympy as sp
from sympy.solvers.inequalities import solve_univariate_inequality

from app.schemas.algebra import AlgebraSolutionSet, AlgebraSolveResponse, AlgebraSolveStep
from app.services.algebra.domain import domain_assumptions_from_expression
from app.services.algebra.formatting import format_interval_set
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.sign_chart import sign_chart_summary
from app.services.algebra.steps import conclusion_step, domain_step
from app.services.algebra.verifier import verify_solution_set


def solve_inequality(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    if problem.relation is None or isinstance(problem.relation, sp.Equality):
        return _unsupported(problem, "Đầu vào không phải bất phương trình.")
    variable = problem.variable
    expression = sp.simplify(problem.relation.lhs - problem.relation.rhs)
    assumptions = domain_assumptions_from_expression(expression, variable)
    steps: list[AlgebraSolveStep] = []
    if assumptions:
        steps.append(domain_step(len(steps) + 1, assumptions))
    try:
        result_set = solve_univariate_inequality(problem.relation, variable, relational=False)
    except Exception as exc:
        return _unsupported(problem, f"SymPy chưa giải được bất phương trình này: {exc}")
    steps.append(AlgebraSolveStep(
        index=len(steps) + 1,
        title="Đưa bất phương trình về một vế",
        explanation="Đưa bất phương trình về dạng một biến rồi tìm khoảng nghiệm thỏa quan hệ đã cho.",
        goal="Tìm tập các giá trị làm bất phương trình đúng.",
        why="Bất phương trình thường không chỉ có vài nghiệm rời rạc mà là các khoảng trên trục số.",
        rule="Giải bất phương trình một biến",
        operation="Rút gọn quan hệ và giải trên miền nghiệm đã chọn.",
        before_latex=sp.latex(problem.relation),
        after_latex=sp.latex(result_set),
        pitfall="Không được xử lý bất phương trình như phương trình; khi nhân chia với biểu thức có thể đổi dấu thì phải xét dấu.",
        check="Kết quả phải là các khoảng mà mọi điểm đại diện đều thỏa bất phương trình gốc.",
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
            index=len(steps) + 1,
            title="Xét dấu biểu thức",
            explanation=sign_summary,
            goal="Giải thích vì sao các khoảng trong tập nghiệm được chọn.",
            why="Dấu của biểu thức chỉ có thể đổi tại nghiệm của tử, mẫu hoặc các mốc làm biểu thức không xác định.",
            rule="Bảng xét dấu",
            operation="Tìm các mốc tới hạn, chia trục số thành khoảng, rồi thử dấu trên từng khoảng.",
            before_latex=sp.latex(sp.factor(expression)),
            after_latex=sp.latex(result_set),
            pitfall="Mốc làm mẫu bằng 0 không được lấy vào tập nghiệm, kể cả khi là biên khoảng.",
            check="Chọn một số trong mỗi khoảng và thay vào bất phương trình gốc để kiểm tra dấu.",
            expression=sp.sstr(sp.factor(expression)),
            expression_latex=sp.latex(sp.factor(expression)),
            result=sp.sstr(result_set),
            result_latex=sp.latex(result_set),
            kind="verify",
            confidence="symbolic",
        ))
    verification = verify_solution_set(problem, result_set if isinstance(result_set, sp.Set) else sp.S.UniversalSet)
    answer = format_interval_set(result_set)
    steps.append(_inequality_verification_step(len(steps) + 1, verification.status, result_set))
    steps.append(conclusion_step(len(steps) + 1, answer, sp.latex(result_set)))
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


def _inequality_verification_step(index: int, status: str, result_set: sp.Set) -> AlgebraSolveStep:
    confidence = "verified" if status == "verified" else "symbolic" if status == "partially_verified" else "unverified"
    return AlgebraSolveStep(
        index=index,
        title="Kiểm tra tập nghiệm",
        explanation="Đối chiếu tập nghiệm symbolic với bất phương trình ban đầu.",
        goal="Xác nhận các khoảng nghiệm không bị chọn nhầm dấu hoặc sai biên.",
        why="Với bất phương trình, lỗi thường gặp là lấy nhầm khoảng hoặc quên loại điểm không xác định.",
        rule="Kiểm chứng tập nghiệm",
        operation="Dùng biểu diễn tập nghiệm để kiểm tra quan hệ và các biên khoảng.",
        after_latex=sp.latex(result_set),
        pitfall="Dấu ngoặc tròn/vuông ở biên khoảng phụ thuộc vào dấu <, <=, >, >= và điều kiện xác định.",
        check="Thử một điểm trong mỗi khoảng được chọn và một điểm ngoài tập nghiệm để so sánh.",
        result=sp.sstr(result_set),
        result_latex=sp.latex(result_set),
        kind="verify",
        confidence=confidence,
    )
