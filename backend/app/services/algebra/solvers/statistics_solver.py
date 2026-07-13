"""Descriptive statistics for algebra-solver (1D data + frequency tables).

Uses stdlib ``statistics`` and SymPy Rational for exact means.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

import sympy as sp

from app.schemas.algebra import (
    AlgebraSolutionSet,
    AlgebraSolveResponse,
    AlgebraSolveStep,
    AlgebraVerificationCheck,
    AlgebraVerificationReport,
)
from app.services.algebra.parser import ParsedAlgebraProblem
from app.services.algebra.steps import conclusion_step, normalize_step

MAX_DATA_POINTS = 200
MAX_TOTAL_FREQUENCY = 10_000


@dataclass(frozen=True)
class RawStatisticsDataset:
    kind: Literal["data", "frequency"]
    values: tuple[sp.Expr, ...]
    frequencies: tuple[int, ...] | None = None


@dataclass(frozen=True)
class GroupedStatisticsDataset:
    intervals: tuple[tuple[sp.Rational, sp.Rational], ...]
    frequencies: tuple[int, ...]


def solve_statistics(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    text = problem.normalized_input.strip()
    steps = [normalize_step(problem)]
    try:
        dataset = _parse_stats_input(text)
        if isinstance(dataset, GroupedStatisticsDataset):
            return _solve_grouped_statistics(problem, dataset, steps)
        expanded = _expand_values(list(dataset.values), list(dataset.frequencies) if dataset.frequencies else None)
    except ValueError as exc:
        return _unsupported(problem, str(exc))

    kind = dataset.kind

    n = len(expanded)
    mean_exact = sp.simplify(sum(expanded) / n)
    try:
        mean_f = float(mean_exact)
    except Exception:
        mean_f = statistics.fmean(float(v) for v in expanded)

    floats = [float(v) for v in expanded]
    median_f = statistics.median(floats)
    try:
        modes = statistics.multimode(floats)
        mode_text = ", ".join(_fmt_float(m) for m in modes[:5])
    except statistics.StatisticsError:
        mode_text = "—"

    if n >= 2:
        var_f = statistics.pvariance(floats)
        std_f = statistics.pstdev(floats)
    else:
        var_f = 0.0
        std_f = 0.0

    sorted_vals = sorted(expanded, key=lambda x: float(x))
    steps.append(AlgebraSolveStep(
        index=2,
        title="Sắp xếp và đếm số liệu",
        explanation=(
            f"Có n = {n} giá trị. Dãy đã sắp: "
            f"{', '.join(sp.sstr(v) for v in sorted_vals[:30])}{'…' if n > 30 else ''}."
        ),
        goal="Chuẩn bị tính các đặc trưng mô tả.",
        why="Trung vị và tần số cần dãy có thứ tự.",
        rule="Thống kê mô tả 1 chiều",
        operation="Sắp xếp không giảm.",
        result=f"n={n}",
        kind="transform",
        confidence="verified",
    ))
    steps.append(AlgebraSolveStep(
        index=3,
        title="Tính các đặc trưng",
        explanation=(
            f"Trung bình = {sp.sstr(mean_exact)}; "
            f"trung vị ≈ {_fmt_float(median_f)}; "
            f"mốt = {mode_text}; "
            f"phương sai (tổng thể) ≈ {_fmt_float(var_f)}; "
            f"độ lệch chuẩn ≈ {_fmt_float(std_f)}."
        ),
        goal="Tính mean, median, mode, variance, stdev.",
        why="Đặc trưng cơ bản của dãy số liệu 1 chiều.",
        rule="statistics + SymPy Rational mean",
        operation="mean exact; median/mode/var/std via stdlib statistics.",
        result=sp.sstr(mean_exact),
        result_latex=sp.latex(mean_exact),
        kind="solve",
        confidence="numeric_checked",
    ))

    answer = (
        f"n={n}; mean={sp.sstr(mean_exact)}; median≈{_fmt_float(median_f)}; "
        f"mode={mode_text}; variance≈{_fmt_float(var_f)}; stdev≈{_fmt_float(std_f)}"
    )
    answer_latex = (
        rf"n={n},\;\bar x={sp.latex(mean_exact)},\;"
        rf"\mathrm{{Med}}\approx {_fmt_float(median_f)},\;"
        rf"s^2\approx {_fmt_float(var_f)}"
    )
    steps.append(conclusion_step(4, answer, answer_latex))

    recompute = sum(floats) / n
    mean_ok = abs(recompute - mean_f) < 1e-9
    verification = AlgebraVerificationReport(
        status="verified" if mean_ok else "partially_verified",
        checks=[
            AlgebraVerificationCheck(
                name="stats_count",
                status="pass",
                detail=f"Số quan sát n={n} trong giới hạn hỗ trợ.",
            ),
            AlgebraVerificationCheck(
                name="stats_mean_recompute",
                status="pass" if mean_ok else "warn",
                detail=f"Kiểm tra lại trung bình: {recompute} vs {mean_f}.",
            ),
        ],
        method=["stdlib.statistics", "exact_rational_mean"],
    )

    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="statistics",
        problem_type="descriptive_stats" if kind == "data" else "descriptive_stats_freq",
        status="solved",
        answer=answer,
        answer_latex=answer_latex,
        solution_set=AlgebraSolutionSet(kind="expression", text=answer, latex=answer_latex),
        steps=steps,
        milestones=[f"Dãy n={n}", f"Mean={sp.sstr(mean_exact)}"],
        verification=verification,
        assumptions=["Phương sai/độ lệch chuẩn theo công thức tổng thể (pvariance/pstdev)."],
        warnings=[],
        errors=[],
    )


def _solve_grouped_statistics(
    problem: ParsedAlgebraProblem,
    dataset: GroupedStatisticsDataset,
    steps: list[AlgebraSolveStep],
) -> AlgebraSolveResponse:
    total = sum(dataset.frequencies)
    midpoints = tuple((left + right) / 2 for left, right in dataset.intervals)
    mean = sp.simplify(sum(point * frequency for point, frequency in zip(midpoints, dataset.frequencies)) / total)
    variance = sp.simplify(
        sum(frequency * (point - mean) ** 2 for point, frequency in zip(midpoints, dataset.frequencies)) / total
    )
    standard_deviation = sp.sqrt(variance)
    q1 = _grouped_quantile(dataset, sp.Rational(1, 4))
    median = _grouped_quantile(dataset, sp.Rational(1, 2))
    q3 = _grouped_quantile(dataset, sp.Rational(3, 4))
    mode = _grouped_mode(dataset)
    iqr = sp.simplify(q3 - q1)
    lower_outlier = sp.simplify(q1 - sp.Rational(3, 2) * iqr)
    upper_outlier = sp.simplify(q3 + sp.Rational(3, 2) * iqr)

    steps.append(AlgebraSolveStep(
        index=2,
        title="Lập giá trị đại diện",
        explanation="Dùng trung điểm mỗi lớp làm giá trị đại diện cho dữ liệu ghép nhóm.",
        rule="Giá trị đại diện x_i=(L_i+U_i)/2",
        result=", ".join(sp.sstr(value) for value in midpoints),
        kind="transform",
        confidence="verified",
    ))
    steps.append(AlgebraSolveStep(
        index=3,
        title="Ước lượng đặc trưng ghép nhóm",
        explanation=(
            f"mean≈{sp.sstr(mean)}; median≈{sp.sstr(median)}; mode≈{sp.sstr(mode)}; "
            f"Q1≈{sp.sstr(q1)}; Q3≈{sp.sstr(q3)}; variance≈{sp.sstr(variance)}."
        ),
        rule="Nội suy tuyến tính trong lớp chứa phân vị",
        result=sp.sstr(mean),
        result_latex=sp.latex(mean),
        kind="solve",
        confidence="numeric_checked",
    ))
    answer = (
        f"n={total}; mean≈{sp.sstr(mean)}; median≈{sp.sstr(median)}; mode≈{sp.sstr(mode)}; "
        f"Q1≈{sp.sstr(q1)}; Q3≈{sp.sstr(q3)}; variance≈{sp.sstr(variance)}; "
        f"stdev≈{sp.sstr(standard_deviation)}; outlier_bounds≈({sp.sstr(lower_outlier)}, {sp.sstr(upper_outlier)})"
    )
    answer_latex = (
        rf"n={total},\;\bar x\approx {sp.latex(mean)},\;Q_1\approx {sp.latex(q1)},\;"
        rf"Q_2\approx {sp.latex(median)},\;Q_3\approx {sp.latex(q3)}"
    )
    steps.append(conclusion_step(4, answer, answer_latex))
    verification = AlgebraVerificationReport(
        status="partially_verified",
        checks=[
            AlgebraVerificationCheck(
                name="grouped_frequency_total",
                status="pass",
                detail=f"Tổng tần số n={total} dương và trong giới hạn.",
            ),
            AlgebraVerificationCheck(
                name="grouped_interval_order",
                status="pass",
                detail="Các khoảng có độ rộng dương, theo thứ tự và không chồng lấn.",
            ),
            AlgebraVerificationCheck(
                name="grouped_mean_recompute",
                status="pass",
                detail="Tính lại tổng trung điểm nhân tần số chia tổng tần số.",
                latex=sp.latex(mean),
            ),
        ],
        method=["grouped_midpoint_recompute", "grouped_quantile_interpolation"],
    )
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="statistics",
        problem_type="descriptive_stats_grouped",
        status="solved",
        answer=answer,
        answer_latex=answer_latex,
        solution_set=AlgebraSolutionSet(kind="expression", text=answer, latex=answer_latex),
        steps=steps,
        milestones=[f"Dữ liệu ghép nhóm n={total}", f"Mean≈{sp.sstr(mean)}"],
        verification=verification,
        assumptions=["Các đặc trưng được ước lượng bằng trung điểm lớp và nội suy tuyến tính trong lớp."],
        warnings=["Dữ liệu ghép nhóm chỉ cho kết quả xấp xỉ, không khôi phục được quan sát gốc."],
        errors=[],
    )


def _grouped_quantile(dataset: GroupedStatisticsDataset, fraction: sp.Rational) -> sp.Expr:
    rank = sp.Rational(sum(dataset.frequencies)) * fraction
    cumulative = 0
    for (left, right), frequency in zip(dataset.intervals, dataset.frequencies):
        next_cumulative = cumulative + frequency
        if frequency > 0 and rank <= next_cumulative:
            return sp.simplify(left + (rank - cumulative) * (right - left) / frequency)
        cumulative = next_cumulative
    return dataset.intervals[-1][1]


def _grouped_mode(dataset: GroupedStatisticsDataset) -> sp.Expr:
    index = max(range(len(dataset.frequencies)), key=dataset.frequencies.__getitem__)
    left, right = dataset.intervals[index]
    frequency = dataset.frequencies[index]
    previous = dataset.frequencies[index - 1] if index > 0 else 0
    following = dataset.frequencies[index + 1] if index + 1 < len(dataset.frequencies) else 0
    denominator = 2 * frequency - previous - following
    if denominator <= 0:
        return sp.simplify((left + right) / 2)
    return sp.simplify(left + sp.Rational(frequency - previous, denominator) * (right - left))


def _parse_stats_input(text: str) -> RawStatisticsDataset | GroupedStatisticsDataset:
    grouped = re.fullmatch(
        r"stats_grouped\(\s*(?:intervals\s*=\s*)?([^;]+)\s*;\s*(?:freqs\s*=\s*)?(.+)\s*\)",
        text,
        re.IGNORECASE,
    )
    if grouped:
        intervals = _parse_intervals(grouped.group(1))
        frequencies = _parse_frequencies(grouped.group(2))
        if len(intervals) != len(frequencies):
            raise ValueError("Số khoảng và số tần số phải bằng nhau.")
        if any(right <= left for left, right in intervals):
            raise ValueError("Mỗi khoảng ghép nhóm phải có cận phải lớn hơn cận trái.")
        if any(intervals[index][1] > intervals[index + 1][0] for index in range(len(intervals) - 1)):
            raise ValueError("Các khoảng ghép nhóm không được chồng lấn.")
        _validate_frequencies(frequencies)
        return GroupedStatisticsDataset(tuple(intervals), tuple(frequencies))

    raw = re.fullmatch(r"stats\(\s*(?:data\s*=\s*)?(.+)\s*\)", text, re.IGNORECASE)
    if raw:
        values = _parse_number_list(raw.group(1))
        if not values:
            raise ValueError("Dãy số liệu trống.")
        if len(values) > MAX_DATA_POINTS:
            raise ValueError(f"Chỉ hỗ trợ tối đa {MAX_DATA_POINTS} số liệu.")
        return RawStatisticsDataset("data", tuple(values))

    frequency = re.fullmatch(
        r"stats_freq\(\s*(?:values\s*=\s*)?([^;]+)\s*;\s*(?:freqs\s*=\s*)?(.+)\s*\)",
        text,
        re.IGNORECASE,
    )
    if frequency:
        values = _parse_number_list(frequency.group(1))
        frequencies = _parse_frequencies(frequency.group(2))
        if len(values) != len(frequencies):
            raise ValueError("Số phần tử values và freqs phải bằng nhau.")
        _validate_frequencies(frequencies)
        return RawStatisticsDataset("frequency", tuple(values), tuple(frequencies))

    raise ValueError(
        "Dạng thống kê chưa hỗ trợ. Dùng stats(data=...), stats_freq(values=...;freqs=...) "
        "hoặc stats_grouped(intervals=0:10,10:20;freqs=3,5)."
    )


def _parse_number_list(text: str) -> list[sp.Expr]:
    parts = [part.strip() for part in re.split(r"[\s,]+", text) if part.strip()]
    values: list[sp.Expr] = []
    for part in parts:
        try:
            value = Fraction(part)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError(f"Không đọc được số liệu: {part}") from exc
        values.append(sp.Rational(value.numerator, value.denominator))
    return values


def _parse_intervals(text: str) -> list[tuple[sp.Rational, sp.Rational]]:
    intervals: list[tuple[sp.Rational, sp.Rational]] = []
    for item in (part.strip() for part in text.split(",") if part.strip()):
        match = re.fullmatch(r"([^:]+):([^:]+)", item)
        if match is None:
            raise ValueError(f"Khoảng ghép nhóm không hợp lệ: {item}")
        left, right = _parse_number_list(" ".join(match.groups()))
        intervals.append((sp.Rational(left), sp.Rational(right)))
    if not intervals:
        raise ValueError("Danh sách khoảng ghép nhóm trống.")
    return intervals


def _parse_frequencies(text: str) -> list[int]:
    values = _parse_number_list(text)
    if any(value.q != 1 for value in values):
        raise ValueError("Tần số phải là số nguyên không âm.")
    return [int(value) for value in values]


def _validate_frequencies(frequencies: list[int]) -> None:
    if any(frequency < 0 for frequency in frequencies):
        raise ValueError("Tần số phải là số nguyên không âm.")
    total = sum(frequencies)
    if total <= 0:
        raise ValueError("Tổng tần số phải dương.")
    if total > MAX_TOTAL_FREQUENCY:
        raise ValueError(f"Tổng tần số không vượt quá {MAX_TOTAL_FREQUENCY}.")


def _expand_values(values: list[sp.Expr], freqs: list[int] | None) -> list[sp.Expr]:
    if freqs is None:
        return list(values)
    expanded: list[sp.Expr] = []
    for value, freq in zip(values, freqs):
        expanded.extend([value] * int(freq))
    if len(expanded) > MAX_DATA_POINTS * 5:
        raise ValueError("Dãy sau khi bung tần số quá dài.")
    return expanded


def _fmt_float(value: float) -> str:
    return f"{value:.10g}"


def _unsupported(problem: ParsedAlgebraProblem, message: str) -> AlgebraSolveResponse:
    return AlgebraSolveResponse(
        input=problem.raw_input,
        normalized_input=problem.normalized_input,
        topic="statistics",
        problem_type="descriptive_stats",
        status="unsupported",
        answer=message,
        errors=[message],
    )
