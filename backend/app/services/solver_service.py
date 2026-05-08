from __future__ import annotations

import re
from typing import Any

from app.services.geometry_engine import (
    calculate_line_equation,
    calculate_line_line_angle,
    calculate_line_line_distance,
    calculate_line_plane_angle,
    calculate_plane_equation,
    calculate_plane_plane_angle,
    calculate_point_line_distance,
    calculate_point_line_projection,
    calculate_point_line_reflection,
    calculate_point_plane_distance,
    calculate_point_plane_projection,
    calculate_point_plane_reflection,
    calculate_point_point_distance,
    calculate_polygon_area,
    calculate_pyramid_volume,
    calculate_tetrahedron_volume,
    calculate_vector_cross,
    calculate_vector_dot,
    prove_collinear,
    prove_coplanar,
)
from app.services.cross_check import (
    verify_point_plane_distance as _xc_point_plane_distance,
    verify_tetrahedron_volume as _xc_tetra_volume,
    verify_triangle_area as _xc_triangle_area,
)
from app.services.linalg import Vec3, cross as _cross, dot as _dot, norm as _norm, sub as _sub, vec3


class SolverStep:
    def __init__(
        self,
        index: int,
        title: str,
        explanation: str,
        expression: str | None,
        result: str | None,
        highlight: list[str],
        kind: str | None = None,
        formula_latex: str | None = None,
        substitution_latex: str | None = None,
        result_latex: str | None = None,
    ) -> None:
        self.index = index
        self.title = title
        self.explanation = explanation
        self.expression = expression
        self.result = result
        self.highlight = highlight
        self.kind = kind
        self.formula_latex = formula_latex
        self.substitution_latex = substitution_latex
        self.result_latex = result_latex

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "explanation": self.explanation,
            "expression": self.expression,
            "result": self.result,
            "highlight": self.highlight,
            "kind": self.kind,
            "formula_latex": self.formula_latex,
            "substitution_latex": self.substitution_latex,
            "result_latex": self.result_latex,
        }


class SolverResult:
    def __init__(self, question: str, answer: str, steps: list[SolverStep], warnings: list[str]) -> None:
        self.question = question
        self.answer = answer
        self.steps = steps
        self.warnings = warnings

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "steps": [s.to_dict() for s in self.steps],
            "warnings": self.warnings,
        }


