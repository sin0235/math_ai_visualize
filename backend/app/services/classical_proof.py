from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.geometry_facts import GeometryFact, build_geometry_fact_graph, parse_plane_token, point_on_plane
from app.services.geometry_theorems import theorem


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
    if kind == "distance_point_line":
        return _point_line_distance_proof(graph, highlight, answer, result_latex)
    if kind == "distance_point_plane":
        return _point_plane_distance_proof(graph, question, highlight, answer, result_latex)
    if kind == "angle_line_line":
        return _line_line_angle_proof(graph, question, highlight, answer, result_latex)
    if kind == "angle_line_plane":
        return _line_plane_angle_proof(graph, question, highlight, answer, result_latex)
    if kind == "angle_plane_plane":
        return _plane_plane_angle_proof(graph, question, highlight, answer, result_latex)
    if kind == "area_polygon":
        return _triangle_area_proof(graph, highlight, answer, result_latex)
    if kind == "volume_pyramid":
        return _pyramid_volume_proof(graph, highlight, answer, result_latex)
    return None


def _point_line_distance_proof(graph, highlight: list[str], answer: str, result_latex: str | None) -> ClassicalProof | None:
    if len(highlight) < 3:
        return None
    point = highlight[0]
    target = tuple(highlight[1:3])
    candidate: tuple[tuple[str, str], GeometryFact] | None = None
    for fact in graph.by_type("perpendicular_lines"):
        first = fact.args.get("first")
        second = fact.args.get("second")
        if not isinstance(first, tuple) or not isinstance(second, tuple):
            continue
        for height, line in ((first, second), (second, first)):
            if point in height and set(line) == set(target) and set(height) & set(target):
                candidate = height, fact
                break
        if candidate:
            break
    if candidate is None:
        for fact in graph.by_type("perpendicular_line_plane"):
            height = fact.args.get("line")
            plane = set(fact.args.get("plane") or ())
            if isinstance(height, tuple) and point in height and set(target).issubset(plane) and set(height) & set(target):
                candidate = height, fact
                break
    if candidate is None:
        return None
    height, fact = candidate
    foot = next(name for name in height if name != point)
    segment = f"{point}{foot}"
    line_name = "".join(target)
    label = graph.length_label(point, foot)
    theorem_text = theorem("distance.point_line.perpendicular_segment").statement
    setup = _setup_step(highlight, [fact], f"Xét điểm {point} và đường thẳng {line_name}.")
    method = ClassicalProofStep(
        title="Nhận ra đoạn vuông góc",
        explanation=f"Vì {segment} vuông góc với {line_name} tại {foot}, nên khoảng cách từ {point} đến {line_name} là độ dài {segment}.",
        highlight=highlight,
        kind="distance_point_line",
        formula_latex=rf"{segment}\perp {line_name}\Rightarrow d({point},{line_name})={segment}",
        claim=f"d({point},{line_name}) = {segment}",
        theorem=theorem_text,
        depends_on=[fact.id],
    )
    conclusion_text = f"Mà {segment} = {label}, nên {answer}." if label else f"Suy ra {answer}."
    conclusion = ClassicalProofStep(
        title="Kết luận",
        explanation=conclusion_text,
        highlight=highlight,
        kind="result",
        result_latex=result_latex,
        claim=answer,
        depends_on=[fact.id],
    )
    return ClassicalProof([setup, method, conclusion], [theorem_text])


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
        theorem=theorem("distance.point_plane.perpendicular_segment").statement,
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


