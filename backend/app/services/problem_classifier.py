from __future__ import annotations

import re
from typing import Any

from app.schemas.advisory import ProblemClassification
from app.schemas.scene import MathScene


_SOLID_KEYWORDS = (
    "hình chóp",
    "hinh chop",
    "lăng trụ",
    "lang tru",
    "tứ diện",
    "tu dien",
    "khối chóp",
    "khoi chop",
    "khối lăng trụ",
    "khoi lang tru",
    "mặt phẳng",
    "mat phang",
    "oxyz",
)
_FUNCTION_KEYWORDS = ("hàm số", "ham so", "đồ thị", "do thi", "y =", "y=")
_CONIC_KEYWORDS = ("đường tròn", "duong tron", "parabol", "elip", "ellipse", "hyperbol")
_VECTOR_KEYWORDS = ("vectơ", "vector", "véc tơ", "vec to", "tích vô hướng", "tich vo huong", "tích có hướng", "tich co huong")
_COORDINATE_2D_KEYWORDS = ("oxy", "tọa độ phẳng", "toa do phang")
_DISTANCE_RE = re.compile(r"kho[aả]ng\s*c[áa]ch|distance|\bd\s*\(", re.IGNORECASE)
_ANGLE_RE = re.compile(r"g[oó]c|angle|cos\s*\(|sin\s*\(", re.IGNORECASE)
_AREA_RE = re.compile(r"di[eệ]n\s*t[íi]ch|area|\bS\s*\(", re.IGNORECASE)
_PERIMETER_RE = re.compile(r"chu\s*vi|perimeter|\bP\s*\(", re.IGNORECASE)
_QUADRILATERAL_METRIC_RE = re.compile(r"h[iì]nh\s*(?:ch[uữ]\s*nh[aậ]t|vu[oô]ng|b[iì]nh\s*h[aà]nh|thang)|rectangle|square|parallelogram|trapezoid", re.IGNORECASE)
_CIRCLE_METRIC_RE = re.compile(r"h[iì]nh\s*tr[oò]n|đường\s*tr[oò]n|duong\s*tron|circle", re.IGNORECASE)
_TRIANGLE_CONGRUENCE_RE = re.compile(r"b[aằ]ng\s*nhau|congruent|≅|≡", re.IGNORECASE)
_TRIANGLE_SIMILARITY_RE = re.compile(r"đ[oồ]ng\s*d[aạ]ng|similar|[∼~]", re.IGNORECASE)
_PYTHAGORAS_RE = re.compile(
    r"pythagor|pi-ta-go|(?:t[ií]nh|t[iì]m|calculate|find)(?:\s+đ[ộo]\s+d[aà]i)?\s+c[aạ]nh\s+[A-Z](?:[0-9]+|')?\s*-?\s*[A-Z](?:[0-9]+|')?",
    re.IGNORECASE,
)
_VOLUME_RE = re.compile(r"th[eể]\s*t[íi]ch|volume|\bV\s*\(", re.IGNORECASE)
_EQUATION_RE = re.compile(r"phương\s*trình|\bpt\b|equation", re.IGNORECASE)
_PROJECTION_RE = re.compile(r"hình\s*chiếu|projection|project", re.IGNORECASE)
_REFLECTION_RE = re.compile(r"đối\s*xứng|reflection|reflect", re.IGNORECASE)
_PARALLEL_RE = re.compile(r"song\s*song|parallel", re.IGNORECASE)
_PERP_RE = re.compile(r"vu[oô]ng\s*g[oó]c|perpendicular", re.IGNORECASE)
_COLLINEAR_RE = re.compile(r"thẳng\s*hàng|collinear", re.IGNORECASE)
_COPLANAR_RE = re.compile(r"đồng\s*phẳng|coplanar", re.IGNORECASE)
_VECTOR_RE = re.compile(r"vector|vect[ơo]|v[ée]c\s*t[ơo]|tích\s*vô\s*hướng|tích\s*có\s*hướng|dot\s*\(|cross\s*\(|×|·", re.IGNORECASE)

_KIND_MAP = {
    "distance_point_plane": ("distance", "point_plane"),
    "distance_point_line": ("distance", "point_line"),
    "distance_point_point": ("distance", "point_point"),
    "distance_line_line": ("distance", "line_line"),
    "angle_line_plane": ("angle", "line_plane"),
    "angle_line_line": ("angle", "line_line"),
    "angle_plane_plane": ("angle", "plane_plane"),
    "area_polygon": ("area", "polygon"),
    "perimeter_polygon": ("perimeter", "polygon"),
    "pythagoras_length": ("pythagoras", "right_triangle_length"),
    "triangle_congruence_sss": ("triangle_congruence", "sss"),
    "triangle_similarity_aa": ("triangle_similarity", "aa"),
    "quadrilateral_metric": ("quadrilateral_metric", "direct_formula"),
    "circle_metric": ("circle_metric", "direct_formula"),
    "volume_pyramid": ("volume", "pyramid"),
    "volume_tetrahedron": ("volume", "tetrahedron"),
    "volume_prism": ("volume", "prism"),
    "equation_line": ("equation", "line"),
    "equation_plane": ("equation", "plane"),
    "proof_collinear": ("proof", "collinear"),
    "proof_coplanar": ("proof", "coplanar"),
    "projection_point_line": ("projection", "point_line"),
    "projection_point_plane": ("projection", "point_plane"),
    "reflection_point_line": ("reflection", "point_line"),
    "reflection_point_plane": ("reflection", "point_plane"),
    "vector": ("vector", None),
    "vector_dot": ("vector_operation", "dot"),
    "vector_cross": ("vector_operation", "cross"),
}


