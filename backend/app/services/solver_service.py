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
    calculate_prism_volume,
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
        sub_steps: list["SolverStep"] | None = None,
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
        self.sub_steps = sub_steps or []

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
            "sub_steps": [s.to_dict() for s in self.sub_steps],
        }


class SolverResult:
    def __init__(
        self,
        question: str,
        answer: str,
        steps: list[SolverStep],
        warnings: list[str],
        *,
        confidence: str = "verified",
        method: str = "oxyz",
        used_facts: list[dict[str, str]] | None = None,
        data_issues: list[str] | None = None,
    ) -> None:
        self.question = question
        self.answer = answer
        self.steps = steps
        self.warnings = warnings
        self.confidence = confidence
        self.method = method
        self.used_facts = used_facts or []
        self.data_issues = data_issues or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "steps": [s.to_dict() for s in self.steps],
            "warnings": self.warnings,
            "confidence": self.confidence,
            "method": self.method,
            "used_facts": self.used_facts,
            "data_issues": self.data_issues,
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


def normalize_solver_question(question: str) -> str:
    q = question.strip()
    if not q:
        return ""
    replacements = {
        "​": "",
        "‌": "",
        "‍": "",
        "（": "(",
        "）": ")",
        "，": ",",
        "、": ",",
        "−": "-",
        "–": "-",
        "—": "-",
        "✕": "×",
        "*": "×",
        "·": ".",
        "•": ".",
    }
    for old, new in replacements.items():
        q = q.replace(old, new)
    q = re.sub(r"\s+", " ", q).strip()
    q = re.sub(r"\b(?:k/c|kc|khoang\s+cach|khoảng\s+cách)\b", "d", q, flags=re.IGNORECASE)
    q = re.sub(r"\b(?:den|đến|toi|tới|tu|từ|cua|của)\b", " ", q, flags=re.IGNORECASE)
    q = re.sub(r"\b(?:mp|mat\s+phang|mặt\s+phẳng)\s+([A-Za-z](?:\s*[A-Za-z0-9']\s*){2,})", lambda m: f"({ _compact_point_sequence_text(m.group(1)) })", q, flags=re.IGNORECASE)
    q = re.sub(r"\b(?:dien\s+tich|diện\s+tích)\s+([A-Za-z](?:\s*[A-Za-z0-9']\s*){2,})", lambda m: f"S({_compact_point_sequence_text(m.group(1))})", q, flags=re.IGNORECASE)
    q = re.sub(r"\b(?:the\s+tich|thể\s+tích)\s+([A-Za-z][A-Za-z0-9']*(?:\s*\.\s*)?[A-Za-z](?:\s*[A-Za-z0-9']\s*){2,})", lambda m: f"V({_compact_solid_text(m.group(1))})", q, flags=re.IGNORECASE)
    q = re.sub(r"\b([dDsSvV])\s*\(", lambda m: f"{m.group(1).upper()}(" if m.group(1).lower() in {"s", "v"} else "d(", q)
    q = _normalize_parenthesized_geometry(q)
    q = re.sub(r"\bd\s+([A-Za-z](?:[0-9]+|')?)\s+(\([A-Za-z0-9'\s]+\)|[A-Za-z](?:\s*[A-Za-z0-9']\s*){1,})", lambda m: f"d({m.group(1).upper()},{_normalize_distance_target_text(m.group(2))})", q, flags=re.IGNORECASE)
    q = _uppercase_geometry_tokens(q)
    q = re.sub(r"\s+", " ", q).strip()
    q = re.sub(r"\bGOC\b", "góc", q, flags=re.IGNORECASE)
    return q


def _normalize_distance_target_text(value: str) -> str:
    target = value.strip()
    if target.startswith("(") and target.endswith(")"):
        return f"({_compact_point_sequence_text(target[1:-1])})"
    return _compact_point_sequence_text(target)


def _uppercase_geometry_tokens(value: str) -> str:
    return re.sub(r"\b([A-Za-z](?:[0-9]+|')?)\s*-\s*([A-Za-z](?:[0-9]+|')?)\b", lambda m: f"{m.group(1).upper()}-{m.group(2).upper()}", value)


def _compact_point_sequence_text(value: str) -> str:
    return "".join(re.findall(r"[A-Za-z](?:[0-9]+|')?", value)).upper()


def _compact_solid_text(value: str) -> str:
    cleaned = value.strip().replace(" ", "")
    if "." in cleaned:
        left, right = cleaned.split(".", 1)
        return f"{_compact_point_sequence_text(left)}.{_compact_point_sequence_text(right)}"
    compact = _compact_point_sequence_text(value)
    return f"{compact[0]}.{compact[1:]}" if len(compact) >= 4 else compact


