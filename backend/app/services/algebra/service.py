from __future__ import annotations

from app.schemas.algebra import AlgebraSolveRequest, AlgebraSolveResponse
from app.services.algebra.classifier import classify_algebra_problem
from app.services.algebra.parser import AlgebraParseError, parse_algebra_problem
from app.services.algebra.solvers.complex_solver import solve_complex
from app.services.algebra.solvers.equation_solver import solve_equation
from app.services.algebra.solvers.exp_log_solver import solve_exp_log
from app.services.algebra.solvers.inequality_solver import solve_inequality
from app.services.algebra.solvers.system_solver import solve_system
from app.services.algebra.solvers.trig_solver import solve_trigonometry


def solve_algebra(request: AlgebraSolveRequest) -> AlgebraSolveResponse:
    try:
        problem = parse_algebra_problem(request.input, topic=request.topic, variables=request.variables or ["x"], domain=request.domain)
    except AlgebraParseError as exc:
        return AlgebraSolveResponse(
            input=request.input,
            normalized_input=request.input.strip(),
            topic=request.topic,
            problem_type="parse_error",
            status="error",
            answer="Không thể đọc đề bài đại số này.",
            errors=[str(exc)],
        )
    topic = classify_algebra_problem(problem)
    if topic == "equation":
        return solve_equation(problem)
    if topic == "inequality":
        return solve_inequality(problem)
    if topic == "exponential_log":
        return solve_exp_log(problem)
    if topic == "trigonometry":
        return solve_trigonometry(problem)
    if topic == "complex":
        return solve_complex(problem)
    if topic == "system":
        return solve_system(problem)
    return AlgebraSolveResponse(
        input=request.input,
        normalized_input=problem.normalized_input,
        topic=topic,
        problem_type="unsupported",
        status="unsupported",
        answer="Dạng bài này chưa được hỗ trợ trong phase đầu. Hiện hệ thống ưu tiên phương trình và bất phương trình một biến.",
        warnings=["Các nhóm mũ-log, lượng giác, số phức, hệ phương trình, cấp số, tổ hợp-xác suất và tham số sẽ được bổ sung ở các phase sau."],
    )