def _latex_to_plain_text(text: str) -> str:
    cleaned = text
    cleaned = re.sub(r"\\overrightarrow\{([^{}]+)\}", r"vector \1", cleaned)
    cleaned = re.sub(r"\\angle\(([^)]+)\)", r"góc(\1)", cleaned)
    cleaned = re.sub(r"\\[a-zA-Z]+(?:\{[^{}]*\})*", " ", cleaned)
    cleaned = cleaned.replace("{", " ").replace("}", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _sanitize_explanation(text: str) -> str:
    return _latex_to_plain_text(text)


_DISTANCE_RE = re.compile(r"kho[aả]ng\s*c[áa]ch|distance|\bd\s*\(", re.IGNORECASE)
_ANGLE_RE = re.compile(r"g[oó]c|angle|cos\s*\(|sin\s*\(", re.IGNORECASE)
_AREA_RE = re.compile(r"di[eệ]n\s*t[íi]ch|area|\bS\s*\(", re.IGNORECASE)
_VECTOR_RE = re.compile(r"vector|vect[ơo]|v[ée]c\s*t[ơo]|tọa\s*độ\s*vector|to[aọ]\s*do\s*vector", re.IGNORECASE)
_VOLUME_RE = re.compile(r"th[eể]\s*t[íi]ch|volume|\bV\s*\(", re.IGNORECASE)
_PARALLEL_RE = re.compile(r"song\s*song|parallel", re.IGNORECASE)
_PERP_RE = re.compile(r"vu[oô]ng\s*g[oó]c|perpendicular", re.IGNORECASE)
_EQUATION_RE = re.compile(r"phương\s*trình|\bpt\b|equation", re.IGNORECASE)
_DOT_RE = re.compile(r"dot\s*\(|tích\s*vô\s*hướng|\.\s*|·", re.IGNORECASE)
_CROSS_RE = re.compile(r"cross\s*\(|tích\s*có\s*hướng|×", re.IGNORECASE)
_PROJECTION_RE = re.compile(r"hình\s*chiếu|projection|project", re.IGNORECASE)
_REFLECTION_RE = re.compile(r"đối\s*xứng|reflection|reflect", re.IGNORECASE)
_COLLINEAR_RE = re.compile(r"thẳng\s*hàng|collinear", re.IGNORECASE)
_COPLANAR_RE = re.compile(r"đồng\s*phẳng|coplanar", re.IGNORECASE)
_POINT_RE = r"[A-Z](?:[0-9]+|')?"


def solve(scene_dict: dict, question: str) -> SolverResult:
    pts = _point_map(scene_dict)
    warnings: list[str] = []
    q = question.strip()

    if _EQUATION_RE.search(q):
        return _solve_equation(pts, q, warnings)
    if _PROJECTION_RE.search(q):
        return _solve_projection(pts, q, warnings)
    if _REFLECTION_RE.search(q):
        return _solve_reflection(pts, q, warnings)
    if _COLLINEAR_RE.search(q):
        return _solve_collinear(pts, q, warnings)
    if _COPLANAR_RE.search(q):
        return _solve_coplanar(pts, q, warnings)
    if _DISTANCE_RE.search(q):
        return _solve_distance(pts, q, warnings)
    if _PARALLEL_RE.search(q):
        return _solve_parallel(pts, q, warnings)
    if _PERP_RE.search(q):
        return _solve_perpendicular(pts, q, warnings)
    if _ANGLE_RE.search(q):
        return _solve_angle(pts, q, warnings)
    if _AREA_RE.search(q):
        return _solve_area(scene_dict, pts, q, warnings)
    if _VOLUME_RE.search(q):
        return _solve_volume(pts, q, warnings)
    if _is_vector_dot_question(q):
        return _solve_vector_operation(pts, q, warnings, "dot")
    if _is_vector_cross_question(q):
        return _solve_vector_operation(pts, q, warnings, "cross")
    if _VECTOR_RE.search(q):
        return _solve_vector(pts, q, warnings)

    warnings.append("Chưa nhận diện được dạng bài. Hãy thử hỏi cụ thể hơn: d(A,B), d(A,BC), d(A,(BCD)), góc giữa AB và CD, S(ABC), V(S.ABCD), phương trình AB, AB . AC, hình chiếu A lên (BCD).")
    return SolverResult(q, "Không xác định", [], warnings)


def _point_map(scene_dict: dict) -> dict[str, Vec3]:
    points: dict[str, Vec3] = {}
    for obj in scene_dict.get("objects", []):
        if obj.get("type") == "point_3d":
            points[obj["name"]] = vec3(float(obj["x"]), float(obj["y"]), float(obj["z"]))
        elif obj.get("type") == "point_2d":
            points[obj["name"]] = vec3(float(obj["x"]), float(obj["y"]), 0.0)
    return points


def _solve_equation(pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    plane_refs = _parse_plane_refs(question)
    if plane_refs:
        return _result_from_calculation(question, calculate_plane_equation(pts, plane_refs[0]), pts)
    edges = _parse_edges(question)
    if edges:
        return _result_from_calculation(question, calculate_line_equation(pts, edges[0]), pts)
    warnings.append("Cần chỉ rõ đường thẳng hoặc mặt phẳng. Ví dụ: phương trình đường thẳng AB, phương trình mặt phẳng (ABC).")
    return SolverResult(question, "Không xác định", [], warnings)


def _solve_projection(pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    parsed = _parse_point_target(question)
    if parsed is None:
        warnings.append("Cần chỉ rõ điểm và đường/mặt phẳng chiếu. Ví dụ: hình chiếu của A lên BC hoặc lên (BCD).")
        return SolverResult(question, "Không xác định", [], warnings)
    point, kind, target = parsed
    if kind == "plane":
        calc = calculate_point_plane_projection(pts, point, list(target))
    else:
        calc = calculate_point_line_projection(pts, point, (target[0], target[1]))
    return _result_from_calculation(question, calc, pts)


def _solve_reflection(pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    parsed = _parse_point_target(question)
    if parsed is None:
        warnings.append("Cần chỉ rõ điểm và đường/mặt phẳng đối xứng. Ví dụ: đối xứng A qua BC hoặc qua (BCD).")
        return SolverResult(question, "Không xác định", [], warnings)
    point, kind, target = parsed
    if kind == "plane":
        calc = calculate_point_plane_reflection(pts, point, list(target))
    else:
        calc = calculate_point_line_reflection(pts, point, (target[0], target[1]))
    return _result_from_calculation(question, calc, pts)


def _solve_collinear(pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    points = _parse_point_sequence(question) or _parse_points(question)
    if len(points) < 3:
        warnings.append("Cần ít nhất 3 điểm để chứng minh thẳng hàng.")
        return SolverResult(question, "Không xác định", [], warnings)
    return _result_from_calculation(question, prove_collinear(pts, points), pts)


def _solve_coplanar(pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    points = _parse_point_sequence(question) or _parse_points(question)
    if len(points) < 3:
        warnings.append("Cần ít nhất 3 điểm để xét đồng phẳng.")
        return SolverResult(question, "Không xác định", [], warnings)
    return _result_from_calculation(question, prove_coplanar(pts, points), pts)


def _solve_vector_operation(pts: dict[str, Vec3], question: str, warnings: list[str], operation: str) -> SolverResult:
    parsed = _parse_vector_operands(question, operation)
    if parsed is None:
        warnings.append("Cần chỉ rõ hai vector. Ví dụ: AB . AC, dot(AB,AC), AB × AC hoặc cross(AB,AC).")
        return SolverResult(question, "Không xác định", [], warnings)
    first, second = parsed
    calc = calculate_vector_dot(pts, first, second) if operation == "dot" else calculate_vector_cross(pts, first, second)
    return _result_from_calculation(question, calc, pts)


def _solve_distance(pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    parsed = _parse_distance(question)
    if parsed is None:
        warnings.append("Không nhận diện được đối tượng. Ví dụ: d(A,B), d(A,BC), d(A,(BCD)).")
        return SolverResult(question, "Không xác định", [], warnings)

    kind, operands = parsed
    if kind == "point_point":
        calc = calculate_point_point_distance(pts, operands[0], operands[1])
    elif kind == "point_line":
        calc = calculate_point_line_distance(pts, operands[0], (operands[1], operands[2]))
    elif kind == "line_line":
        calc = calculate_line_line_distance(pts, (operands[0], operands[1]), (operands[2], operands[3]))
    else:
        calc = calculate_point_plane_distance(pts, operands[0], operands[1:])
    return _result_from_calculation(question, calc, pts)


def _solve_angle(pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    parsed = _parse_angle(question)
    if parsed is None:
        warnings.append("Không nhận diện được góc. Ví dụ: góc ABC, góc giữa AB và CD, góc giữa AB và (BCD).")
        return SolverResult(question, "Không xác định", [], warnings)

    kind, operands = parsed
    if kind == "line_line":
        calc = calculate_line_line_angle(pts, (operands[0], operands[1]), (operands[2], operands[3]))
    elif kind == "line_plane":
        calc = calculate_line_plane_angle(pts, (operands[0], operands[1]), operands[2:])
    elif kind == "plane_plane":
        split = len(operands) // 2
        calc = calculate_plane_plane_angle(pts, operands[:split], operands[split:])
    else:
        calc = calculate_line_line_angle(pts, (operands[1], operands[0]), (operands[1], operands[2]))
        calc["label"] = f"∠{''.join(operands)}"
    return _result_from_calculation(question, calc, pts)


def _solve_area(scene_dict: dict, pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    polygon = _parse_polygon_after_marker(question, "S") or _parse_plane_refs(question)[0] if _parse_plane_refs(question) else None
    if polygon is None:
        polygon = _find_face_points(scene_dict, question) or _parse_point_sequence(question)
    if polygon is None or len(polygon) < 3:
        warnings.append("Không đủ thông tin để tính diện tích. Ví dụ: S(ABC) hoặc diện tích ABCD.")
        return SolverResult(question, "Không xác định", [], warnings)
    return _result_from_calculation(question, calculate_polygon_area(pts, polygon), pts)


def _solve_vector(pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    edges = _parse_edges(question)
    if not edges:
        warnings.append("Cần chỉ rõ vector. Ví dụ: vector AB hoặc tọa độ vector AB.")
        return SolverResult(question, "Không xác định", [], warnings)
    a, b = edges[0]
    missing = [name for name in [a, b] if name not in pts]
    if missing:
        warnings.append(f"Điểm {', '.join(missing)} không có trong scene.")
        return SolverResult(question, "Không xác định", [], warnings)
    vector = _sub(pts[b], pts[a])
    is_2d = abs(vector[2]) <= 1e-12 and all(abs(pts[name][2]) <= 1e-12 for name in [a, b])
    value = f"({_fmt(vector[0], 6)}; {_fmt(vector[1], 6)})" if is_2d else f"({_fmt(vector[0], 6)}; {_fmt(vector[1], 6)}; {_fmt(vector[2], 6)})"
    steps = [
        SolverStep(1, "Xác định vector", f"Vector cần tính là {a}{b}, lấy điểm đầu {a} và điểm cuối {b} từ hình.", None, None, [a, b], kind="input"),
        SolverStep(2, "Trừ tọa độ", f"Tính theo công thức trừ tọa độ: vector {a}{b} = ({b}_x - {a}_x; {b}_y - {a}_y" + ("; {b}_z - {a}_z" if not is_2d else "") + ").", None, None, [a, b], kind="vector"),
        SolverStep(3, "Kết luận", f"Suy ra vector {a}{b} = {value}.", None, value, [a, b], kind="result", result_latex=value),
    ]
    return SolverResult(question, f"vector {a}{b} = {value}", steps, warnings)


def _solve_volume(pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    solid = _parse_solid_after_marker(question, "V") or _parse_solid_text(question)
    if solid and len(solid) == 2:
        apex_or_base, base = solid
        if len(apex_or_base) == 1 and len(base) >= 3:
            return _result_from_calculation(question, calculate_pyramid_volume(pts, apex_or_base[0], base), pts)
        names = [*apex_or_base, *base]
        if len(names) >= 4:
            return _result_from_calculation(question, calculate_tetrahedron_volume(pts, names[:4]), pts)

    points = _parse_point_sequence(question)
    if points and len(points) >= 4:
        return _result_from_calculation(question, calculate_tetrahedron_volume(pts, points[:4]), pts)
    warnings.append("Cần chỉ rõ điểm để tính thể tích. Ví dụ: V(S.ABCD) hoặc V(ABCD).")
    return SolverResult(question, "Không xác định", [], warnings)


def _solve_parallel(pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    edges = _parse_edges(question)
    if len(edges) < 2:
        warnings.append("Cần hai đường thẳng. Ví dụ: AB song song CD.")
        return SolverResult(question, "Không xác định", [], warnings)
    calc = calculate_line_line_angle(pts, edges[0], edges[1])
    if calc["status"] != "ok":
        return _result_from_calculation(question, calc, pts)
    relation = _line_relation_status(pts, edges[0], edges[1])
    is_parallel = abs(calc["result_value"]) < 1e-6 and relation in {"parallel", "coincident"}
    warnings = [*calc["warnings"]]
    if abs(calc["result_value"]) < 1e-6 and relation == "skew":
        warnings.append("Hai đường có vector chỉ phương song song nhưng không đồng phẳng, nên là hai đường chéo nhau trong scene.")
    answer = f"{''.join(edges[0])} song song {''.join(edges[1])}: {'ĐÚNG' if is_parallel else 'SAI'}"
    return SolverResult(question, answer, _steps_from_calculation(calc, pts), warnings)


def _solve_perpendicular(pts: dict[str, Vec3], question: str, warnings: list[str]) -> SolverResult:
    edges = _parse_edges(question)
    if len(edges) < 2:
        warnings.append("Cần hai đường thẳng. Ví dụ: AB vuông góc CD.")
        return SolverResult(question, "Không xác định", [], warnings)
    calc = calculate_line_line_angle(pts, edges[0], edges[1])
    if calc["status"] != "ok":
        return _result_from_calculation(question, calc, pts)
    relation = _line_relation_status(pts, edges[0], edges[1])
    is_perpendicular = abs(calc["result_value"] - 90) < 1e-6 and relation == "intersect"
    warnings = [*calc["warnings"]]
    if abs(calc["result_value"] - 90) < 1e-6 and relation == "skew":
        warnings.append("Hai đường có hướng vuông góc nhưng không cắt nhau, nên là hai đường chéo nhau trong scene.")
    answer = f"{''.join(edges[0])} vuông góc {''.join(edges[1])}: {'ĐÚNG' if is_perpendicular else 'SAI'}"
    return SolverResult(question, answer, _steps_from_calculation(calc, pts), warnings)


def _cross_check_warnings(calc: dict[str, Any], points: dict[str, Vec3] | None) -> list[str]:
    if not points:
        return []
    kind = str(calc.get("kind", ""))
    highlight = [str(name) for name in calc.get("highlight", []) if str(name) in points]
    try:
        if kind == "distance_point_plane" and len(highlight) >= 4:
            point = points[highlight[0]]
            plane_pts = [points[name] for name in highlight[1:4]]
            res = _xc_point_plane_distance(list(point), [list(pt) for pt in plane_pts])
            if not res.consistent:
                return [
                    f"Cross-check khoảng cách: chênh lệch giữa hai cách tính ({res.primary:.6g} vs {res.secondary:.6g}). {res.detail}".strip()
                ]
        elif kind == "area_polygon" and len(highlight) == 3:
            pts3 = [list(points[name]) for name in highlight[:3]]
            res = _xc_triangle_area(pts3)
            if not res.consistent:
                return [
                    f"Cross-check diện tích: chênh lệch giữa cross product và Heron ({res.primary:.6g} vs {res.secondary:.6g}). {res.detail}".strip()
                ]
        elif kind == "volume_tetrahedron" and len(highlight) >= 4:
            pts4 = [list(points[name]) for name in highlight[:4]]
            res = _xc_tetra_volume(pts4)
            if not res.consistent:
                return [
                    f"Cross-check thể tích: chênh lệch giữa định thức và (1/3)·S·h ({res.primary:.6g} vs {res.secondary:.6g}). {res.detail}".strip()
                ]
        elif kind == "volume_pyramid" and len(highlight) >= 4:
            apex = points[highlight[0]]
            base = [list(points[name]) for name in highlight[1:4]]
            res = _xc_tetra_volume([list(apex), *base])
            if not res.consistent:
                return [
                    f"Cross-check thể tích: chênh lệch giữa hai cách tính tứ diện đáy ({res.primary:.6g} vs {res.secondary:.6g}). {res.detail}".strip()
                ]
    except Exception:
        return []
    return []


def _result_from_calculation(question: str, calc: dict[str, Any], points: dict[str, Vec3] | None = None) -> SolverResult:
    if calc["status"] != "ok":
        return SolverResult(question, "Không xác định", [], calc["warnings"])
    unit = "°" if calc.get("unit") == "degrees" else ""
    warnings = [*calc["warnings"], *_pedagogical_warnings(calc), *_cross_check_warnings(calc, points)]
    value = calc.get("result_value")
    if isinstance(value, int | float):
        answer = f"{calc['label']} = {_fmt(value, 6)}{unit}"
    else:
        answer = calc.get("answer") or f"{calc['label']} = {calc['result_latex']}"
    return SolverResult(question, answer, _steps_from_calculation(calc, points), warnings)


def _pedagogical_warnings(calc: dict[str, Any]) -> list[str]:
    value = calc.get("result_value")
    if not isinstance(value, int | float) or abs(value) > 1e-9:
        return []
    kind = calc.get("kind")
    label = calc.get("label", "Kết quả")
    if kind == "distance_point_plane":
        return [f"{label} bằng 0 vì điểm đang nằm trên mặt phẳng trong scene. Nếu hình dựng không đúng đề, hãy chỉnh lại điểm hoặc hỏi khoảng cách từ đỉnh ngoài mặt phẳng đáy."]
    if kind == "distance_point_line":
        return [f"{label} bằng 0 vì điểm đang nằm trên đường thẳng trong scene."]
    if kind == "area_polygon":
        return [f"{label} bằng 0 vì các điểm không tạo thành đa giác có diện tích trong scene."]
    if kind in {"volume_pyramid", "volume_tetrahedron"}:
        return [f"{label} bằng 0 vì các điểm đang đồng phẳng hoặc đáy/chiều cao suy biến trong scene."]
    return []


def _point_text(name: str, points: dict[str, Vec3] | None) -> str:
    if points is None or name not in points:
        return name
    x, y, z = points[name]
    return f"{name}({_fmt(x, 6)}, {_fmt(y, 6)}, {_fmt(z, 6)})"


def _build_step2_detail(calc: dict[str, Any], points: dict[str, Vec3] | None) -> str:
    highlight = [str(value) for value in calc.get("highlight", [])]
    if not highlight:
        return ""

    coords = ", ".join(_point_text(name, points) for name in highlight)
    if points is None:
        return f"Điểm liên quan: {', '.join(highlight)}."

    kind = str(calc.get("kind", ""))

    if kind == "distance_line_line" and len(highlight) >= 4 and all(name in points for name in highlight[:4]):
        a, b, c, d = highlight[:4]
        u = _sub(points[b], points[a])
        v = _sub(points[d], points[c])
        w = _sub(points[c], points[a])
        n = _cross(u, v)
        return (
            f"Chọn gốc tại {a}. Từ tọa độ điểm: {coords}. "
            f"Lập vector chỉ phương u=\\overrightarrow{{{a}{b}}}={_vec_latex(u)}, "
            f"v=\\overrightarrow{{{c}{d}}}={_vec_latex(v)}, "
            f"và vector nối hai đường w=\\overrightarrow{{{a}{c}}}={_vec_latex(w)}. "
            f"Khi đó pháp tuyến chung n=u\\times v={_vec_latex(n)}."
        )

    if kind == "distance_point_line" and len(highlight) >= 3 and all(name in points for name in highlight[:3]):
        p, a, b = highlight[:3]
        ap = _sub(points[p], points[a])
        ab = _sub(points[b], points[a])
        return (
            f"Chọn gốc tại {a}. Từ tọa độ điểm: {coords}. "
            f"Lập \\overrightarrow{{{a}{p}}}={_vec_latex(ap)} và \\overrightarrow{{{a}{b}}}={_vec_latex(ab)} để thay vào công thức."
        )

    if kind == "distance_point_plane" and len(highlight) >= 4 and all(name in points for name in highlight[:4]):
        p = highlight[0]
        a, b, c = highlight[1], highlight[2], highlight[3]
        ab = _sub(points[b], points[a])
        ac = _sub(points[c], points[a])
        ap = _sub(points[p], points[a])
        n = _cross(ab, ac)
        return (
            f"Chọn gốc tại {a} trên mặt phẳng. Từ tọa độ điểm: {coords}. "
            f"Lập \\overrightarrow{{{a}{b}}}={_vec_latex(ab)}, \\overrightarrow{{{a}{c}}}={_vec_latex(ac)}, "
            f"suy ra pháp tuyến \\vec n=\\overrightarrow{{{a}{b}}}\\times\\overrightarrow{{{a}{c}}}={_vec_latex(n)}; "
            f"đồng thời \\overrightarrow{{{a}{p}}}={_vec_latex(ap)}."
        )

    return f"Tọa độ các điểm liên quan: {coords}."


def _steps_from_calculation(calc: dict[str, Any], points: dict[str, Vec3] | None = None) -> list[SolverStep]:
    highlight = calc["highlight"]
    label_plain = _latex_to_plain_text(str(calc["label"]))
    result_latex = str(calc["result_latex"])
    result_plain = _latex_to_plain_text(result_latex)
    return [
        SolverStep(
            1,
            "Xác định dữ liệu đầu vào",
            _sanitize_explanation(f"Bài toán cần tính {label_plain} từ các đối tượng: {', '.join(highlight)}."),
            None,
            None,
            highlight,
            kind="input",
        ),
        SolverStep(
            2,
            "Chọn công thức và thay số",
            f"Dùng công thức hình học không gian deterministic, rồi thay số theo tọa độ. {_build_step2_detail(calc, points)}",
            calc["formula_latex"],
            None,
            highlight,
            kind=calc["kind"],
            formula_latex=calc["formula_latex"],
            substitution_latex=calc["substitution_latex"],
        ),
        SolverStep(
            3,
            "Kết quả",
            _sanitize_explanation(f"Suy ra {label_plain} = {result_plain}."),
            None,
            calc["result_latex"],
            highlight,
            kind="result",
            result_latex=calc["result_latex"],
        ),
    ]


def _is_vector_dot_question(question: str) -> bool:
    return bool(_DOT_RE.search(question) and _parse_vector_operands(question, "dot"))


def _is_vector_cross_question(question: str) -> bool:
    return bool(_CROSS_RE.search(question) and _parse_vector_operands(question, "cross"))


def _parse_vector_operands(question: str, operation: str) -> tuple[tuple[str, str], tuple[str, str]] | None:
    function_name = "dot" if operation == "dot" else "cross"
    inside = _inside_function(question, function_name)
    if inside:
        left, right = _split_two_operands(inside)
        first = _parse_edge_token(left)
        second = _parse_edge_token(right)
        return (first, second) if first and second else None
    operator = r"(?:\.|·)" if operation == "dot" else r"(?:×|x)"
    match = re.search(rf"\b({_POINT_RE}{_POINT_RE})\s*{operator}\s*({_POINT_RE}{_POINT_RE})\b", question)
    if not match:
        return None
    first = _parse_edge_token(match.group(1))
    second = _parse_edge_token(match.group(2))
    return (first, second) if first and second else None


def _parse_point_target(question: str) -> tuple[str, str, tuple[str, ...]] | None:
    plane_refs = _parse_plane_refs(question)
    points = _parse_points(question)
    if plane_refs and points:
        point = next((name for name in points if name not in plane_refs[0]), None)
        if point:
            return point, "plane", tuple(plane_refs[0])
    edges = _parse_edges(question)
    if edges and points:
        point = next((name for name in points if name not in edges[0]), None)
        if point:
            return point, "line", edges[0]
    return None


def _parse_distance(question: str) -> tuple[str, list[str]] | None:
    inside = _inside_function(question, "d")
    if inside:
        first, second = _split_two_operands(inside)
        if first:
            point = _parse_point_token(first)
            plane = _parse_plane_token(second)
            edge = _parse_edge_token(second)
            other_point = _parse_point_token(second)
            first_edge = _parse_edge_token(first)
            if first_edge and edge:
                return "line_line", [*first_edge, *edge]
            if point and plane:
                return "point_plane", [point, *plane]
            if point and edge:
                return "point_line", [point, *edge]
            if point and other_point:
                return "point_point", [point, other_point]

    plane_refs = _parse_plane_refs(question)
    points = _parse_points(question)
    if plane_refs and points:
        first = next((point for point in points if point not in plane_refs[0]), None)
        if first:
            return "point_plane", [first, *plane_refs[0]]
    edges = _parse_edges(question)
    if len(edges) >= 2:
        return "line_line", [*edges[0], *edges[1]]
    if points and edges:
        first = next((point for point in points if point not in edges[0]), None)
        if first:
            return "point_line", [first, *edges[0]]
    if len(points) >= 2:
        return "point_point", points[:2]
    return None


def _parse_angle(question: str) -> tuple[str, list[str]] | None:
    plane_refs = _parse_plane_refs(question)
    edges = _parse_edges(question)
    if len(plane_refs) >= 2:
        return "plane_plane", [*plane_refs[0], *plane_refs[1]]
    if edges and plane_refs:
        return "line_plane", [*edges[0], *plane_refs[0]]
    if len(edges) >= 2:
        return "line_line", [*edges[0], *edges[1]]
    points = _parse_points(question)
    if len(points) >= 3:
        return "three_points", points[:3]
    sequence = _parse_point_sequence(question)
    if sequence and len(sequence) >= 3:
        return "three_points", sequence[:3]
    return None


def _parse_edges(question: str) -> list[tuple[str, str]]:
    planes = {"".join(plane) for plane in _parse_plane_refs(question)}
    edges: list[tuple[str, str]] = []
    for match in re.finditer(rf"(?<![A-Z0-9'])({_POINT_RE})\s*-\s*({_POINT_RE})(?![A-Z0-9'])", question):
        edges.append((match.group(1), match.group(2)))
    for token in re.findall(rf"\b({_POINT_RE}{_POINT_RE})\b", question):
        if token not in planes:
            parsed = _parse_edge_token(token)
            if parsed:
                edges.append(parsed)
    return list(dict.fromkeys(edges))


def _parse_plane_refs(question: str) -> list[list[str]]:
    refs: list[list[str]] = []
    for raw in re.findall(r"\(([A-Z0-9']{3,})\)", question):
        refs.append(_split_point_sequence(raw))
    for raw in re.findall(r"mặt(?:\s+phẳng)?\s+([A-Z0-9']{3,})", question, flags=re.IGNORECASE):
        refs.append(_split_point_sequence(raw))
    return refs


def _parse_points(question: str) -> list[str]:
    return list(dict.fromkeys(re.findall(rf"\b({_POINT_RE})\b", question)))


def _parse_point_sequence(question: str) -> list[str] | None:
    candidates = re.findall(r"\b([A-Z][A-Z0-9']{2,})\b", question)
    for candidate in candidates:
        points = _split_point_sequence(candidate)
        if len(points) >= 3:
            return points
    return None


def _parse_polygon_after_marker(question: str, marker: str) -> list[str] | None:
    inside = _inside_function(question, marker)
    if inside:
        return _parse_plane_token(inside) or _split_point_sequence(inside)
    return None


def _parse_solid_after_marker(question: str, marker: str) -> tuple[list[str], list[str]] | None:
    inside = _inside_function(question, marker)
    if not inside or "." not in inside:
        return None
    left, right = inside.split(".", 1)
    return _split_point_sequence(left), _split_point_sequence(right)


def _parse_solid_text(question: str) -> tuple[list[str], list[str]] | None:
    match = re.search(r"([A-Z0-9']+)\.([A-Z0-9']+)", question)
    if not match:
        return None
    return _split_point_sequence(match.group(1)), _split_point_sequence(match.group(2))


def _find_face_points(scene_dict: dict, question: str) -> list[str] | None:
    sequence = _parse_point_sequence(question)
    if sequence:
        return sequence
    for obj in scene_dict.get("objects", []):
        if obj.get("type") == "face" and obj.get("points"):
            return obj["points"]
    return None


def _inside_function(question: str, name: str) -> str | None:
    match = re.search(rf"\b{name}\s*\(([^)]*)\)", question, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _split_two_operands(value: str) -> tuple[str, str]:
    if "," in value:
        left, right = value.split(",", 1)
        return left.strip(), right.strip()
    parts = value.split()
    if len(parts) >= 2:
        return parts[0], parts[1]
    return value.strip(), ""


def _parse_point_token(token: str) -> str | None:
    match = re.fullmatch(_POINT_RE, token.strip())
    return match.group(0) if match else None


def _parse_edge_token(token: str) -> tuple[str, str] | None:
    cleaned = token.strip().replace(" ", "")
    if "-" in cleaned:
        left, right = cleaned.split("-", 1)
        if _parse_point_token(left) and _parse_point_token(right):
            return left, right
    points = _split_point_sequence(cleaned)
    if len(points) == 2:
        return points[0], points[1]
    return None


def _parse_plane_token(token: str) -> list[str] | None:
    cleaned = token.strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1]
    cleaned = re.sub(r"^mặt\s+", "", cleaned, flags=re.IGNORECASE).strip()
    points = _split_point_sequence(cleaned)
    return points if len(points) >= 3 else None


def _split_point_sequence(value: str) -> list[str]:
    return re.findall(_POINT_RE, value.replace(" ", ""))


def _line_relation_status(pts: dict[str, Vec3], edge_1: tuple[str, str], edge_2: tuple[str, str]) -> str:
    a, b = edge_1
    c, d = edge_2
    if any(name not in pts for name in [a, b, c, d]):
        return "missing"
    p, q = pts[a], pts[c]
    u = _sub(pts[b], pts[a])
    v = _sub(pts[d], pts[c])
    cross = _cross(u, v)
    if _norm(cross) <= 1e-9:
        return "coincident" if _norm(_cross(_sub(q, p), u)) <= 1e-6 else "parallel"
    distance = abs(_dot(_sub(q, p), cross)) / _norm(cross)
    return "intersect" if distance <= 1e-6 else "skew"


def _fmt(value: float, digits: int = 4) -> str:
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return text or "0"


def _vec_latex(value: Vec3) -> str:
    return f"({_fmt(value[0])},{_fmt(value[1])},{_fmt(value[2])})"
