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

    assert result.status == "solved"
    assert result.topic == "statistics"
    assert result.normalized_input == "stats(data=1,2,3,4)"
    assert "mean=5/2" in result.answer


def test_grouped_statistics_estimates_quartiles_variance_and_outlier_bounds():
    result = solve_algebra(AlgebraSolveRequest(
        input="stats_grouped(intervals=0:10,10:20,20:30;freqs=2,5,3)",
        topic="statistics",
    ))

    assert result.status == "solved"
    assert result.problem_type == "descriptive_stats_grouped"
    assert "mean≈16" in result.answer
    assert "median≈16" in result.answer
    assert "variance≈49" in result.answer
    assert "Q1≈11" in result.answer
    assert result.verification.status == "partially_verified"
    assert {check.name for check in result.verification.checks} == {
        "grouped_frequency_total",
        "grouped_interval_order",
        "grouped_mean_recompute",
    }


def test_statistics_rejects_unsafe_tokens_and_invalid_grouped_contracts():
    unsafe = solve_algebra(AlgebraSolveRequest(input="stats(data=__import__(os))", topic="statistics"))
    overlap = solve_algebra(AlgebraSolveRequest(
        input="stats_grouped(intervals=0:10,5:15;freqs=2,3)",
        topic="statistics",
    ))
    fractional_frequency = solve_algebra(AlgebraSolveRequest(
        input="stats_grouped(intervals=0:10,10:20;freqs=2,3/2)",
        topic="statistics",
    ))

    assert unsafe.status == "unsupported"
    assert overlap.status == "unsupported"
    assert "chồng lấn" in overlap.answer
    assert fractional_frequency.status == "unsupported"
    assert "số nguyên" in fractional_frequency.answer
