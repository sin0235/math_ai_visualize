from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra
from app.services.algebra.solvers.sequence_solver import _evaluate


def test_arithmetic_u2():
    calc = _evaluate("arithmetic(u1=2,u2=4,n=9)")
    assert calc.result == 18
    assert calc.preamble is not None
    assert calc.preamble.title == "Tìm công sai"


def test_arithmetic_sum_u2():
    calc = _evaluate("arithmetic_sum(u1=2,u2=4,n=9)")
    assert calc.result == 90
    assert calc.preamble is not None


def test_geometric_u2():
    calc = _evaluate("geometric(u1=2,u2=4,n=9)")
    assert calc.result == 512
    assert calc.preamble is not None
    assert calc.preamble.title == "Tìm công bội"


def test_natural_language_arithmetic_u1_u2_u9():
    result = solve_algebra(AlgebraSolveRequest(
        input="với cấp số cộng với u1 = 2, u2 = 6, hỏi số hạng thứ 9 bằng bao nhiêu",
        topic="sequence",
    ))
    assert result.status == "solved"
    assert "34" in (result.answer or "") or result.answer_latex == "34"