def _normalize_parenthesized_geometry(question: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(question):
        char = question[index]
        if char != "(":
            result.append(char)
            index += 1
            continue
        end = _find_matching_paren(question, index)
        if end is None:
            result.append(char)
            index += 1
            continue
        inner = _normalize_parenthesized_geometry(question[index + 1:end])
        if re.fullmatch(r"[A-Za-z0-9'\s.]+", inner):
            inner = _compact_solid_text(inner) if "." in inner else _compact_point_sequence_text(inner)
        result.append(f"({inner})")
        index = end + 1
    return "".join(result)


def solve(scene_dict: dict, question: str, geometry_method: str = "oxyz") -> SolverResult:
    pts = _point_map(scene_dict)
    warnings: list[str] = _scene_reliability_warnings(scene_dict)
    q = normalize_solver_question(question)

    guard = _metric_data_guard(scene_dict, q)
    if guard:
        result = SolverResult(q, "Không đủ dữ kiện", [], [*warnings, guard])
        _apply_result_metadata(result, scene_dict, geometry_method)
        return result

    if _EQUATION_RE.search(q):
        result = _solve_equation(pts, q, warnings)
    elif _PROJECTION_RE.search(q):
        result = _solve_projection(pts, q, warnings)
    elif _REFLECTION_RE.search(q):
        result = _solve_reflection(pts, q, warnings)
    elif _COLLINEAR_RE.search(q):
        result = _solve_collinear(pts, q, warnings)
    elif _COPLANAR_RE.search(q):
        result = _solve_coplanar(pts, q, warnings)
    elif _DISTANCE_RE.search(q):
        result = _solve_distance(pts, q, warnings)
    elif _PARALLEL_RE.search(q):
        result = _solve_parallel(pts, q, warnings)
    elif _PERP_RE.search(q):
        result = _solve_perpendicular(pts, q, warnings)
    elif _ANGLE_RE.search(q):
        result = _solve_angle(pts, q, warnings)
    elif _AREA_RE.search(q):
        result = _solve_area(scene_dict, pts, q, warnings)
    elif _VOLUME_RE.search(q):
        result = _solve_volume(pts, q, warnings)
    elif _is_vector_dot_question(q):
        result = _solve_vector_operation(pts, q, warnings, "dot")
    elif _is_vector_cross_question(q):
        result = _solve_vector_operation(pts, q, warnings, "cross")
    elif _VECTOR_RE.search(q):
        result = _solve_vector(pts, q, warnings)
    else:
        warnings.append("Chưa nhận diện được dạng bài. Hãy thử hỏi cụ thể hơn: d(A,B), d(A,BC), d(A,(BCD)), góc giữa AB và CD, S(ABC), V(S.ABCD), phương trình AB, AB . AC, hình chiếu A lên (BCD).")
        result = SolverResult(q, "Không xác định", [], warnings)

    _prepend_context_warnings(result, warnings)
    if geometry_method == "classical":
        result = _classicalize_result(result, scene_dict, pts)
    _apply_result_metadata(result, scene_dict, geometry_method)
    return result


def _apply_result_metadata(result: SolverResult, scene_dict: dict, method: str) -> None:
    result.method = method if method in {"oxyz", "classical"} else "oxyz"
    result.data_issues = _result_data_issues(result)
    result.confidence = _result_confidence(result)
    result.used_facts = _solver_used_facts(scene_dict, _result_highlights(result), result)


def _result_highlights(result: SolverResult) -> list[str]:
    names: list[str] = []
    for step in result.steps:
        for name in step.highlight:
            if name not in names:
                names.append(name)
    return names


def _result_data_issues(result: SolverResult) -> list[str]:
    issue_markers = (
        "không đủ dữ kiện",
        "không dùng tọa độ minh họa",
        "cảnh báo cas",
        "scene còn cảnh báo cas",
        "giá trị mặc định",
        "suy biến",
        "đang nằm trên",
        "không gọi được",
        "cross-check",
    )
    issues = [
        warning for warning in result.warnings
        if any(marker in warning.lower() for marker in issue_markers)
    ]
    return list(dict.fromkeys(issues))


def _result_confidence(result: SolverResult) -> str:
    if result.answer in {"Không đủ dữ kiện", "Không xác định"}:
        return "insufficient"
    if result.data_issues:
        return "partial"
    return "verified"


def _prepend_context_warnings(result: SolverResult, context_warnings: list[str]) -> None:
    if not context_warnings:
        return
    merged = [*context_warnings]
    for warning in result.warnings:
        if warning not in merged:
            merged.append(warning)
    result.warnings = merged


def _scene_reliability_warnings(scene_dict: dict) -> list[str]:
    warnings: list[str] = []
    unresolved = [
        issue for issue in scene_dict.get("cas_issues", [])
        if isinstance(issue, dict) and not bool(issue.get("auto_fixed"))
    ]
    if unresolved:
        warnings.append("Scene còn cảnh báo CAS chưa tự sửa; lời giải chỉ đáng tin nếu các dữ kiện liên quan không nằm trong cảnh báo đó.")
    if scene_dict.get("parameters"):
        names = ", ".join(str(item.get("name")) for item in scene_dict.get("parameters", []) if isinstance(item, dict) and item.get("name"))
        if names:
            warnings.append(f"Scene có tham số ({names}); kết quả số hiện tính theo giá trị mặc định của tham số.")
    return warnings


def _metric_data_guard(scene_dict: dict, question: str) -> str | None:
    if not scene_dict.get("problem_text"):
        return None
    if scene_dict.get("topic") in {"coordinate_2d", "coordinate_3d"}:
        return None
    metric_query = any(regex.search(question) for regex in (_DISTANCE_RE, _ANGLE_RE, _AREA_RE, _VOLUME_RE))
    if not metric_query:
        return None
    if _ANGLE_RE.search(question) and _has_angle_evidence(scene_dict):
        return None
    if _has_metric_evidence(scene_dict):
        return None
    return (
        "Đề/scene hiện không có dữ kiện định lượng đã kiểm chứng cho đại lượng cần tính. "
        "Hệ thống không dùng tọa độ minh họa do AI tự chọn để kết luận số học."
    )


def _has_metric_evidence(scene_dict: dict) -> bool:
    if scene_dict.get("parameters"):
        return True
    for obj in scene_dict.get("objects", []):
        if not isinstance(obj, dict):
            continue
        if any(isinstance(obj.get(field), str) and obj.get(field) for field in ("x_expr", "y_expr", "z_expr", "radius_expr")):
            return True
    for rel in scene_dict.get("relations", []):
        if not isinstance(rel, dict):
            continue
        metadata = rel.get("metadata") if isinstance(rel.get("metadata"), dict) else {}
        if (
            rel.get("type") in {"distance", "angle", "equal_length"}
            and any(key in metadata for key in ("value", "length", "angle"))
            and _metadata_is_usable_fact(metadata, default=True)
        ):
            return True
    for ann in scene_dict.get("annotations", []):
        if not isinstance(ann, dict):
            continue
        metadata = ann.get("metadata") if isinstance(ann.get("metadata"), dict) else {}
        if (
            ann.get("type") in {"length", "angle"}
            and _looks_metric_label(ann.get("label"))
            and _metadata_is_usable_fact(metadata, default=True)
        ):
            return True
    return False


def _looks_metric_label(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    return bool(re.search(r"\d|sqrt|√|\b[a-z]\b", text, flags=re.IGNORECASE))


def _has_angle_evidence(scene_dict: dict) -> bool:
    for rel in scene_dict.get("relations", []):
        if not isinstance(rel, dict):
            continue
        metadata = rel.get("metadata") if isinstance(rel.get("metadata"), dict) else {}
        if rel.get("type") in {"angle", "perpendicular", "parallel"} and _metadata_is_usable_fact(metadata, default=True):
            return True
    for ann in scene_dict.get("annotations", []):
        if not isinstance(ann, dict):
            continue
        metadata = ann.get("metadata") if isinstance(ann.get("metadata"), dict) else {}
        if ann.get("type") in {"angle", "right_angle"} and _metadata_is_usable_fact(metadata, default=True):
            return True
    return False


def _metadata_is_usable_fact(metadata: dict[str, Any], *, default: bool) -> bool:
    source = metadata.get("source")
    confidence = metadata.get("confidence")
    if source is None and confidence is None:
        return default
    if source == "construction" or confidence == "unverified":
        return False
    return source in {None, "given", "inferred"} and confidence in {None, "verified", "partial"}


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
        top_or_apex, base = solid
        if len(top_or_apex) == 1 and len(base) >= 3:
            return _result_from_calculation(question, calculate_pyramid_volume(pts, top_or_apex[0], base), pts)
        if len(top_or_apex) >= 3 and len(base) >= 3:
            return _result_from_calculation(question, calculate_prism_volume(pts, top_or_apex, base), pts)
        names = [*top_or_apex, *base]
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


def _classicalize_result(result: SolverResult, scene_dict: dict, points: dict[str, Vec3]) -> SolverResult:
    if result.answer in {"Không xác định", "Không đủ dữ kiện"} or len(result.steps) < 2:
        return result
    kind = result.steps[1].kind or ""
    highlight = result.steps[1].highlight
    if not kind:
        return result
    if kind == "volume_pyramid" and _pyramid_volume_fact(scene_dict, highlight) is None:
        warnings = [
            *result.warnings,
            "Mode Tương quan hình học chưa xác định được chiều cao khối chóp từ quan hệ vuông góc đã kiểm chứng; không dùng tọa độ minh họa để kết luận thể tích.",
        ]
        return SolverResult(result.question, "Không đủ dữ kiện", [], warnings)

    facts = _relevant_scene_facts(scene_dict, highlight)
    fact_sub_steps = [
        SolverStep(index + 1, "Dữ kiện từ đề/hình", fact, None, None, highlight, kind="fact")
        for index, fact in enumerate(facts[:6])
    ]
    if not fact_sub_steps:
        fact_sub_steps = [SolverStep(1, "Dữ kiện từ hình", f"Các đối tượng liên quan là {', '.join(highlight)}.", None, None, highlight, kind="fact")]

    setup = SolverStep(
        1,
        "Xác định dữ kiện hình học",
        "Chỉ dùng các điểm, quan hệ và nhãn đã có trong scene; không thêm giả thiết ngoài đề.",
        None,
        None,
        highlight,
        kind="input",
        sub_steps=fact_sub_steps,
    )
    point_plane_height = _point_plane_height_fact(scene_dict, highlight) if kind == "distance_point_plane" else None
    line_plane_projection = _line_plane_projection_fact(scene_dict, result.question, highlight) if kind == "angle_line_plane" else None
    plane_plane_angle = _plane_plane_angle_fact(scene_dict, result.question) if kind == "angle_plane_plane" else None
    pyramid_volume = _pyramid_volume_fact(scene_dict, highlight) if kind == "volume_pyramid" else None
    method_step = _classical_method_step(kind, highlight, result.question, scene_dict)
    conclusion = SolverStep(
        3,
        "Kết luận",
        _classical_conclusion_text(
            kind,
            highlight,
            result.answer,
            point_plane_height,
            line_plane_projection,
            plane_plane_angle,
            pyramid_volume,
        ),
        None,
        result.steps[-1].result,
        highlight,
        kind="result",
        result_latex=result.steps[-1].result_latex,
    )
    result.steps = [setup, method_step, conclusion]
    result.warnings = [
        *result.warnings,
        "Mode Tương quan hình học đang dùng template deterministic an toàn; AI không được phép tự thêm định lý, dữ kiện hoặc thay đổi kết quả.",
    ]
    return result


def _classical_method_step(kind: str, highlight: list[str], question: str = "", scene_dict: dict | None = None) -> SolverStep:
    label = ", ".join(highlight)
    if kind == "distance_point_plane" and len(highlight) >= 4:
        p, *plane = highlight[:4]
        plane_name = "".join(plane)
        height = _point_plane_height_fact(scene_dict or {}, highlight)
        if height:
            foot = height["foot"]
            segment = height["segment"]
            return SolverStep(
                2,
                "Nhận ra đường cao",
                f"Vì {segment} vuông góc với mặt phẳng ({plane_name}) và {foot} thuộc ({plane_name}), nên {segment} là đoạn vuông góc kẻ từ {p} đến ({plane_name}). Do đó khoảng cách cần tìm là {segment}.",
                None,
                None,
                highlight,
                kind=kind,
                formula_latex=rf"{segment}\perp({plane_name}),\ {foot}\in({plane_name})\Rightarrow d({p},({plane_name}))={segment}",
            )
        return SolverStep(
            2,
            "Dựng khoảng cách điểm đến mặt phẳng",
            f"Gọi H là hình chiếu vuông góc của {p} lên mặt phẳng ({plane_name}). Khi đó khoảng cách cần tìm là độ dài {p}H.",
            None,
            None,
            highlight,
            kind=kind,
            formula_latex=rf"d({p},({plane_name}))={p}H,\ {p}H\perp({plane_name})",
        )
    if kind == "distance_point_line" and len(highlight) >= 3:
        p, a, b = highlight[:3]
        return SolverStep(
            2,
            "Dựng khoảng cách điểm đến đường thẳng",
            f"Gọi H là hình chiếu vuông góc của {p} lên đường thẳng {a}{b}. Khi đó khoảng cách cần tìm là {p}H.",
            None,
            None,
            highlight,
            kind=kind,
            formula_latex=rf"d({p},{a}{b})={p}H,\ {p}H\perp {a}{b}",
        )
    if kind == "distance_point_point" and len(highlight) >= 2:
        a, b = highlight[:2]
        return SolverStep(
            2,
            "Xét đoạn thẳng cần đo",
            f"Khoảng cách giữa hai điểm {a} và {b} chính là độ dài đoạn thẳng {a}{b}.",
            None,
            None,
            highlight,
            kind=kind,
            formula_latex=rf"d({a},{b})={a}{b}",
        )
    if kind == "distance_line_line" and len(highlight) >= 4:
        a, b, c, d = highlight[:4]
        return SolverStep(
            2,
            "Dựng đoạn vuông góc chung",
            f"Khoảng cách giữa {a}{b} và {c}{d} là độ dài đoạn vuông góc chung nếu hai đường chéo nhau, hoặc khoảng cách từ một điểm trên đường này đến đường kia nếu chúng song song.",
            None,
            None,
            highlight,
            kind=kind,
        )
    if kind == "angle_line_plane" and len(highlight) >= 2:
        a, b = highlight[:2]
        plane_ref = _first_plane_ref(question, highlight)
        plane = "".join(plane_ref) if plane_ref else "".join(highlight[2:5])
        projection = _line_plane_projection_fact(scene_dict or {}, question, highlight)
        if projection and projection.get("perpendicular_line") == "true":
            line = f"{a}{b}"
            return SolverStep(
                2,
                "Nhận ra đường vuông góc mặt phẳng",
                f"Vì {line} vuông góc với mặt phẳng ({plane}), nên góc giữa {line} và ({plane}) bằng 90°.",
                None,
                None,
                highlight,
                kind=kind,
                formula_latex=rf"{line}\perp({plane})\Rightarrow \widehat{{({line},({plane}))}}=90^\circ",
            )
        if projection:
            outside = projection["outside"]
            plane_point = projection["plane_point"]
            foot = projection["foot"]
            projected_line = projection["projected_line"]
            angle_name = projection["angle_name"]
            return SolverStep(
                2,
                "Dùng hình chiếu trên mặt phẳng",
                f"Gọi {foot} là hình chiếu của {outside} lên ({plane}). Vì {plane_point} thuộc ({plane}), nên hình chiếu của {a}{b} trên ({plane}) là {projected_line}. Do đó góc giữa {a}{b} và ({plane}) là góc {angle_name}.",
                None,
                None,
                highlight,
                kind=kind,
                formula_latex=rf"\widehat{{({a}{b},({plane}))}}=\widehat{{{angle_name}}}",
            )
        return SolverStep(
            2,
            "Dùng hình chiếu của đường thẳng",
            f"Góc giữa {a}{b} và mặt phẳng ({plane}) là góc giữa {a}{b} và hình chiếu của nó trên mặt phẳng đó.",
            None,
            None,
            highlight,
            kind=kind,
            formula_latex=rf"\widehat{{({a}{b},({plane}))}}=\widehat{{({a}{b},d')}}",
        )
    if kind == "angle_line_line" and len(highlight) >= 4:
        a, b, c, d = highlight[:4]
        return SolverStep(
            2,
            "Quy về góc giữa hai đường cắt nhau",
            f"Góc giữa {a}{b} và {c}{d} được hiểu là góc giữa hai đường thẳng lần lượt song song với chúng và cùng đi qua một điểm.",
            None,
            None,
            highlight,
            kind=kind,
        )
    if kind == "angle_plane_plane":
        plane_refs = _parse_plane_refs(question)
        first_plane = "".join(plane_refs[0]) if len(plane_refs) >= 1 else "P"
        second_plane = "".join(plane_refs[1]) if len(plane_refs) >= 2 else "Q"
        plane_angle = _plane_plane_angle_fact(scene_dict or {}, question)
        if plane_angle:
            intersection = plane_angle["intersection"]
            first_line = plane_angle["first_line"]
            second_line = plane_angle["second_line"]
            vertex = plane_angle["vertex"]
            angle_name = plane_angle["angle_name"]
            return SolverStep(
                2,
                "Dựng góc phẳng nhị diện",
                f"Hai mặt phẳng ({first_plane}) và ({second_plane}) cắt nhau theo {intersection}. Trong ({first_plane}) có {first_line} vuông góc {intersection} tại {vertex}; trong ({second_plane}) có {second_line} vuông góc {intersection} tại {vertex}. Vì vậy góc giữa hai mặt phẳng là góc {angle_name}.",
                None,
                None,
                highlight,
                kind=kind,
                formula_latex=rf"{first_line}\perp {intersection},\ {second_line}\perp {intersection}\Rightarrow \widehat{{(({first_plane}),({second_plane}))}}=\widehat{{{angle_name}}}",
            )
        return SolverStep(
            2,
            "Dựng góc giữa hai mặt phẳng",
            f"Tìm giao tuyến của hai mặt phẳng ({first_plane}) và ({second_plane}). Trong mỗi mặt phẳng, dựng một đường thẳng vuông góc với giao tuyến tại cùng một điểm; góc giữa hai đường đó là góc giữa hai mặt phẳng.",
            None,
            None,
            highlight,
            kind=kind,
            formula_latex=rf"\widehat{{(({first_plane}),({second_plane}))}}=\widehat{{(d_1,d_2)}}",
        )
    if kind == "area_polygon":
        polygon = "".join(highlight)
        return SolverStep(
            2,
            "Tính diện tích theo đáy và chiều cao",
            f"Xét đa giác {polygon}; chọn cách chia hoặc chọn đáy - chiều cao phù hợp với các dữ kiện đã có trên hình.",
            None,
            None,
            highlight,
            kind=kind,
        )
    if kind in {"volume_pyramid", "volume_tetrahedron"} and len(highlight) >= 4:
        apex = highlight[0]
        base = "".join(highlight[1:])
        pyramid_volume = _pyramid_volume_fact(scene_dict or {}, highlight) if kind == "volume_pyramid" else None
        if pyramid_volume:
            height_segment = pyramid_volume["height_segment"]
            foot = pyramid_volume["foot"]
            return SolverStep(
                2,
                "Nhận ra đáy và chiều cao",
                f"Xem {base} là đáy của khối chóp. Vì {height_segment} vuông góc với mặt phẳng ({base}) và {foot} thuộc ({base}), nên {height_segment} là chiều cao của khối chóp.",
                None,
                None,
                highlight,
                kind=kind,
                formula_latex=rf"V_{{{apex}.{base}}}=\frac{{1}}{{3}}S_{{{base}}}\cdot {height_segment}",
            )
        return SolverStep(
            2,
            "Tính thể tích theo đáy và chiều cao",
            f"Xem {base} là đáy và dựng chiều cao từ {apex} xuống mặt phẳng đáy. Thể tích bằng một phần ba diện tích đáy nhân chiều cao.",
            None,
            None,
            highlight,
            kind=kind,
            formula_latex=rf"V=\frac{{1}}{{3}}S_{{{base}}}\cdot h",
        )
    if kind == "volume_prism" and len(highlight) >= 6:
        return SolverStep(
            2,
            "Tính thể tích lăng trụ",
            "Thể tích lăng trụ bằng diện tích đáy nhân với chiều cao tương ứng.",
            None,
            None,
            highlight,
            kind=kind,
            formula_latex=r"V=S_{\text{đáy}}\cdot h",
        )
    if kind == "proof_collinear" and len(highlight) >= 3:
        return SolverStep(
            2,
            "Kiểm tra quan hệ thẳng hàng",
            f"Chọn một đường thẳng đi qua hai điểm đầu, rồi kiểm tra các điểm còn lại có cùng nằm trên đường thẳng đó hay không.",
            None,
            None,
            highlight,
            kind=kind,
        )
    if kind == "proof_coplanar" and len(highlight) >= 4:
        return SolverStep(
            2,
            "Kiểm tra quan hệ đồng phẳng",
            f"Chọn mặt phẳng đi qua ba điểm không thẳng hàng đầu tiên, rồi kiểm tra các điểm còn lại có thuộc mặt phẳng đó hay không.",
            None,
            None,
            highlight,
            kind=kind,
        )
    return SolverStep(
        2,
        "Chọn định nghĩa hình học phù hợp",
        f"Dạng này chưa có template THPT chuyên biệt, nên hệ thống chỉ trình bày các đối tượng liên quan: {label}.",
        None,
        None,
        highlight,
        kind=kind,
    )


def _classical_conclusion_text(
    kind: str,
    highlight: list[str],
    answer: str,
    point_plane_height: dict[str, str] | None,
    line_plane_projection: dict[str, str] | None = None,
    plane_plane_angle: dict[str, str] | None = None,
    pyramid_volume: dict[str, str] | None = None,
) -> str:
    if kind == "distance_point_plane" and len(highlight) >= 4 and point_plane_height:
        p = highlight[0]
        plane_name = "".join(highlight[1:4])
        segment = point_plane_height["segment"]
        length_label = point_plane_height.get("length_label")
        if length_label:
            return f"Mà {segment} = {length_label}, nên d({p},({plane_name})) = {segment} = {length_label}."
        return f"Vì {segment} là đoạn vuông góc từ {p} đến ({plane_name}), nên {answer}."
    if kind == "angle_line_plane" and len(highlight) >= 2 and line_plane_projection:
        line = "".join(highlight[:2])
        plane_name = line_plane_projection["plane"]
        if line_plane_projection.get("perpendicular_line") == "true":
            return f"Vì {line} vuông góc với ({plane_name}), nên góc giữa {line} và ({plane_name}) bằng 90°."
        angle_name = line_plane_projection["angle_name"]
        return f"Vì hình chiếu của {line} trên ({plane_name}) đã xác định, nên góc giữa {line} và ({plane_name}) là góc {angle_name}; do đó {answer}."
    if kind == "angle_plane_plane" and plane_plane_angle:
        first_plane = plane_plane_angle["first_plane"]
        second_plane = plane_plane_angle["second_plane"]
        angle_name = plane_plane_angle["angle_name"]
        return f"Vì góc phẳng nhị diện giữa ({first_plane}) và ({second_plane}) là góc {angle_name}, nên {answer}."
    if kind == "volume_pyramid" and pyramid_volume:
        apex = pyramid_volume["apex"]
        base = pyramid_volume["base"]
        height_segment = pyramid_volume["height_segment"]
        height_label = pyramid_volume.get("height_label")
        if height_label:
            return f"Với đáy {base} và chiều cao {height_segment} = {height_label}, áp dụng V = 1/3·S_đáy·h, suy ra {answer}."
        return f"Với đáy {base} và chiều cao {height_segment}, áp dụng V = 1/3·S_đáy·h, suy ra {answer}."
    return f"Dựa trên các dữ kiện hình học đã kiểm chứng, suy ra {answer}."


def _first_plane_ref(question: str, highlight: list[str]) -> list[str] | None:
    plane_refs = _parse_plane_refs(question)
    if plane_refs:
        return plane_refs[0]
    if len(highlight) >= 5:
        return highlight[2:5]
    return None


def _point_plane_height_fact(scene_dict: dict, highlight: list[str]) -> dict[str, str] | None:
    if len(highlight) < 4:
        return None
    point = highlight[0]
    plane = highlight[1:4]
    plane_set = set(plane)
    for rel in scene_dict.get("relations", []):
        if not isinstance(rel, dict) or str(rel.get("type") or "").strip().lower() != "perpendicular":
            continue
        metadata = rel.get("metadata") if isinstance(rel.get("metadata"), dict) else {}
        if not _metadata_is_usable_fact(metadata, default=True):
            continue
        object_1 = str(rel.get("object_1") or "")
        object_2 = str(rel.get("object_2") or "")
        segment = _parse_edge_token(object_1)
        plane_ref = _parse_plane_token(object_2)
        if segment is None or plane_ref is None:
            segment = _parse_edge_token(object_2)
            plane_ref = _parse_plane_token(object_1)
        if segment is None or plane_ref is None:
            continue
        if set(plane_ref) != plane_set or point not in segment:
            continue
        foot = segment[1] if segment[0] == point else segment[0]
        if foot not in plane_set:
            continue
        ordered_segment = f"{point}{foot}"
        return {
            "foot": foot,
            "segment": ordered_segment,
            "length_label": _length_label_for_segment(scene_dict, point, foot) or "",
        }
    return None


def _line_plane_projection_fact(scene_dict: dict, question: str, highlight: list[str]) -> dict[str, str] | None:
    if len(highlight) < 2:
        return None
    line = (highlight[0], highlight[1])
    plane_ref = _first_plane_ref(question, highlight)
    if plane_ref is None:
        return None
    plane_set = set(plane_ref)
    plane_name = "".join(plane_ref)
    line_set = set(line)

    for rel in scene_dict.get("relations", []):
        if not isinstance(rel, dict) or str(rel.get("type") or "").strip().lower() != "perpendicular":
            continue
        metadata = rel.get("metadata") if isinstance(rel.get("metadata"), dict) else {}
        if not _metadata_is_usable_fact(metadata, default=True):
            continue

        segment, relation_plane = _perpendicular_segment_plane(rel)
        if segment is None or relation_plane is None or set(relation_plane) != plane_set:
            continue

        segment_set = set(segment)
        if segment_set == line_set:
            return {
                "plane": plane_name,
                "perpendicular_line": "true",
            }

        for outside, foot in (segment, (segment[1], segment[0])):
            if outside not in line_set:
                continue
            plane_point = line[1] if line[0] == outside else line[0]
            if not _point_is_on_plane_fact(scene_dict, plane_point, plane_ref):
                continue
            if not _point_is_on_plane_fact(scene_dict, foot, plane_ref):
                continue
            if foot == plane_point:
                return {
                    "plane": plane_name,
                    "perpendicular_line": "true",
                }
            return {
                "plane": plane_name,
                "outside": outside,
                "foot": foot,
                "plane_point": plane_point,
                "projected_line": f"{foot}{plane_point}",
                "angle_name": f"{outside}{plane_point}{foot}",
            }
    return None


def _perpendicular_segment_plane(relation: dict[str, Any]) -> tuple[tuple[str, str] | None, list[str] | None]:
    object_1 = str(relation.get("object_1") or "")
    object_2 = str(relation.get("object_2") or "")
    segment = _parse_edge_token(object_1)
    plane_ref = _parse_plane_token(object_2)
    if segment is not None and plane_ref is not None:
        return segment, plane_ref
    segment = _parse_edge_token(object_2)
    plane_ref = _parse_plane_token(object_1)
    return segment, plane_ref


def _point_is_on_plane_fact(scene_dict: dict, point: str, plane_ref: list[str]) -> bool:
    if point in set(plane_ref):
        return True
    for rel in scene_dict.get("relations", []):
        if not isinstance(rel, dict) or str(rel.get("type") or "").strip().lower() != "on_plane":
            continue
        metadata = rel.get("metadata") if isinstance(rel.get("metadata"), dict) else {}
        if not _metadata_is_usable_fact(metadata, default=True):
            continue
        if str(rel.get("object_1") or "") != point:
            continue
        rel_plane = _parse_plane_token(str(rel.get("object_2") or ""))
        if rel_plane is not None and set(rel_plane) == set(plane_ref):
            return True
    return False


def _plane_plane_angle_fact(scene_dict: dict, question: str) -> dict[str, str] | None:
    plane_refs = _parse_plane_refs(question)
    if len(plane_refs) < 2:
        return None
    first_plane, second_plane = plane_refs[:2]
    first_set = set(first_plane)
    second_set = set(second_plane)
    common = [point for point in first_plane if point in second_set]
    if len(common) < 2:
        return None
    intersection = (common[0], common[1])
    intersection_label = f"{intersection[0]}{intersection[1]}"

    for vertex in intersection:
        first_line = _perpendicular_line_to_edge_in_plane(scene_dict, intersection, first_set, vertex)
        second_line = _perpendicular_line_to_edge_in_plane(scene_dict, intersection, second_set, vertex)
        if first_line is None or second_line is None:
            continue
        first_other = first_line[1] if first_line[0] == vertex else first_line[0]
        second_other = second_line[1] if second_line[0] == vertex else second_line[0]
        if first_other == second_other:
            continue
        return {
            "first_plane": "".join(first_plane),
            "second_plane": "".join(second_plane),
            "intersection": intersection_label,
            "vertex": vertex,
            "first_line": f"{first_line[0]}{first_line[1]}",
            "second_line": f"{second_line[0]}{second_line[1]}",
            "angle_name": f"{first_other}{vertex}{second_other}",
        }
    return None


def _pyramid_volume_fact(scene_dict: dict, highlight: list[str]) -> dict[str, str] | None:
    if len(highlight) < 4:
        return None
    apex = highlight[0]
    base = highlight[1:]
    base_set = set(base)
    base_label = "".join(base)
    for rel in scene_dict.get("relations", []):
        if not isinstance(rel, dict) or str(rel.get("type") or "").strip().lower() != "perpendicular":
            continue
        metadata = rel.get("metadata") if isinstance(rel.get("metadata"), dict) else {}
        if not _metadata_is_usable_fact(metadata, default=True):
            continue
        segment, plane_ref = _perpendicular_segment_plane(rel)
        if segment is None or plane_ref is None:
            continue
        if set(plane_ref) != base_set or apex not in segment:
            continue
        foot = segment[1] if segment[0] == apex else segment[0]
        if foot not in base_set:
            continue
        height_segment = f"{apex}{foot}"
        return {
            "apex": apex,
            "base": base_label,
            "foot": foot,
            "height_segment": height_segment,
            "height_label": _length_label_for_segment(scene_dict, apex, foot) or "",
        }
    return None


def _perpendicular_line_to_edge_in_plane(
    scene_dict: dict,
    edge: tuple[str, str],
    plane_set: set[str],
    vertex: str,
) -> tuple[str, str] | None:
    edge_set = set(edge)
    for rel in scene_dict.get("relations", []):
        if not isinstance(rel, dict) or str(rel.get("type") or "").strip().lower() != "perpendicular":
            continue
        metadata = rel.get("metadata") if isinstance(rel.get("metadata"), dict) else {}
        if not _metadata_is_usable_fact(metadata, default=True):
            continue
        first = _parse_edge_token(str(rel.get("object_1") or ""))
        second = _parse_edge_token(str(rel.get("object_2") or ""))
        if first is None or second is None:
            continue
        candidate = second if set(first) == edge_set else first if set(second) == edge_set else None
        if candidate is None:
            continue
        if set(candidate) == edge_set or vertex not in candidate:
            continue
        if not set(candidate).issubset(plane_set):
            continue
        return candidate
    return None


def _length_label_for_segment(scene_dict: dict, first: str, second: str) -> str | None:
    target_set = {first, second}
    for ann in scene_dict.get("annotations", []):
        if not isinstance(ann, dict) or ann.get("type") != "length":
            continue
        metadata = ann.get("metadata") if isinstance(ann.get("metadata"), dict) else {}
        if not _metadata_is_usable_fact(metadata, default=True):
            continue
        target = str(ann.get("target") or "")
        edge = _parse_edge_token(target)
        label = ann.get("label")
        if edge and set(edge) == target_set and isinstance(label, str) and label.strip():
            return label.strip()
    return None


def _relevant_scene_facts(scene_dict: dict, highlight: list[str]) -> list[str]:
    names = set(highlight)
    facts: list[str] = []
    for ann in scene_dict.get("annotations", []):
        if not isinstance(ann, dict):
            continue
        fact = _annotation_fact(ann, names)
        if fact:
            facts.append(fact)
    for rel in scene_dict.get("relations", []):
        if not isinstance(rel, dict):
            continue
        fact = _relation_fact(rel, names)
        if fact:
            facts.append(fact)
    return list(dict.fromkeys(facts))


def _solver_used_facts(scene_dict: dict, highlight: list[str], result: SolverResult) -> list[dict[str, str]]:
    names = set(highlight)
    facts: list[dict[str, str]] = []

    for ann in scene_dict.get("annotations", []):
        if not isinstance(ann, dict):
            continue
        text = _annotation_fact(ann, names)
        if text:
            metadata = ann.get("metadata") if isinstance(ann.get("metadata"), dict) else {}
            facts.append({"source": _fact_source_from_metadata(metadata, "given"), "text": _append_evidence(text, metadata)})

    for rel in scene_dict.get("relations", []):
        if not isinstance(rel, dict):
            continue
        text = _relation_fact(rel, names)
        if text:
            metadata = rel.get("metadata") if isinstance(rel.get("metadata"), dict) else {}
            facts.append({"source": _fact_source_from_metadata(metadata, "verified"), "text": _append_evidence(text, metadata)})

    for param in scene_dict.get("parameters", []):
        if not isinstance(param, dict):
            continue
        name = str(param.get("name") or "").strip()
        if not name:
            continue
        value = param.get("default")
        label = str(param.get("label") or name)
        facts.append({"source": "parameter_default", "text": f"{label} đang dùng giá trị mặc định {value}."})

    for issue in scene_dict.get("cas_issues", []):
        if not isinstance(issue, dict):
            continue
        description = str(issue.get("description") or "").strip()
        if not description:
            continue
        source = "verified" if bool(issue.get("auto_fixed")) else "construction_only"
        prefix = "CAS đã tự sửa" if source == "verified" else "CAS chưa tự sửa"
        facts.append({"source": source, "text": f"{prefix}: {description}"})

    if not facts and result.answer not in {"Không đủ dữ kiện", "Không xác định"}:
        if scene_dict.get("topic") in {"coordinate_2d", "coordinate_3d"}:
            facts.append({"source": "given", "text": "Bài toán tọa độ: dùng tọa độ điểm có trong scene."})
        else:
            facts.append({"source": "construction_only", "text": "Chưa có dữ kiện đề/quan hệ định lượng rõ trong scene; kết quả dựa trên tọa độ scene hiện tại."})

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for fact in facts:
        key = (fact["source"], fact["text"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(fact)
    return deduped[:10]


def _fact_source_from_metadata(metadata: dict[str, Any], fallback: str) -> str:
    source = metadata.get("source")
    confidence = metadata.get("confidence")
    if source == "construction" or confidence == "unverified":
        return "construction_only"
    if source == "given":
        return "given"
    if source == "inferred":
        return "verified" if confidence == "verified" else "inferred"
    if confidence == "verified":
        return "verified"
    return fallback


def _append_evidence(text: str, metadata: dict[str, Any]) -> str:
    evidence = metadata.get("evidence")
    if isinstance(evidence, str) and evidence.strip():
        return f"{text} Căn cứ: {evidence.strip()}."
    return text


def _annotation_fact(annotation: dict[str, Any], names: set[str]) -> str | None:
    atype = str(annotation.get("type") or "")
    target = str(annotation.get("target") or "")
    label = annotation.get("label")
    target_points = set(_split_point_sequence(target.replace("-", "")))
    metadata = annotation.get("metadata") if isinstance(annotation.get("metadata"), dict) else {}
    if atype == "length" and target_points.intersection(names) and isinstance(label, str) and label.strip():
        return f"Đề cho độ dài {target.replace('-', '')} = {label.strip()}."
    if atype == "angle" and target in names and isinstance(label, str) and label.strip():
        arms = metadata.get("arms")
        if isinstance(arms, list) and len(arms) >= 2:
            return f"Đề cho góc {arms[0]}{target}{arms[1]} = {label.strip()}."
    if atype == "right_angle" and target in names:
        arms = metadata.get("arms")
        if isinstance(arms, list) and len(arms) >= 2:
            return f"Có {arms[0]}{target} vuông góc {target}{arms[1]}."
    return None


def _relation_fact(relation: dict[str, Any], names: set[str]) -> str | None:
    rtype = str(relation.get("type") or "").strip().lower()
    object_1 = str(relation.get("object_1") or "")
    object_2 = str(relation.get("object_2") or "")
    points = set(_split_point_sequence(f"{object_1}{object_2}".replace("plane", "")))
    if points and not points.intersection(names):
        return None
    if rtype == "perpendicular" and object_2:
        return f"Có {object_1} vuông góc {object_2}."
    if rtype == "parallel" and object_2:
        return f"Có {object_1} song song {object_2}."
    if rtype == "equal_length" and object_2:
        return f"Có {object_1} = {object_2}."
    if rtype == "midpoint" and object_2:
        return f"{object_1} là trung điểm của {object_2.replace('-', '')}."
    if rtype == "on_line" and object_2:
        return f"{object_1} nằm trên đường thẳng {object_2.replace('-', '')}."
    if rtype == "on_plane" and object_2:
        return f"{object_1} nằm trên mặt phẳng {object_2}."
    return None


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
    for raw in re.findall(r"\(([A-Z0-9'\s]{3,})\)", question):
        refs.append(_split_point_sequence(raw))
    for raw in re.findall(r"(?:mp|mat\s+phang|mặt(?:\s+phẳng)?)\s+([A-Z0-9'\s]{3,})", question, flags=re.IGNORECASE):
        refs.append(_split_point_sequence(raw))
    return [ref for ref in refs if len(ref) >= 3]


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
    match = re.search(rf"\b{name}\s*\(", question, flags=re.IGNORECASE)
    if not match:
        return None
    open_index = match.end() - 1
    close_index = _find_matching_paren(question, open_index)
    if close_index is None:
        return None
    return question[open_index + 1:close_index].strip()


def _find_matching_paren(value: str, open_index: int) -> int | None:
    depth = 0
    for index in range(open_index, len(value)):
        if value[index] == "(":
            depth += 1
        elif value[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _split_two_operands(value: str) -> tuple[str, str]:
    depth = 0
    for index, char in enumerate(value):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            return value[:index].strip(), value[index + 1:].strip()
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
    cleaned = re.sub(r"^(?:mp|mat\s+phang|mặt(?:\s+phẳng)?)\s+", "", cleaned, flags=re.IGNORECASE).strip()
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