def classify_render_problem(problem_text: str, grade: int | None = None, scene: MathScene | None = None) -> ProblemClassification:
    text = _normalize(problem_text)
    signals: list[str] = []
    topic = "unknown"
    confidence = 0.25
    source = "rules"

    if scene is not None:
        if scene.topic != "unknown":
            topic = scene.topic
            confidence = 0.82
            source = "existing_metadata"
            signals.append(f"scene.topic={scene.topic}")
        if scene.renderer:
            signals.append(f"renderer={scene.renderer}")
        if scene.view.dimension:
            signals.append(f"dimension={scene.view.dimension}")

    keyword_topic, keyword_signal = _topic_from_text(text)
    if keyword_topic != "unknown":
        signals.append(keyword_signal)
        if topic == "unknown":
            topic = keyword_topic
            confidence = 0.72
        elif topic == keyword_topic:
            confidence = min(0.95, confidence + 0.1)
        else:
            source = "hybrid_rules"
            confidence = max(confidence, 0.65)

    if grade is not None:
        signals.append(f"grade={grade}")

    domain = _domain_from_topic(topic)
    return ProblemClassification(
        domain=domain,
        topic=topic,
        task_type="render_scene",
        sub_type=_render_sub_type(topic, text),
        confidence=confidence,
        source=source,
        signals=_dedupe(signals),
        supported_by_current_solver=None,
    )


def classify_solve_question(
    question: str,
    scene_dict: dict[str, Any] | None = None,
    solver_result: Any | None = None,
) -> ProblemClassification:
    signals: list[str] = []
    scene_topic = str((scene_dict or {}).get("topic") or "unknown")
    topic = scene_topic if scene_topic != "unknown" else "coordinate_3d"
    if scene_topic != "unknown":
        signals.append(f"scene.topic={scene_topic}")

    task_type: str | None = None
    sub_type: str | None = None
    confidence = 0.25
    source = "rules"

    step_kind = _first_semantic_step_kind(solver_result)
    if step_kind:
        mapped = _map_step_kind(step_kind)
        if mapped is not None:
            task_type, sub_type = mapped
            confidence = 0.92
            source = "existing_metadata"
            signals.append(f"step.kind={step_kind}")

    if task_type is None:
        task_type, sub_type, signal = _solve_task_from_question(question)
        if task_type is not None:
            confidence = 0.8
            signals.append(signal)

    answer = str(getattr(solver_result, "answer", "") or "") if solver_result is not None else ""
    warnings = list(getattr(solver_result, "warnings", []) or []) if solver_result is not None else []
    supported = None
    if solver_result is not None:
        supported = bool(task_type and answer not in {"Không xác định", "Không đủ dữ kiện"} and getattr(solver_result, "steps", []))
        if answer in {"Không xác định", "Không đủ dữ kiện"}:
            signals.append(f"solver.answer={answer}")
            confidence = min(confidence, 0.6) if task_type else 0.25
        if warnings:
            signals.append(f"solver.warnings={len(warnings)}")

    if task_type is None:
        task_type = "unknown"
        supported = False if solver_result is not None else None

    return ProblemClassification(
        domain="geometry",
        topic=topic,
        task_type=task_type,
        sub_type=sub_type,
        confidence=confidence,
        source=source,
        signals=_dedupe(signals),
        supported_by_current_solver=supported,
    )


def _topic_from_text(text: str) -> tuple[str, str]:
    if _contains_any(text, _FUNCTION_KEYWORDS):
        return "function_graph", "keyword=function_graph"
    if _contains_any(text, _VECTOR_KEYWORDS):
        return "vector_2d", "keyword=vector"
    if _contains_any(text, _CONIC_KEYWORDS):
        return "conic", "keyword=conic"
    if _contains_any(text, _COORDINATE_2D_KEYWORDS):
        return "coordinate_2d", "keyword=coordinate_2d"
    if _contains_any(text, _SOLID_KEYWORDS):
        return "solid_geometry", "keyword=solid_geometry"
    return "unknown", "keyword=unknown"


def _domain_from_topic(topic: str) -> str:
    if topic == "function_graph":
        return "function"
    if topic in {"coordinate_2d", "conic", "vector_2d", "solid_geometry", "coordinate_3d"}:
        return "geometry"
    return "unknown"


