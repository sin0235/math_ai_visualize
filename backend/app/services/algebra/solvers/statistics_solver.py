"""Descriptive statistics for algebra-solver (1D data + frequency tables).

Uses stdlib ``statistics`` and SymPy Rational for exact means.
"""

from __future__ import annotations

import re
import statistics

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


def solve_statistics(problem: ParsedAlgebraProblem) -> AlgebraSolveResponse:
    text = problem.normalized_input.strip()
    steps = [normalize_step(problem)]
    try:
        kind, values, freqs = _parse_stats_input(text)
        expanded = _expand_values(values, freqs)
    except ValueError as exc:
        return _unsupported(problem, str(exc))

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


def _parse_stats_input(text: str) -> tuple[str, list[sp.Expr], list[int] | None]:
    m = re.fullmatch(r"stats\(\s*(?:data\s*=\s*)?(.+)\s*\)", text, re.IGNORECASE)
    if m:
        values = _parse_number_list(m.group(1))
        if not values:
            raise ValueError("Dãy số liệu trống.")
        if len(values) > MAX_DATA_POINTS:
            raise ValueError(f"Chỉ hỗ trợ tối đa {MAX_DATA_POINTS} số liệu.")
        return "data", values, None

    m = re.fullmatch(
        r"stats_freq\(\s*(?:values\s*=\s*)?([^;]+)\s*;\s*(?:freqs\s*=\s*)?(.+)\s*\)",
        text,
        re.IGNORECASE,
    )
    if m:
        values = _parse_number_list(m.group(1))
        freqs_raw = _parse_number_list(m.group(2))
        freqs = [int(f) for f in freqs_raw]
        if len(values) != len(freqs):
            raise ValueError("Số phần tử values và freqs phải bằng nhau.")
        if any(f < 0 for f in freqs):
            raise ValueError("Tần số phải là số nguyên không âm.")
        if sum(freqs) > MAX_TOTAL_FREQUENCY:
            raise ValueError(f"Tổng tần số không vượt quá {MAX_TOTAL_FREQUENCY}.")
        if sum(freqs) == 0:
            raise ValueError("Tổng tần số phải dương.")
        return "freq", values, freqs

    raise ValueError(
        "Dạng thống kê chưa hỗ trợ. Dùng stats(data=1,2,3) hoặc stats_freq(values=1,2;freqs=3,1)."
    )


def _parse_number_list(text: str) -> list[sp.Expr]:
    parts = [p.strip() for p in re.split(r"[\s,]+", text) if p.strip()]
    out: list[sp.Expr] = []
    for part in parts:
        cleaned = part.replace("^", "**")
        try:
            val = sp.sympify(cleaned, evaluate=True)
        except Exception as exc:
            raise ValueError(f"Không đọc được số liệu: {part}") from exc
        if getattr(val, "free_symbols", set()):
            raise ValueError(f"Số liệu không được chứa biến: {part}")
        out.append(sp.nsimplify(val))
    return out


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
