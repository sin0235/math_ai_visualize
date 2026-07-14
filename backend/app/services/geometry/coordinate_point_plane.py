from __future__ import annotations

from functools import reduce
from math import gcd
from typing import Any

import sympy as sp

from app.services.geometry.metric_precision import approximate_latex, parse_metric_precision
from app.services.geometry.orthogonal_frame import parse_point_plane_goal, resolve_point_plane_frame
from app.services.geometry.solution_builder import SolverResult, SolverStep
from app.services.geometry_facts import GeometryFact, build_geometry_fact_graph


def solve_coordinate_point_plane_from_facts(
    scene: dict[str, Any],
    question: str,
    warnings: list[str] | None = None,
    *,
    precision_text: str | None = None,
) -> SolverResult | None:
    goal = parse_point_plane_goal(question)
    if goal is None:
        return None
    source, plane = goal
    graph = build_geometry_fact_graph(scene)
    resolution = resolve_point_plane_frame(graph, source, plane)
    if resolution.solution is None:
        if resolution.declared_frame_seen and resolution.reason:
            return SolverResult(
                question,
                "Không đủ dữ kiện",
                [],
                [*(warnings or []), resolution.reason],
                confidence="insufficient",
                method="oxyz",
            )
        return None

    solution = resolution.solution
    frame = solution.frame
    points = solution.points
    origin, second, third = plane
    first_direction = sp.simplify(points[second] - points[origin])
    second_direction = sp.simplify(points[third] - points[origin])
    point_direction = sp.simplify(points[source] - points[origin])
    normal = _primitive_vector(first_direction.cross(second_direction))
    if normal is None:
        return SolverResult(
            question,
            "Không đủ dữ kiện",
            [],
            [*(warnings or []), f"Ba điểm {origin}, {second}, {third} không xác định một mặt phẳng."],
            confidence="insufficient",
            method="oxyz",
        )

    numerator = sp.simplify(abs(normal.dot(point_direction)))
    denominator = sp.simplify(sp.sqrt(normal.dot(normal)))
    distance = sp.simplify(numerator / denominator)
    if distance != sp.simplify(solution.projection.distance):
        return SolverResult(
            question,
            "Không đủ dữ kiện",
            [],
            [*(warnings or []), "Hai phép tính exact cho khoảng cách không khớp nhau."],
            confidence="insufficient",
            method="oxyz",
        )

    exact_latex = sp.latex(distance)
    precision = parse_metric_precision(
        precision_text or "",
        question,
        str(scene.get("problem_text") or ""),
    )
    approximate = approximate_latex(distance, precision) if precision is not None else None
    displayed_value = exact_latex + (rf" \approx {approximate}" if approximate else "")
    plane_name = "".join(plane)
    answer = f"d({source},({plane_name})) = {displayed_value}"
    frame_fact = frame.fact
    construction_facts = list(solution.construction_facts)
    evidence_facts = [frame_fact, *construction_facts]
    evidence_ids = [fact.id for fact in evidence_facts]

    base = tuple(str(item) for item in frame_fact.args.get("base") or ())
    top = tuple(str(item) for item in frame_fact.args.get("top") or ())
    axis_lengths = frame.axis_lengths
    relevant_names = list(dict.fromkeys([source, *plane]))
    coordinate_latex = r",\quad ".join(
        rf"{name}={_matrix_latex(points[name])}" for name in relevant_names
    )
    midpoint_explanation, midpoint_formula = _midpoint_details(construction_facts, points)
    axis_formula = ""
    if len(base) == 4 and len(top) == 4:
        axis_formula = (
            rf"{base[0]}=(0;0;0),\quad "
            rf"{base[1]}=({sp.latex(axis_lengths[0])};0;0),\quad "
            rf"{base[3]}=(0;{sp.latex(axis_lengths[1])};0),\quad "
            rf"{top[0]}=(0;0;{sp.latex(axis_lengths[2])})"
        )

    conclusion = f"Giữ nguyên dạng chính xác {exact_latex}."
    if approximate:
        conclusion += f" Chỉ tại kết quả cuối mới làm tròn theo yêu cầu đề bài, được {approximate.replace('{,}', ',')}."

    steps = [
        SolverStep(
            1,
            "Chọn hệ trục tọa độ",
            _frame_explanation(frame_fact, base, top),
            None,
            None,
            list(dict.fromkeys([*base, *top, source, *plane])),
            kind="coordinate_frame_setup",
            formula_latex=axis_formula or None,
            claim="Hệ tọa độ được dựng từ các dữ kiện hình học đã cho, không dùng tỉ lệ minh họa.",
            relation_ids=[frame_fact.id],
        ),
        SolverStep(
            2,
            "Xác định tọa độ các điểm",
            midpoint_explanation or "Suy ra tọa độ các điểm cần dùng từ khung vuông góc đã chọn.",
            None,
            None,
            relevant_names,
            kind="coordinate_derivation",
            formula_latex=midpoint_formula or coordinate_latex,
            substitution_latex=coordinate_latex if midpoint_formula else None,
            claim=f"Đã xác định tọa độ exact của {', '.join(relevant_names)}.",
            relation_ids=evidence_ids,
            depends_on=[frame_fact.id],
        ),
        SolverStep(
            3,
            "Lập vectơ pháp tuyến",
            f"Lập hai vectơ {origin}{second}, {origin}{third} nằm trong mặt phẳng ({plane_name}) rồi lấy tích có hướng.",
            None,
            None,
            relevant_names,
            kind="distance_point_plane_setup",
            formula_latex=(
                rf"\overrightarrow{{{origin}{second}}}={_matrix_latex(first_direction)},\quad "
                rf"\overrightarrow{{{origin}{third}}}={_matrix_latex(second_direction)},\quad "
                rf"\vec n=\overrightarrow{{{origin}{second}}}\times"
                rf"\overrightarrow{{{origin}{third}}}={_matrix_latex(normal)}"
            ),
            claim=rf"\vec n={_matrix_latex(normal)} là một pháp tuyến của ({plane_name}).",
            relation_ids=evidence_ids,
            depends_on=[frame_fact.id],
        ),
        SolverStep(
            4,
            "Tính khoảng cách",
            f"Chiếu vectơ {origin}{source} lên pháp tuyến của mặt phẳng ({plane_name}) và rút gọn exact.",
            None,
            exact_latex,
            relevant_names,
            kind="distance_point_plane",
            formula_latex=(
                rf"d({source},({plane_name}))="
                rf"\frac{{|\vec n\cdot\overrightarrow{{{origin}{source}}}|}}{{\|\vec n\|}}"
            ),
            substitution_latex=(
                rf"\overrightarrow{{{origin}{source}}}={_matrix_latex(point_direction)},\quad "
                rf"d=\frac{{{sp.latex(numerator)}}}{{{sp.latex(denominator)}}}={exact_latex}"
            ),
            result_latex=exact_latex,
            claim=f"d({source},({plane_name})) = {exact_latex}",
            relation_ids=evidence_ids,
            depends_on=[frame_fact.id],
        ),
        SolverStep(
            5,
            "Kết luận",
            conclusion,
            None,
            displayed_value,
            relevant_names,
            kind="result",
            formula_latex=rf"d({source},({plane_name}))={displayed_value}",
            result_latex=displayed_value,
            claim=answer,
            relation_ids=evidence_ids,
            depends_on=["4"],
        ),
    ]
    return SolverResult(
        question,
        answer,
        steps,
        warnings or [],
        confidence="verified",
        method="oxyz",
        used_facts=[_used_fact(fact) for fact in evidence_facts],
    )