def _line_line_angle_proof(graph, question: str, highlight: list[str], answer: str, result_latex: str | None) -> ClassicalProof | None:
    edges = _edge_refs(question)
    if len(edges) < 2:
        return None
    first, second = edges[:2]
    for fact in graph.by_type("perpendicular_lines"):
        fact_first = fact.args.get("first")
        fact_second = fact.args.get("second")
        if not isinstance(fact_first, tuple) or not isinstance(fact_second, tuple):
            continue
        if {frozenset(fact_first), frozenset(fact_second)} != {frozenset(first), frozenset(second)}:
            continue
        first_name, second_name = "".join(first), "".join(second)
        theorem_text = theorem("angle.line_line.perpendicular").statement
        setup = _setup_step(highlight, [fact], f"Xét hai đường thẳng {first_name} và {second_name}.")
        method = ClassicalProofStep(
            title="Dùng quan hệ vuông góc",
            explanation=f"Theo dữ kiện đã kiểm chứng, {first_name} vuông góc với {second_name}. Vì vậy góc giữa hai đường bằng 90°.",
            highlight=highlight,
            kind="angle_line_line",
            formula_latex=rf"{first_name}\perp {second_name}\Rightarrow \widehat{{({first_name},{second_name})}}=90^\circ",
            claim=f"Góc giữa {first_name} và {second_name} bằng 90°",
            theorem=theorem_text,
            depends_on=[fact.id],
        )
        return ClassicalProof(
            [setup, method, _conclusion(highlight, answer, result_latex, [fact.id])],
            [theorem_text],
        )
    return None


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
            theorem_text = theorem("angle.line_plane.perpendicular").statement
            method = ClassicalProofStep(
                title="Nhận ra đường vuông góc mặt phẳng",
                explanation=f"Vì {line_name} vuông góc với mặt phẳng ({plane_name}), nên góc giữa {line_name} và ({plane_name}) bằng 90°.",
                highlight=highlight,
                kind="angle_line_plane",
                formula_latex=rf"{line_name}\perp({plane_name})\Rightarrow \widehat{{({line_name},({plane_name}))}}=90^\circ",
                claim=f"Góc giữa {line_name} và ({plane_name}) bằng 90°",
                theorem=theorem_text,
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
            return ClassicalProof([setup, method, conclusion], [theorem_text])

        projection = _projection_from_height(graph, line, plane_tuple, segment, fact)
        if projection:
            outside, foot, plane_point = projection
            projected_line = f"{foot}{plane_point}"
            angle_name = f"{outside}{plane_point}{foot}"
            theorem_text = theorem("angle.line_plane.projection").statement
            method = ClassicalProofStep(
                title="Dùng hình chiếu trên mặt phẳng",
                explanation=f"Gọi {foot} là hình chiếu của {outside} lên ({plane_name}). Vì {plane_point} thuộc ({plane_name}), nên hình chiếu của {line_name} trên ({plane_name}) là {projected_line}. Do đó góc giữa {line_name} và ({plane_name}) là góc {angle_name}.",
                highlight=highlight,
                kind="angle_line_plane",
                formula_latex=rf"\widehat{{({line_name},({plane_name}))}}=\widehat{{{angle_name}}}",
                claim=f"Góc giữa {line_name} và ({plane_name}) là góc {angle_name}",
                theorem=theorem_text,
                depends_on=[fact.id],
            )
            return ClassicalProof([setup, method, _conclusion(highlight, answer, result_latex, [fact.id])], [theorem_text])
    return None


def _plane_plane_angle_proof(graph, question: str, highlight: list[str], answer: str, result_latex: str | None) -> ClassicalProof | None:
    planes = [tuple(plane) for raw in re.findall(r"\(([^()]+)\)", question) if (plane := parse_plane_token(f"({raw})"))]
    if len(planes) < 2:
        return None
    first_plane, second_plane = planes[:2]
    common = [point for point in first_plane if point in set(second_plane)]
    if len(common) < 2:
        return None
    intersection = (common[0], common[1])
    first = _line_perpendicular_to_intersection(graph, intersection, first_plane)
    second = _line_perpendicular_to_intersection(graph, intersection, second_plane)
    if first is None or second is None:
        return None
    first_line, first_fact = first
    second_line, second_fact = second
    shared_vertices = set(first_line) & set(second_line) & set(intersection)
    if not shared_vertices:
        return None
    vertex = sorted(shared_vertices)[0]
    first_other = first_line[1] if first_line[0] == vertex else first_line[0]
    second_other = second_line[1] if second_line[0] == vertex else second_line[0]
    first_name = "".join(first_plane)
    second_name = "".join(second_plane)
    intersection_name = "".join(intersection)
    angle_name = f"{first_other}{vertex}{second_other}"
    theorem_text = theorem("angle.plane_plane.normal_section").statement
    facts = [first_fact, second_fact]
    setup = _setup_step(highlight, facts, f"Hai mặt phẳng ({first_name}) và ({second_name}) cắt nhau theo {intersection_name}.")
    method = ClassicalProofStep(
        title="Dựng góc phẳng nhị diện",
        explanation=f"Hai mặt phẳng cắt nhau theo {intersection_name}. Trong ({first_name}), {''.join(first_line)} vuông góc {intersection_name}; trong ({second_name}), {''.join(second_line)} vuông góc {intersection_name} tại {vertex}. Do đó góc giữa hai mặt phẳng là góc {angle_name}.",
        highlight=highlight,
        kind="angle_plane_plane",
        formula_latex=rf"{''.join(first_line)}\perp {intersection_name},\ {''.join(second_line)}\perp {intersection_name}\Rightarrow \widehat{{(({first_name}),({second_name}))}}=\widehat{{{angle_name}}}",
        claim=f"Góc giữa ({first_name}) và ({second_name}) là góc {angle_name}",
        theorem=theorem_text,
        depends_on=[fact.id for fact in facts],
    )
    return ClassicalProof(
        [setup, method, _conclusion(highlight, answer, result_latex, [fact.id for fact in facts])],
        [theorem_text],
    )


def _line_perpendicular_to_intersection(graph, intersection: tuple[str, str], plane: tuple[str, ...]) -> tuple[tuple[str, str], GeometryFact] | None:
    intersection_set = set(intersection)
    plane_set = set(plane)
    for fact in graph.by_type("perpendicular_lines"):
        first = fact.args.get("first")
        second = fact.args.get("second")
        if not isinstance(first, tuple) or not isinstance(second, tuple):
            continue
        for candidate_intersection, candidate_line in ((first, second), (second, first)):
            if set(candidate_intersection) == intersection_set and set(candidate_line).issubset(plane_set):
                return candidate_line, fact
    for fact in graph.by_type("perpendicular_line_plane"):
        candidate_line = fact.args.get("line")
        fact_plane = set(fact.args.get("plane") or ())
        if not isinstance(candidate_line, tuple):
            continue
        if intersection_set.issubset(fact_plane) and set(candidate_line).issubset(plane_set) and set(candidate_line) & intersection_set:
            return candidate_line, fact
    return None


def _triangle_area_proof(graph, highlight: list[str], answer: str, result_latex: str | None) -> ClassicalProof | None:
    if len(highlight) != 3:
        return None
    triangle = set(highlight)
    for fact in graph.by_type("perpendicular_lines"):
        first = fact.args.get("first")
        second = fact.args.get("second")
        if not isinstance(first, tuple) or not isinstance(second, tuple):
            continue
        common = set(first) & set(second)
        if len(common) != 1 or set(first) | set(second) != triangle:
            continue
        first_label = graph.length_label(*first)
        second_label = graph.length_label(*second)
        if first_label is None or second_label is None:
            continue
        triangle_name = "".join(highlight)
        first_name, second_name = "".join(first), "".join(second)
        theorem_text = theorem("area.triangle.perpendicular_sides").statement
        setup_facts = [fact, *[item for item in graph.by_type("length") if item.args.get("points") in {first, second}]]
        setup = _setup_step(highlight, setup_facts, f"Tam giác {triangle_name} có hai cạnh vuông góc.")
        method = ClassicalProofStep(
            title="Tính diện tích tam giác vuông",
            explanation=f"Vì {first_name} vuông góc {second_name}, tam giác {triangle_name} vuông tại {next(iter(common))}. Dùng hai cạnh góc vuông {first_name} = {first_label} và {second_name} = {second_label}.",
            highlight=highlight,
            kind="area_polygon",
            formula_latex=rf"S_{{{triangle_name}}}=\frac12\cdot {first_name}\cdot {second_name}",
            claim=f"S({triangle_name}) = 1/2·{first_name}·{second_name}",
            theorem=theorem_text,
            depends_on=[item.id for item in setup_facts],
        )
        return ClassicalProof(
            [setup, method, _conclusion(highlight, answer, result_latex, [item.id for item in setup_facts])],
            [theorem_text],
        )
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
    theorem_text = theorem("volume.pyramid.base_height").statement
    setup = _setup_step(highlight, [fact], f"Xét khối chóp có đỉnh {apex}, đáy {base_name} và đường cao ứng viên {segment}.")
    method = ClassicalProofStep(
        title="Nhận ra đáy và chiều cao",
        explanation=f"Vì {segment} vuông góc với mặt phẳng đáy ({base_name}) và {foot} thuộc đáy, nên {segment} là chiều cao của khối chóp.",
        highlight=highlight,
        kind="volume_pyramid",
        formula_latex=rf"V=\frac13 S_{{{base_name}}}\cdot {segment}",
        claim=f"{segment} là chiều cao của khối chóp",
        theorem=theorem_text,
        depends_on=[fact.id],
    )
    if label:
        text = f"Với đáy {base_name} và chiều cao {segment} = {label}, áp dụng V = 1/3·S_đáy·h, suy ra {answer}."
    else:
        text = f"Với đáy {base_name} và chiều cao {segment}, áp dụng V = 1/3·S_đáy·h, suy ra {answer}."
    conclusion = ClassicalProofStep("Kết luận", text, highlight, "result", result_latex=result_latex, claim=answer, depends_on=[fact.id])
    return ClassicalProof([setup, method, conclusion], [theorem_text])


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


def _edge_refs(question: str) -> list[tuple[str, str]]:
    point = r"[A-Z](?:[0-9]+|')?"
    return [
        (match.group(1), match.group(2))
        for match in re.finditer(rf"\b({point})({point})\b", question)
    ]


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