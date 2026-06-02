from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_trig_solver_solves_sine_on_default_interval():
    result = solve_algebra(AlgebraSolveRequest(input="sin(x)=1/2"))

    assert result.status == "solved"
    assert result.topic == "trigonometry"
    assert result.solution_set.kind == "finite"
    assert {value.text for value in result.solution_set.values} == {"pi/6", "5*pi/6"}
    assert result.verification.status == "verified"
    assert [step.title for step in result.steps[:3]] == ["Đưa về phương trình lượng giác cơ bản", "Viết nghiệm theo chu kỳ", "Lọc nghiệm trên khoảng chuẩn"]
    assert all(step.kind != "normalize" for step in result.steps)


def test_trig_solver_solves_cos_double_angle_on_default_interval():
    result = solve_algebra(AlgebraSolveRequest(input="cos(2*x)=1"))

    assert result.status == "solved"
    assert result.solution_set.kind == "finite"
    assert {value.text for value in result.solution_set.values} == {"0", "pi"}
    assert "Lọc nghiệm trên khoảng chuẩn" in [step.title for step in result.steps]