def _primitive_vector(vector: sp.Matrix) -> sp.Matrix | None:
    values = [sp.Rational(sp.simplify(value)) for value in vector]
    if all(value == 0 for value in values):
        return None
    common_denominator = sp.ilcm(*[int(value.q) for value in values])
    integers = [int(value * common_denominator) for value in values]
    common_divisor = reduce(gcd, (abs(value) for value in integers if value), 0) or 1
    return sp.Matrix([value // common_divisor for value in integers])


def _matrix_latex(vector: sp.Matrix) -> str:
    return r"\left(" + ";".join(sp.latex(sp.simplify(value)) for value in vector) + r"\right)"


def _frame_explanation(
    frame_fact: GeometryFact,
    base: tuple[str, ...],
    top: tuple[str, ...],
) -> str:
    if len(base) == 4 and len(top) == 4:
        return (
            f"Chọn {base[0]} làm gốc; ba trục lần lượt theo {base[0]}{base[1]}, "
            f"{base[0]}{base[3]} và {base[0]}{top[0]}. "
            "Ba phương này đôi một vuông góc theo cấu trúc khối đã cho."
        )
    return frame_fact.text


def _midpoint_details(
    facts: list[GeometryFact],
    points: dict[str, sp.Matrix],
) -> tuple[str, str | None]:
    explanations: list[str] = []
    formulas: list[str] = []
    for fact in facts:
        point = str(fact.args.get("point") or "")
        segment = fact.args.get("segment")
        if not point or not isinstance(segment, tuple) or len(segment) != 2:
            continue
        first, second = segment
        explanations.append(f"Vì {point} là trung điểm của {first}{second}, lấy trung bình tọa độ hai đầu mút.")
        formulas.append(
            rf"{point}=\frac{{{first}+{second}}}{{2}}={_matrix_latex(points[point])}"
        )
    return " ".join(explanations), r",\quad ".join(formulas) or None


def _used_fact(fact: GeometryFact) -> dict[str, str]:
    source = "given" if fact.source == "given" else "verified"
    return {"source": source, "text": fact.text}
