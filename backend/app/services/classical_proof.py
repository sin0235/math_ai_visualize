from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.geometry_facts import GeometryFact, build_geometry_fact_graph, parse_plane_token, point_on_plane


@dataclass(frozen=True)
class ClassicalProofStep:
    title: str
    explanation: str
    highlight: list[str]
    kind: str
    formula_latex: str | None = None
    result_latex: str | None = None
    claim: str | None = None
    theorem: str | None = None
    depends_on: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClassicalProof:
    steps: list[ClassicalProofStep]
    used_theorems: list[str]


def build_classical_proof(
    scene: dict[str, Any],
    question: str,
    kind: str,
    highlight: list[str],
    answer: str,
    result_latex: str | None,
) -> ClassicalProof | None:
    graph = build_geometry_fact_graph(scene)
    if kind == "distance_point_plane":
        return _point_plane_distance_proof(graph, question, highlight, answer, result_latex)
    if kind == "angle_line_plane":
        return _line_plane_angle_proof(graph, question, highlight, answer, result_latex)
    if kind == "volume_pyramid":
        return _pyramid_volume_proof(graph, highlight, answer, result_latex)
    return None


def _point_plane_distance_proof(graph, question: str, highlight: list[str], answer: str, result_latex: str | None) -> ClassicalProof | None:
    if len(highlight) < 4:
        return None
    point = highlight[0]
    plane = tuple(highlight[1:4])
    plane_name = "".join(plane)
    height = _height_fact(graph, point, plane)
    if height is None:
        return None
    segment, foot, fact = height
    label = graph.length_label(point, foot)
    setup = _setup_step(highlight, [fact], f"Xét điểm {point}, mặt phẳng ({plane_name}) và quan hệ vuông góc đã cho.")
    method = ClassicalProofStep(
        title="Nhận ra đường cao",
        explanation=f"Vì {segment} vuông góc với mặt phẳng ({plane_name}) và {foot} thuộc ({plane_name}), nên {segment} là đoạn vuông góc kẻ từ {point} đến ({plane_name}). Do đó khoảng cách cần tìm là {segment}.",
        highlight=highlight,
        kind="distance_point_plane",
        formula_latex=rf"{segment}\perp({plane_name}),\ {foot}\in({plane_name})\Rightarrow d({point},({plane_name}))={segment}",
        claim=f"d({point},({plane_name})) = {segment}",
        theorem="Khoảng cách từ điểm đến mặt phẳng là độ dài đoạn vuông góc kẻ từ điểm đó đến mặt phẳng.",
        depends_on=[fact.id],
    )
    conclusion_text = f"Mà {segment} = {label}, nên d({point},({plane_name})) = {segment} = {result_latex or answer.split('=', 1)[-1].strip()}." if label else f"Suy ra {answer}."
    conclusion = ClassicalProofStep(
        title="Kết luận",
        explanation=conclusion_text,
        highlight=highlight,
        kind="result",
        result_latex=result_latex,
        claim=answer,
        depends_on=[fact.id],
    )
    return ClassicalProof([setup, method, conclusion], [method.theorem or ""])


def _line_plane_angle_proof(graph, question: str, highlight: list[str], answer: str, result_latex: str | None) -> ClassicalProof | None:
    if len(highlight) < 2:
        return None
    line = (highlight[0], highlight[1])
    plane = _first_plane_ref(question, highlight)
    if plane is None:
        return None
    plane_tuple = tuple(plane)
    plane_name = "".join(plane_tuple)
    line_name = "".join(line)
    setup = _setup_step(highlight, graph.by_type("perpendicular_line_plane"), f"Xét đường thẳng {line_name} và mặt phẳng ({plane_name}).")

    for fact in graph.by_type("perpendicular_line_plane"):
        segment = fact.args.get("line")
        fact_plane = tuple(fact.args.get("plane") or ())
        if set(fact_plane) != set(plane_tuple) or not isinstance(segment, tuple):
            continue
        if set(segment) == set(line):
            theorem = "Đường thẳng vuông góc với mặt phẳng thì góc giữa đường thẳng đó và mặt phẳng bằng 90°."
            method = ClassicalProofStep(
                title="Nhận ra đường vuông góc mặt phẳng",
                explanation=f"Vì {line_name} vuông góc với mặt phẳng ({plane_name}), nên góc giữa {line_name} và ({plane_name}) bằng 90°.",
                highlight=highlight,
                kind="angle_line_plane",
                formula_latex=rf"{line_name}\perp({plane_name})\Rightarrow \widehat{{({line_name},({plane_name}))}}=90^\circ",
                claim=f"Góc giữa {line_name} và ({plane_name}) bằng 90°",
                theorem=theorem,
                depends_on=[fact.id],
            )
            conclusion = ClassicalProofStep(
                title="Kết luận",
                explanation=f"Suy ra góc giữa {line_name} và ({plane_name}) bằng 90°.",
                highlight=highlight,
                kind="result",
                result_latex=result_latex,
                claim=answer,
                depends_on=[fact.id],
            )
            return ClassicalProof([setup, method, conclusion], [theorem])

        projection = _projection_from_height(graph, line, plane_tuple, segment, fact)
        if projection:
            outside, foot, plane_point = projection
            projected_line = f"{foot}{plane_point}"
            angle_name = f"{outside}{plane_point}{foot}"
            theorem = "Góc giữa đường thẳng và mặt phẳng là góc giữa đường thẳng đó và hình chiếu của nó trên mặt phẳng."
            method = ClassicalProofStep(
                title="Dùng hình chiếu trên mặt phẳng",
                explanation=f"Gọi {foot} là hình chiếu của {outside} lên ({plane_name}). Vì {plane_point} thuộc ({plane_name}), nên hình chiếu của {line_name} trên ({plane_name}) là {projected_line}. Do đó góc giữa {line_name} và ({plane_name}) là góc {angle_name}.",
                highlight=highlight,
                kind="angle_line_plane",
                formula_latex=rf"\widehat{{({line_name},({plane_name}))}}=\widehat{{{angle_name}}}",
                claim=f"Góc giữa {line_name} và ({plane_name}) là góc {angle_name}",
                theorem=theorem,
                depends_on=[fact.id],
            )
            return ClassicalProof([setup, method, _conclusion(highlight, answer, result_latex, [fact.id])], [theorem])
    return None


