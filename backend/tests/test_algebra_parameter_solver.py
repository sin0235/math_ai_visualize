from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_parameter_solver_finds_quadratic_double_root_condition():
    result = solve_algebra(AlgebraSolveRequest(input="quadratic_double_root(a=1,b=-2*m,c=1,var=x,param=m)", topic="parameter"))

    assert result.status == "solved"
    assert result.topic == "parameter"
    assert result.solution_set.kind == "conditions"
    assert "1" in result.solution_set.text
    assert "-1" in result.solution_set.text
    assert result.verification.status == "verified"


def test_parameter_solver_finds_quadratic_two_distinct_roots_condition():
    result = solve_algebra(AlgebraSolveRequest(input="quadratic_has_two_roots(a=1,b=m,c=1,var=x,param=m)", topic="parameter"))

    assert result.status == "solved"
    assert result.solution_set.kind == "conditions"
    assert "-2" in result.solution_set.text
    assert "2" in result.solution_set.text
    assert result.verification.status == "verified"


def test_parameter_solver_finds_quadratic_positive_all_condition():
    result = solve_algebra(AlgebraSolveRequest(input="quadratic_positive_all(a=1,b=m,c=1,var=x,param=m)", topic="parameter"))

    assert result.status == "solved"
    assert result.solution_set.kind == "conditions"
    assert "m > -2" in result.solution_set.text
    assert "m < 2" in result.solution_set.text
    assert result.verification.status == "verified"


def test_parameter_solver_auto_detects_structured_template():
    result = solve_algebra(AlgebraSolveRequest(input="quadratic_has_real_root(a=1,b=m,c=1,var=x,param=m)", topic="auto"))

    assert result.status == "solved"
    assert result.topic == "parameter"
    assert result.input_interpretation is not None
    assert result.input_interpretation.topic_hint == "parameter"
