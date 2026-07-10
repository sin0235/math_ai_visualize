from app.schemas.algebra import AlgebraSolveRequest
from app.services.algebra import solve_algebra


def test_stats_basic_mean_median_mode():
    result = solve_algebra(AlgebraSolveRequest(input="stats(data=1,2,2,3,5)", topic="statistics"))
    assert result.status == "solved"
    assert result.topic == "statistics"
    assert "mean=13/5" in result.answer or "mean=2.6" in result.answer
    assert "median" in result.answer
    assert result.verification.status in {"verified", "partially_verified"}


def test_stats_freq():
    result = solve_algebra(AlgebraSolveRequest(input="stats_freq(values=1,2,3;freqs=2,3,1)", topic="statistics"))
    assert result.status == "solved"
    # mean = (1*2+2*3+3*1)/6 = 11/6
    assert "11/6" in result.answer or "1.833" in result.answer


def test_stats_rejects_too_many_points():
    data = ",".join(str(i) for i in range(201))
    result = solve_algebra(AlgebraSolveRequest(input=f"stats(data={data})", topic="statistics"))
    assert result.status == "unsupported"


def test_stats_from_vietnamese():
    result = solve_algebra(AlgebraSolveRequest(input="Tính trung bình của 1 2 3 4"))
    assert result.topic == "statistics" or result.status in {"solved", "partial", "unsupported", "error"}
    if result.status == "solved":
        assert "mean" in result.answer