def _render_sub_type(topic: str, text: str) -> str | None:
    if topic == "solid_geometry":
        if "lăng trụ" in text or "lang tru" in text:
            return "prism_or_solid"
        if "tứ diện" in text or "tu dien" in text:
            return "tetrahedron_or_solid"
        return "pyramid_or_solid"
    if topic == "function_graph":
        return "function_plot"
    if topic == "conic":
        return "conic_2d"
    if topic in {"coordinate_2d", "coordinate_3d"}:
        return "coordinate_geometry"
    if topic == "vector_2d":
        return "vector_geometry"
    return None


def _first_semantic_step_kind(solver_result: Any | None) -> str | None:
    if solver_result is None:
        return None
    for step in getattr(solver_result, "steps", []) or []:
        kind = getattr(step, "kind", None)
        if isinstance(kind, str) and kind and kind not in {"input", "result", "fact"}:
            return kind
    return None


def _map_step_kind(kind: str) -> tuple[str, str | None] | None:
    if kind in _KIND_MAP:
        return _KIND_MAP[kind]
    if kind.startswith("distance_"):
        return "distance", kind.removeprefix("distance_")
    if kind.startswith("angle_"):
        return "angle", kind.removeprefix("angle_")
    if kind.startswith("volume_"):
        return "volume", kind.removeprefix("volume_")
    if kind.startswith("perimeter_"):
        return "perimeter", kind.removeprefix("perimeter_")
    if kind.startswith("equation_"):
        return "equation", kind.removeprefix("equation_")
    if kind.startswith("proof_"):
        return "proof", kind.removeprefix("proof_")
    return None


def _solve_task_from_question(question: str) -> tuple[str | None, str | None, str]:
    triangle_count = len(re.findall(r"(?:tam\s*gi[aá]c|triangle|[△∆])\s*[A-Z]{3}", question, re.IGNORECASE))
    if triangle_count == 2 and _TRIANGLE_CONGRUENCE_RE.search(question):
        return "triangle_congruence", "sss", "question_regex=triangle_congruence"
    if triangle_count == 2 and _TRIANGLE_SIMILARITY_RE.search(question):
        return "triangle_similarity", "aa", "question_regex=triangle_similarity"
    if _CIRCLE_METRIC_RE.search(question) and (_AREA_RE.search(question) or _PERIMETER_RE.search(question)):
        return "circle_metric", "direct_formula", "question_regex=circle_metric"
    if _QUADRILATERAL_METRIC_RE.search(question) and (_AREA_RE.search(question) or _PERIMETER_RE.search(question)):
        return "quadrilateral_metric", "direct_formula", "question_regex=quadrilateral_metric"
    if _DISTANCE_RE.search(question):
        return "distance", _distance_sub_type(question), "question_regex=distance"
    if _PROJECTION_RE.search(question):
        return "projection", _target_sub_type(question), "question_regex=projection"
    if _REFLECTION_RE.search(question):
        return "reflection", _target_sub_type(question), "question_regex=reflection"
    if _EQUATION_RE.search(question):
        return "equation", _target_sub_type(question), "question_regex=equation"
    if _COLLINEAR_RE.search(question):
        return "proof", "collinear", "question_regex=collinear"
    if _COPLANAR_RE.search(question):
        return "proof", "coplanar", "question_regex=coplanar"
    if _PARALLEL_RE.search(question):
        return "relation", "parallel", "question_regex=parallel"
    if _PERP_RE.search(question):
        return "relation", "perpendicular", "question_regex=perpendicular"
    if _ANGLE_RE.search(question):
        return "angle", _angle_sub_type(question), "question_regex=angle"
    if _AREA_RE.search(question):
        return "area", "polygon", "question_regex=area"
    if _PERIMETER_RE.search(question):
        return "perimeter", "polygon", "question_regex=perimeter"
    if _PYTHAGORAS_RE.search(question):
        return "pythagoras", "right_triangle_length", "question_regex=pythagoras"
    if _VOLUME_RE.search(question):
        return "volume", "solid", "question_regex=volume"
    if _VECTOR_RE.search(question):
        return "vector", None, "question_regex=vector"
    return None, None, "question_regex=unknown"


def _distance_sub_type(question: str) -> str | None:
    if re.search(r"d\s*\([^,]+,\s*\([^)]+\)\s*\)", question, flags=re.IGNORECASE):
        return "point_plane"
    if re.search(r"d\s*\([^,]{2,},\s*[^,]{2,}\s*\)", question, flags=re.IGNORECASE):
        return "line_line"
    return None


def _angle_sub_type(question: str) -> str | None:
    plane_count = len(re.findall(r"\([A-Z0-9'\s]{3,}\)", question))
    if plane_count >= 2:
        return "plane_plane"
    if plane_count == 1:
        return "line_plane"
    return "line_line"


def _target_sub_type(question: str) -> str | None:
    if re.search(r"\([A-Z0-9'\s]{3,}\)", question):
        return "plane"
    if re.search(r"[A-Z][A-Z0-9']", question):
        return "line"
    return None


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