def _pyramid_volume_proof(graph, highlight: list[str], answer: str, result_latex: str | None) -> ClassicalProof | None:
    if len(highlight) < 4:
        return None
    apex = highlight[0]
    base = tuple(highlight[1:])
    height = _height_fact(graph, apex, base)
    if height is None:
        return None
    segment, foot, fact = height
    base_name = "".join(base)
    label = graph.length_label(apex, foot)
    theorem = "Thể tích khối chóp bằng một phần ba diện tích đáy nhân với chiều cao."
    setup = _setup_step(highlight, [fact], f"Xét khối chóp có đỉnh {apex}, đáy {base_name} và đường cao ứng viên {segment}.")
    method = ClassicalProofStep(
        title="Nhận ra đáy và chiều cao",
        explanation=f"Vì {segment} vuông góc với mặt phẳng đáy ({base_name}) và {foot} thuộc đáy, nên {segment} là chiều cao của khối chóp.",
        highlight=highlight,
        kind="volume_pyramid",
        formula_latex=rf"V=\frac13 S_{{{base_name}}}\cdot {segment}",
        claim=f"{segment} là chiều cao của khối chóp",
        theorem=theorem,
        depends_on=[fact.id],
    )
    if label:
        text = f"Với đáy {base_name} và chiều cao {segment} = {label}, áp dụng V = 1/3·S_đáy·h, suy ra {answer}."
    else:
        text = f"Với đáy {base_name} và chiều cao {segment}, áp dụng V = 1/3·S_đáy·h, suy ra {answer}."
    conclusion = ClassicalProofStep("Kết luận", text, highlight, "result", result_latex=result_latex, claim=answer, depends_on=[fact.id])
    return ClassicalProof([setup, method, conclusion], [theorem])


def _setup_step(highlight: list[str], facts: list[GeometryFact], fallback: str) -> ClassicalProofStep:
    fact_texts = [fact.text for fact in facts if fact.trusted]
    return ClassicalProofStep(
        title="Xác định dữ kiện hình học",
        explanation="; ".join(dict.fromkeys(fact_texts[:4])) or fallback,
        highlight=highlight,
        kind="input",
        claim="Chọn các dữ kiện đã cho/đã kiểm chứng để lập luận.",
        depends_on=[fact.id for fact in facts if fact.trusted][:4],
    )


def _height_fact(graph, point: str, plane: tuple[str, ...]) -> tuple[str, str, GeometryFact] | None:
    plane_set = set(plane)
    for fact in graph.by_type("perpendicular_line_plane"):
        segment = fact.args.get("line")
        fact_plane = tuple(fact.args.get("plane") or ())
        if not isinstance(segment, tuple) or set(fact_plane) != plane_set or point not in segment:
            continue
        foot = segment[1] if segment[0] == point else segment[0]
        if not point_on_plane(graph, foot, plane):
            continue
        return f"{point}{foot}", foot, fact
    return None


def _projection_from_height(graph, line: tuple[str, str], plane: tuple[str, ...], height_segment: tuple[str, str], fact: GeometryFact) -> tuple[str, str, str] | None:
    line_set = set(line)
    for outside, foot in (height_segment, (height_segment[1], height_segment[0])):
        if outside not in line_set:
            continue
        plane_point = line[1] if line[0] == outside else line[0]
        if point_on_plane(graph, foot, plane) and point_on_plane(graph, plane_point, plane):
            return outside, foot, plane_point
    return None


def _first_plane_ref(question: str, highlight: list[str]) -> tuple[str, ...] | None:
    for raw in re.findall(r"\(([^()]+)\)", question):
        plane = parse_plane_token(f"({raw})")
        if plane:
            return tuple(plane)
    if len(highlight) >= 5:
        return tuple(highlight[2:5])
    return None


def _conclusion(highlight: list[str], answer: str, result_latex: str | None, depends_on: list[str]) -> ClassicalProofStep:
    return ClassicalProofStep(
        title="Kết luận",
        explanation=f"Dựa trên các dữ kiện hình học đã kiểm chứng, suy ra {answer}.",
        highlight=highlight,
        kind="result",
        result_latex=result_latex,
        claim=answer,
        depends_on=depends_on,
    )