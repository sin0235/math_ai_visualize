import re
from itertools import combinations
from math import acos, asin, degrees, isfinite, sqrt
from typing import Any

import sympy as sp
from scipy.spatial import cKDTree

from app.schemas.scene import AdvancedRenderSettings, Face, Line3D, MathScene, Plane, Point3D, Segment, Sphere, Vector3D
from app.services.linalg import Vec3, add as _add, bbox_diagonal, centroid as linalg_centroid, cross as _cross, distance as _distance, dot as _dot, norm as _norm, normalize as _normalize, plane_from_points, raw_plane_from_named_points, scale as _scale, sub as _sub, to_tuple, vec3

EPS = 1e-9
DISPLAY_EPS = 1e-6
MAX_COMPUTED_PAIRS = 100
_SAFE_SYMPY_LOCALS = {
    "sqrt": sp.sqrt,
    "pi": sp.pi,
    "E": sp.E,
    "e": sp.E,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "abs": sp.Abs,
}

def normalize_scene(scene: MathScene, settings: AdvancedRenderSettings | None = None) -> MathScene:
    settings = settings or AdvancedRenderSettings()
    if scene.renderer != "threejs_3d":
        return scene

    data = scene.model_dump()
    scene = _normalize_origin_marker(scene, settings)
    data = scene.model_dump()

    if settings.auto_segments_from_faces:
        point_names = {obj.name for obj in scene.objects if isinstance(obj, Point3D)}
        existing_edges = {
            _edge_key(obj.points[0], obj.points[1])
            for obj in scene.objects
            if isinstance(obj, Segment)
        }
        new_segments: list[dict[str, Any]] = []

        for face in [obj for obj in scene.objects if isinstance(obj, Face)]:
            for start, end in _face_edges(face.points):
                if start not in point_names or end not in point_names:
                    continue
                key = _edge_key(start, end)
                if key in existing_edges:
                    continue
                existing_edges.add(key)
                new_segments.append({
                    "type": "segment",
                    "points": [start, end],
                    "hidden": _looks_hidden_edge(start, end, scene),
                })

        if new_segments:
            data["objects"] = [*data["objects"], *new_segments]

    data = _normalize_segment_intersection_points(MathScene.model_validate(data), data)
    data = _normalize_special_property_annotations(MathScene.model_validate(data), data)

    if scene.view.show_coordinates:
        existing_coord_targets = {
            ann.target for ann in scene.annotations if ann.type == "coordinate_label"
        }
        for obj in scene.objects:
            if isinstance(obj, Point3D) and obj.name not in existing_coord_targets:
                data["annotations"].append({
                    "type": "coordinate_label",
                    "target": obj.name,
                    "metadata": {},
                })

    return MathScene.model_validate(data)


def _normalize_segment_intersection_points(scene: MathScene, data: dict[str, Any]) -> dict[str, Any]:
    points = _point_map(scene)
    segments = [obj for obj in scene.objects if isinstance(obj, Segment)]
    if len(segments) < 2:
        return data

    existing_points = {_point_key(_point_tuple(point)): point.name for point in points.values()}
    point_names = set(points)
    objects = data.setdefault("objects", [])
    relations = data.setdefault("relations", [])
    added = 0

    for first, second in _segment_candidate_pairs(segments, points):
        if set(first.points).intersection(second.points):
            continue
        intersection = _segment_segment_intersection(first, second, points)
        if intersection is None:
            continue
        if any(_distance(intersection, existing) <= DISPLAY_EPS for existing in existing_points):
            continue
        name = _next_intersection_name(point_names, added)
        point_names.add(name)
        existing_points[_point_key(intersection)] = name
        added += 1
        objects.append({
            "type": "point_3d",
            "name": name,
            "x": intersection[0],
            "y": intersection[1],
            "z": intersection[2],
        })
        relations.append({
            "type": "intersection",
            "object_1": name,
            "object_2": f"{first.points[0]}-{first.points[1]}:{second.points[0]}-{second.points[1]}",
            "metadata": {"objects": [list(first.points), list(second.points)]},
        })

    return data


def _segment_candidate_pairs(segments: list[Segment], points: dict[str, Point3D]) -> list[tuple[Segment, Segment]]:
    midpoint_data: list[tuple[Segment, Vec3, float]] = []
    for segment in segments:
        start = points.get(segment.points[0])
        end = points.get(segment.points[1])
        if start is None or end is None:
            continue
        start_point = _point_tuple(start)
        end_point = _point_tuple(end)
        midpoint = _scale(_add(start_point, end_point), 0.5)
        half_length = _distance(start_point, end_point) / 2
        midpoint_data.append((segment, midpoint, half_length))
    if len(midpoint_data) < 2:
        return []
    max_radius = max(item[2] for item in midpoint_data)
    coords = [item[1] for item in midpoint_data]
    tree = cKDTree(coords)
    raw_pairs = tree.query_pairs(2 * max_radius + DISPLAY_EPS)
    candidates: list[tuple[Segment, Segment]] = []
    for first_index, second_index in sorted(raw_pairs):
        first, first_midpoint, first_half = midpoint_data[first_index]
        second, second_midpoint, second_half = midpoint_data[second_index]
        if _distance(first_midpoint, second_midpoint) > first_half + second_half + DISPLAY_EPS:
            continue
        candidates.append((first, second))
    return candidates



def _normalize_special_property_annotations(scene: MathScene, data: dict[str, Any]) -> dict[str, Any]:
    points = _point_map(scene)
    annotations = data.setdefault("annotations", [])
    next_equal_group = _next_equal_mark_group(annotations)

    for relation in scene.relations:
        relation_type = relation.type.lower().strip()
        if relation_type == "midpoint":
            midpoint_name = relation.object_1
            edge = _relation_edge(relation.object_2, relation.metadata)
            if edge is None or midpoint_name not in points:
                continue
            start, end = edge
            midpoint_point = points[midpoint_name]
            start_point = points.get(start)
            end_point = points.get(end)
            if start_point is None or end_point is None:
                continue
            expected = _scale(_add(_point_tuple(start_point), _point_tuple(end_point)), 0.5)
            if _distance(_point_tuple(midpoint_point), expected) > DISPLAY_EPS:
                continue
            group = next_equal_group
            added = False
            for target in (_target_key(start, midpoint_name), _target_key(midpoint_name, end)):
                if not _has_annotation(annotations, "equal_marks", target):
                    annotations.append({"type": "equal_marks", "target": target, "metadata": {"group": group}})
                    added = True
            if added:
                next_equal_group += 1
        elif relation_type == "equal_length":
            first = _parse_edge_ref(relation.object_1)
            second = _parse_edge_ref(relation.object_2)
            if first is None or second is None:
                continue
            group = next_equal_group
            added = False
            for start, end in (first, second):
                target = _target_key(start, end)
                if not _has_annotation(annotations, "equal_marks", target):
                    annotations.append({"type": "equal_marks", "target": target, "metadata": {"group": group}})
                    added = True
            if added:
                next_equal_group += 1
        elif relation_type == "perpendicular":
            first = _parse_edge_ref(relation.object_1)
            second = _parse_edge_ref(relation.object_2)
            if first is None or second is None:
                continue
            right_angle = _right_angle_from_edges(first, second)
            if right_angle is None:
                continue
            vertex, arms = right_angle
            if not _has_right_angle(annotations, vertex, arms):
                annotations.append({"type": "right_angle", "target": vertex, "metadata": {"arms": list(arms)}})

    return data


def _relation_edge(object_2: str | None, metadata: dict[str, Any]) -> tuple[str, str] | None:
    edge = _parse_edge_ref(object_2)
    if edge is not None:
        return edge
    for key in ("segment", "edge"):
        value = metadata.get(key)
        if isinstance(value, str):
            edge = _parse_edge_ref(value)
            if edge is not None:
                return edge
    points = metadata.get("points") or metadata.get("endpoints")
    if isinstance(points, list) and len(points) >= 2 and all(isinstance(item, str) for item in points[:2]):
        return points[0], points[1]
    return None


def _parse_edge_ref(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    cleaned = value.strip()
    cleaned = re.sub(r"^(segment|line)\((.*)\)$", r"\2", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(" ", "")
    if "-" in cleaned:
        parts = [part for part in cleaned.split("-") if part]
        if len(parts) == 2:
            return parts[0], parts[1]
    if len(cleaned) == 2 and cleaned.isalpha():
        return cleaned[0], cleaned[1]
    return None


def _target_key(start: str, end: str) -> str:
    return f"{start}-{end}"


def _has_annotation(annotations: list[dict[str, Any]], annotation_type: str, target: str) -> bool:
    reverse = "-".join(reversed(target.split("-"))) if "-" in target else target
    return any(
        annotation.get("type") == annotation_type and annotation.get("target") in {target, reverse}
        for annotation in annotations
    )


def _has_right_angle(annotations: list[dict[str, Any]], vertex: str, arms: tuple[str, str]) -> bool:
    arm_set = set(arms)
    for annotation in annotations:
        if annotation.get("type") != "right_angle" or annotation.get("target") != vertex:
            continue
        metadata = annotation.get("metadata") or {}
        existing_arms = metadata.get("arms")
        if isinstance(existing_arms, list) and set(existing_arms) == arm_set:
            return True
    return False


def _right_angle_from_edges(first: tuple[str, str], second: tuple[str, str]) -> tuple[str, tuple[str, str]] | None:
    shared = set(first).intersection(second)
    if len(shared) != 1:
        return None
    vertex = next(iter(shared))
    arm_1 = first[1] if first[0] == vertex else first[0]
    arm_2 = second[1] if second[0] == vertex else second[0]
    return vertex, (arm_1, arm_2)


def _next_equal_mark_group(annotations: list[dict[str, Any]]) -> int:
    groups = [
        annotation.get("metadata", {}).get("group")
        for annotation in annotations
        if annotation.get("type") == "equal_marks"
    ]
    numeric_groups = [group for group in groups if isinstance(group, int)]
    return max(numeric_groups, default=0) + 1


def _normalize_origin_marker(scene: MathScene, settings: AdvancedRenderSettings) -> MathScene:
    if settings.coordinate_assignment == "ai":
        return scene
    points = [obj for obj in scene.objects if isinstance(obj, Point3D)]
    if not points:
        return scene

    candidate = _origin_candidate(scene, settings, points)
    if candidate is None:
        if any(_is_origin(point) for point in points):
            return scene
        data = scene.model_dump()
        data["objects"] = [
            {"type": "point_3d", "name": "O", "x": 0, "y": 0, "z": 0, "x_expr": "0", "y_expr": "0", "z_expr": "0"},
            *data["objects"],
        ]
        data["annotations"].append({"type": "coordinate_label", "target": "O", "metadata": {}})
        return MathScene.model_validate(data)

    origin_expr = _point_expr(candidate)
    if all(sp.simplify(value) == 0 for value in origin_expr):
        return scene

    data = scene.model_dump()
    for obj in data.get("objects", []):
        if obj.get("type") != "point_3d":
            continue
        exprs = _point_dict_expr(obj)
        shifted = tuple(sp.simplify(value - offset) for value, offset in zip(exprs, origin_expr, strict=True))
        obj["x"], obj["y"], obj["z"] = (_expr_float(value) for value in shifted)
        obj["x_expr"], obj["y_expr"], obj["z_expr"] = (_expr_text(value) for value in shifted)
    return MathScene.model_validate(data)


def _origin_candidate(scene: MathScene, settings: AdvancedRenderSettings, points: list[Point3D]) -> Point3D | None:
    if settings.coordinate_assignment == "prefer_o_origin":
        point_o = next((point for point in points if point.name == "O"), None)
        if point_o is not None:
            return point_o
    return max(points, key=lambda point: _origin_score(point, scene), default=None)


def _origin_score(point: Point3D, scene: MathScene) -> tuple[int, int, int, int]:
    if _is_origin(point):
        origin_bonus = 1_000
    else:
        origin_bonus = 0
    name_bonus = 200 if point.name == "O" else 0
    simplicity = -sum(_expr_complexity(value) for value in _point_expr(point))
    incidence = sum(_object_mentions_point(obj, point.name) for obj in scene.objects) + sum(_relation_mentions_point(rel, point.name) for rel in scene.relations)
    return (origin_bonus + name_bonus, simplicity, incidence, -len(point.name))


def _object_mentions_point(obj: Any, name: str) -> int:
    data = obj.model_dump() if hasattr(obj, "model_dump") else {}
    return str(data).count(name)


def _relation_mentions_point(rel: Any, name: str) -> int:
    data = rel.model_dump() if hasattr(rel, "model_dump") else {}
    return str(data).count(name)


def _point_expr(point: Point3D) -> tuple[sp.Expr, sp.Expr, sp.Expr]:
    return (
        _parse_expr(point.x_expr, point.x),
        _parse_expr(point.y_expr, point.y),
        _parse_expr(point.z_expr, point.z),
    )


def _point_dict_expr(point: dict[str, Any]) -> tuple[sp.Expr, sp.Expr, sp.Expr]:
    return (
        _parse_expr(point.get("x_expr"), float(point.get("x", 0))),
        _parse_expr(point.get("y_expr"), float(point.get("y", 0))),
        _parse_expr(point.get("z_expr"), float(point.get("z", 0))),
    )


def _parse_expr(expr: str | None, value: float) -> sp.Expr:
    if expr:
        try:
            parsed = sp.sympify(expr.replace("^", "**"), locals=_SAFE_SYMPY_LOCALS)
            if not parsed.free_symbols:
                return sp.simplify(parsed)
        except Exception:
            pass
    return sp.Rational(str(float(value))).limit_denominator(1_000_000)


def _expr_float(expr: sp.Expr) -> float:
    return float(sp.N(expr))


def _expr_text(expr: sp.Expr) -> str:
    simplified = sp.simplify(expr)
    return str(simplified).replace("**", "^")


def _expr_complexity(expr: sp.Expr) -> int:
    simplified = sp.simplify(expr)
    if simplified == 0:
        return 0
    if simplified.is_Integer:
        return 1 + abs(int(simplified))
    if simplified.is_Rational:
        return 4 + abs(int(simplified.p)) + abs(int(simplified.q))
    return 20 + len(str(simplified))


def compute_three_geometry(scene: MathScene) -> dict[str, Any]:
    points = _point_map(scene)
    lines = [obj for obj in scene.objects if isinstance(obj, Line3D)]
    planes = [obj for obj in scene.objects if isinstance(obj, Plane)]
    vectors = [obj for obj in scene.objects if isinstance(obj, Vector3D)]
    spheres = [obj for obj in scene.objects if isinstance(obj, Sphere)]
    warnings: list[str] = []
    intersections: list[dict[str, Any]] = []
    computed_vectors: list[dict[str, Any]] = []
    measurements: list[dict[str, Any]] = []

    pair_count = len(lines) * (len(lines) - 1) // 2 + len(lines) * len(planes)
    if pair_count <= MAX_COMPUTED_PAIRS:
        for line_1, line_2 in combinations(lines, 2):
            result = _line_line_intersection(line_1, line_2, points)
            intersections.append(result)
            if result["status"] in {"parallel", "coincident", "skew", "degenerate"}:
                warnings.append(_intersection_warning(result))

        for line in lines:
            for plane in planes:
                result = _line_plane_intersection(line, plane, points)
                intersections.append(result)
                if result["status"] in {"parallel", "line_in_plane", "degenerate"}:
                    warnings.append(_intersection_warning(result))
    else:
        warnings.append(f"Skipped computed intersections because {pair_count} object pairs exceed {MAX_COMPUTED_PAIRS}.")

    normal_length = _normal_length(points)
    for plane in planes:
        if not plane.show_normal:
            continue
        plane_data = _plane_data(plane, points)
        if plane_data is None:
            warnings.append(f"Plane {plane.name or _plane_label(plane)} is degenerate; normal vector was not rendered.")
            continue
        centroid, normal = plane_data
        end = _add(centroid, _scale(normal, normal_length))
        computed_vectors.append({
            "name": f"n_{plane.name or _plane_label(plane)}",
            "from": _as_point(centroid),
            "to": _as_point(end),
            "color": "#7c3aed",
            "kind": "normal",
            "target": plane.name or _plane_label(plane),
        })

    for vector in vectors:
        start = points.get(vector.from_point)
        end = points.get(vector.to_point)
        if start is None or end is None:
            warnings.append(f"Vector {vector.name or ''} references a missing point.")
            continue
        computed_vectors.append({
            "name": vector.name,
            "from": _as_point(_point_tuple(start)),
            "to": _as_point(_point_tuple(end)),
            "color": vector.color,
            "kind": "vector",
            "target": vector.name,
        })

    for sphere in spheres:
        for plane in planes:
            result = _sphere_plane_distance(sphere, plane, points)
            measurements.append(result)
            if result["status"] == "degenerate":
                warnings.append(f"Sphere-plane measurement {result['sphere']} and {result['plane']}: degenerate.")

    return {"intersections": intersections, "vectors": computed_vectors, "measurements": measurements, "warnings": warnings}


def calculate_point_point_distance(points: dict[str, Vec3], a: str, b: str) -> dict[str, Any]:
    result = _calculation_result("distance_point_point", f"d({a},{b})", [a, b])
    missing = _missing_points(points, [a, b])
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    delta = _sub(points[b], points[a])
    value = _norm(delta)
    completed = _complete_result(
        result,
        value,
        f"d({a},{b})=\\sqrt{{(x_{b}-x_{a})^2+(y_{b}-y_{a})^2+(z_{b}-z_{a})^2}}",
        f"\\sqrt{{{_fmt(delta[0])}^2+{_fmt(delta[1])}^2+{_fmt(delta[2])}^2}}",
        "distance",
    )
    exact = _exact_distance_latex(delta)
    if exact is not None:
        completed["result_latex"] = exact
    return completed


def calculate_point_line_distance(points: dict[str, Vec3], point_name: str, line_points: tuple[str, str]) -> dict[str, Any]:
    a, b = line_points
    result = _calculation_result("distance_point_line", f"d({point_name},{a}{b})", [point_name, a, b])
    missing = _missing_points(points, [point_name, a, b])
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    p, line_a, line_b = points[point_name], points[a], points[b]
    direction = _sub(line_b, line_a)
    length = _norm(direction)
    if length <= EPS:
        return _with_warning(result, f"Đường thẳng {a}{b} suy biến vì {a} và {b} trùng nhau.")
    cross_value = _cross(_sub(p, line_a), direction)
    value = _norm(cross_value) / length
    result["foot"] = _as_point(_project_point_to_line(p, line_a, direction))
    return _complete_result(
        result,
        value,
        f"d({point_name},{a}{b})=\\frac{{\\|\\overrightarrow{{{a}{point_name}}}\\times\\overrightarrow{{{a}{b}}}\\|}}{{\\|\\overrightarrow{{{a}{b}}}\\|}}",
        f"\\frac{{\\|{_vec_latex(cross_value)}\\|}}{{{_fmt(length)}}}",
        "distance",
    )


def calculate_line_line_distance(points: dict[str, Vec3], edge_1: tuple[str, str], edge_2: tuple[str, str]) -> dict[str, Any]:
    a, b = edge_1
    c, d = edge_2
    result = _calculation_result("distance_line_line", f"d({a}{b},{c}{d})", [a, b, c, d])
    missing = _missing_points(points, [a, b, c, d])
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    p, q = points[a], points[c]
    u = _sub(points[b], points[a])
    v = _sub(points[d], points[c])
    if _norm(u) <= EPS or _norm(v) <= EPS:
        return _with_warning(result, f"Đường thẳng {a}{b} hoặc {c}{d} suy biến vì hai điểm trùng nhau.")
    normal = _cross(u, v)
    normal_norm = _norm(normal)
    if normal_norm <= EPS:
        cross_value = _cross(_sub(q, p), u)
        value = _norm(cross_value) / _norm(u)
        return _complete_result(
            result,
            value,
            f"d({a}{b},{c}{d})=d({c},{a}{b})=\\frac{{\\|\\overrightarrow{{{a}{c}}}\\times\\overrightarrow{{{a}{b}}}\\|}}{{\\|\\overrightarrow{{{a}{b}}}\\|}}",
            f"\\frac{{\\|{_vec_latex(cross_value)}\\|}}{{{_fmt(_norm(u))}}}",
            "distance",
        )
    value = abs(_dot(_sub(q, p), normal)) / normal_norm
    return _complete_result(
        result,
        value,
        f"d({a}{b},{c}{d})=\\frac{{|\\overrightarrow{{{a}{c}}}\\cdot(\\overrightarrow{{{a}{b}}}\\times\\overrightarrow{{{c}{d}}})|}}{{\\|\\overrightarrow{{{a}{b}}}\\times\\overrightarrow{{{c}{d}}}\\|}}",
        f"\\frac{{|{_fmt(_dot(_sub(q, p), normal))}|}}{{{_fmt(normal_norm)}}}",
        "distance",
    )


def calculate_point_plane_distance(points: dict[str, Vec3], point_name: str, plane_points: list[str]) -> dict[str, Any]:
    label = "".join(plane_points)
    result = _calculation_result("distance_point_plane", f"d({point_name},({label}))", [point_name, *plane_points])
    missing = _missing_points(points, [point_name, *plane_points])
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    plane_data = _plane_data_from_names(points, plane_points)
    if plane_data is None:
        return _with_warning(result, f"Mặt phẳng {label} suy biến vì không xác định được vector pháp tuyến.")
    plane_point, normal = plane_data
    p = points[point_name]
    signed_distance = _dot(normal, _sub(p, plane_point))
    value = abs(signed_distance)
    result["foot"] = _as_point(_sub(p, _scale(normal, signed_distance)))
    return _complete_result(
        result,
        value,
        f"d({point_name},({label}))=\\frac{{|\\vec n\\cdot\\overrightarrow{{{plane_points[0]}{point_name}}}|}}{{\\|\\vec n\\|}}",
        f"\\frac{{|{_vec_latex(normal)}\\cdot{_vec_latex(_sub(p, plane_point))}|}}{{{_fmt(_norm(normal))}}}",
        "distance",
    )


def calculate_line_line_angle(points: dict[str, Vec3], edge_1: tuple[str, str], edge_2: tuple[str, str]) -> dict[str, Any]:
    a, b = edge_1
    c, d = edge_2
    result = _calculation_result("angle_line_line", f"\\angle({a}{b},{c}{d})", [a, b, c, d])
    missing = _missing_points(points, [a, b, c, d])
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    v1 = _sub(points[b], points[a])
    v2 = _sub(points[d], points[c])
    angle = _angle_between_vectors(v1, v2)
    if angle is None:
        return _with_warning(result, f"Không xác định được góc vì {a}{b} hoặc {c}{d} suy biến.")
    return _complete_result(
        result,
        angle,
        f"\\cos\\varphi=\\frac{{|\\overrightarrow{{{a}{b}}}\\cdot\\overrightarrow{{{c}{d}}}|}}{{\\|\\overrightarrow{{{a}{b}}}\\|\\,\\|\\overrightarrow{{{c}{d}}}\\|}}",
        f"\\varphi=\\arccos\\left(\\frac{{|{_fmt(_dot(v1, v2))}|}}{{{_fmt(_norm(v1))}\\cdot{_fmt(_norm(v2))}}}\\right)",
        "degrees",
    )


def calculate_line_plane_angle(points: dict[str, Vec3], edge: tuple[str, str], plane_points: list[str]) -> dict[str, Any]:
    a, b = edge
    label = "".join(plane_points)
    result = _calculation_result("angle_line_plane", f"\\angle({a}{b},({label}))", [a, b, *plane_points])
    missing = _missing_points(points, [a, b, *plane_points])
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    plane_data = _plane_data_from_names(points, plane_points)
    if plane_data is None:
        return _with_warning(result, f"Mặt phẳng {label} suy biến vì không xác định được vector pháp tuyến.")
    direction = _sub(points[b], points[a])
    normal = plane_data[1]
    direction_norm = _norm(direction)
    if direction_norm <= EPS:
        return _with_warning(result, f"Đường thẳng {a}{b} suy biến vì {a} và {b} trùng nhau.")
    ratio = _clamp(abs(_dot(direction, normal)) / (direction_norm * _norm(normal)))
    angle = degrees(asin(ratio))
    return _complete_result(
        result,
        angle,
        f"\\sin\\varphi=\\frac{{|\\overrightarrow{{{a}{b}}}\\cdot\\vec n|}}{{\\|\\overrightarrow{{{a}{b}}}\\|\\,\\|\\vec n\\|}}",
        f"\\varphi=\\arcsin\\left(\\frac{{|{_fmt(_dot(direction, normal))}|}}{{{_fmt(direction_norm)}\\cdot{_fmt(_norm(normal))}}}\\right)",
        "degrees",
    )


def calculate_plane_plane_angle(points: dict[str, Vec3], plane_1_points: list[str], plane_2_points: list[str]) -> dict[str, Any]:
    label_1 = "".join(plane_1_points)
    label_2 = "".join(plane_2_points)
    result = _calculation_result("angle_plane_plane", f"\\angle(({label_1}),({label_2}))", [*plane_1_points, *plane_2_points])
    missing = _missing_points(points, [*plane_1_points, *plane_2_points])
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    plane_1 = _plane_data_from_names(points, plane_1_points)
    plane_2 = _plane_data_from_names(points, plane_2_points)
    if plane_1 is None or plane_2 is None:
        return _with_warning(result, f"Không xác định được vector pháp tuyến của một trong hai mặt phẳng.")
    normal_1, normal_2 = plane_1[1], plane_2[1]
    angle = _angle_between_vectors(normal_1, normal_2)
    if angle is None:
        return _with_warning(result, f"Không xác định được góc giữa ({label_1}) và ({label_2}).")
    return _complete_result(
        result,
        angle,
        "\\cos\\varphi=\\frac{|\\vec n_1\\cdot\\vec n_2|}{\\|\\vec n_1\\|\\,\\|\\vec n_2\\|}",
        f"\\varphi=\\arccos\\left(\\frac{{|{_fmt(_dot(normal_1, normal_2))}|}}{{{_fmt(_norm(normal_1))}\\cdot{_fmt(_norm(normal_2))}}}\\right)",
        "degrees",
    )


def calculate_polygon_area(points: dict[str, Vec3], polygon_points: list[str]) -> dict[str, Any]:
    label = "".join(polygon_points)
    result = _calculation_result("area_polygon", f"S({label})", polygon_points)
    missing = _missing_points(points, polygon_points)
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    resolved = [points[name] for name in polygon_points]
    if len(resolved) < 3:
        return _with_warning(result, "Cần ít nhất 3 điểm để tính diện tích.")
    area = 0.0
    anchor = resolved[0]
    details: list[str] = []
    for index in range(1, len(resolved) - 1):
        cross_value = _cross(_sub(resolved[index], anchor), _sub(resolved[index + 1], anchor))
        triangle_area = _norm(cross_value) / 2
        area += triangle_area
        details.append(_fmt(triangle_area))
    result["parts"] = details
    completed = _complete_result(
        result,
        area,
        f"S({label})=\\sum \\frac12\\|\\vec u_i\\times\\vec v_i\\|",
        " + ".join(details) if details else "0",
        "area",
    )
    if len(resolved) == 3:
        exact = _exact_norm_over_latex(_cross(_sub(resolved[1], anchor), _sub(resolved[2], anchor)), 2)
        if exact is not None:
            completed["result_latex"] = exact
    return completed


def calculate_tetrahedron_volume(points: dict[str, Vec3], tetra_points: list[str]) -> dict[str, Any]:
    label = "".join(tetra_points)
    result = _calculation_result("volume_tetrahedron", f"V({label})", tetra_points)
    if len(tetra_points) < 4:
        return _with_warning(result, "Cần 4 điểm để tính thể tích tứ diện.")
    a, b, c, d = tetra_points[:4]
    missing = _missing_points(points, [a, b, c, d])
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    triple = _dot(_cross(_sub(points[b], points[a]), _sub(points[c], points[a])), _sub(points[d], points[a]))
    volume = abs(triple) / 6
    completed = _complete_result(
        result,
        volume,
        f"V=\\frac16|[\\overrightarrow{{{a}{b}}},\\overrightarrow{{{a}{c}}},\\overrightarrow{{{a}{d}}}]|",
        f"\\frac16|{_fmt(triple)}|",
        "volume",
    )
    exact = _exact_scalar_over_latex(abs(triple), 6)
    if exact is not None:
        completed["result_latex"] = exact
    return completed


def calculate_pyramid_volume(points: dict[str, Vec3], apex: str, base_points: list[str]) -> dict[str, Any]:
    label = f"{apex}.{''.join(base_points)}"
    result = _calculation_result("volume_pyramid", f"V({label})", [apex, *base_points])
    missing = _missing_points(points, [apex, *base_points])
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    area_result = calculate_polygon_area(points, base_points)
    if area_result["status"] != "ok":
        return _with_warning(result, "Không tính được diện tích đáy.")
    plane_data = _plane_data_from_names(points, base_points)
    if plane_data is None:
        return _with_warning(result, "Đáy suy biến nên không tính được chiều cao.")
    plane_point, normal = plane_data
    height = abs(_dot(normal, _sub(points[apex], plane_point)))
    volume = area_result["result_value"] * height / 3
    return _complete_result(
        result,
        volume,
        "V=\\frac13 S_{đáy}\\cdot h",
        f"\\frac13\\cdot{_fmt(area_result['result_value'])}\\cdot{_fmt(height)}",
        "volume",
    )


def calculate_vector_dot(points: dict[str, Vec3], edge_1: tuple[str, str], edge_2: tuple[str, str]) -> dict[str, Any]:
    a, b = edge_1
    c, d = edge_2
    result = _calculation_result("vector_dot", f"\\overrightarrow{{{a}{b}}}\\cdot\\overrightarrow{{{c}{d}}}", [a, b, c, d])
    missing = _missing_points(points, [a, b, c, d])
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    u = _sub(points[b], points[a])
    v = _sub(points[d], points[c])
    value = _dot(u, v)
    return _complete_result(
        result,
        value,
        f"\\overrightarrow{{{a}{b}}}\\cdot\\overrightarrow{{{c}{d}}}=u_xv_x+u_yv_y+u_zv_z",
        f"{_vec_latex(u)}\\cdot{_vec_latex(v)}={_fmt(u[0])}\\cdot{_fmt(v[0])}+{_fmt(u[1])}\\cdot{_fmt(v[1])}+{_fmt(u[2])}\\cdot{_fmt(v[2])}",
        "scalar",
    )


def calculate_vector_cross(points: dict[str, Vec3], edge_1: tuple[str, str], edge_2: tuple[str, str]) -> dict[str, Any]:
    a, b = edge_1
    c, d = edge_2
    result = _calculation_result("vector_cross", f"\\overrightarrow{{{a}{b}}}\\times\\overrightarrow{{{c}{d}}}", [a, b, c, d])
    missing = _missing_points(points, [a, b, c, d])
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    u = _sub(points[b], points[a])
    v = _sub(points[d], points[c])
    value = _cross(u, v)
    result["result_vector"] = _as_point(value)
    return _complete_text_result(
        result,
        f"\\overrightarrow{{{a}{b}}}\\times\\overrightarrow{{{c}{d}}}=\\begin{{vmatrix}}\\vec i&\\vec j&\\vec k\\\\u_x&u_y&u_z\\\\v_x&v_y&v_z\\end{{vmatrix}}",
        f"{_vec_latex(u)}\\times{_vec_latex(v)}",
        _vec_latex(value),
        f"{result['label']} = {_vec_latex(value)}",
    )


def calculate_line_equation(points: dict[str, Vec3], edge: tuple[str, str]) -> dict[str, Any]:
    a, b = edge
    result = _calculation_result("equation_line", f"d_{{{a}{b}}}", [a, b])
    missing = _missing_points(points, [a, b])
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    p = points[a]
    u = _sub(points[b], points[a])
    if _norm(u) <= EPS:
        return _with_warning(result, f"Đường thẳng {a}{b} suy biến vì {a} và {b} trùng nhau.")
    result["point"] = _as_point(p)
    result["direction"] = _as_point(u)
    equation = f"\\begin{{cases}}x={_fmt(p[0])}+{_fmt(u[0])}t\\\\y={_fmt(p[1])}+{_fmt(u[1])}t\\\\z={_fmt(p[2])}+{_fmt(u[2])}t\\end{{cases}}"
    return _complete_text_result(
        result,
        f"d_{{{a}{b}}}: M={a}+t\\overrightarrow{{{a}{b}}}",
        f"{a}{_vec_latex(p)},\\;\\overrightarrow{{{a}{b}}}={_vec_latex(u)}",
        equation,
        f"d_{{{a}{b}}}: {equation}",
    )


def calculate_plane_equation(points: dict[str, Vec3], plane_points: list[str]) -> dict[str, Any]:
    label = "".join(plane_points)
    result = _calculation_result("equation_plane", f"({label})", plane_points)
    missing = _missing_points(points, plane_points)
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    plane_data = _raw_plane_data_from_names(points, plane_points)
    if plane_data is None:
        return _with_warning(result, f"Mặt phẳng {label} suy biến vì các điểm thẳng hàng hoặc trùng nhau.")
    anchor, normal, basis = plane_data
    d_value = -_dot(normal, anchor)
    result["coefficients"] = {"a": normal[0], "b": normal[1], "c": normal[2], "d": d_value}
    equation = _plane_equation_latex(normal, d_value)
    return _complete_text_result(
        result,
        f"({label}): a(x-x_0)+b(y-y_0)+c(z-z_0)=0",
        f"\\vec n=\\overrightarrow{{{basis[0]}{basis[1]}}}\\times\\overrightarrow{{{basis[0]}{basis[2]}}}={_vec_latex(normal)}",
        equation,
        f"({label}): {equation}",
    )


def calculate_point_line_projection(points: dict[str, Vec3], point_name: str, line_points: tuple[str, str]) -> dict[str, Any]:
    a, b = line_points
    result = _calculation_result("projection_point_line", f"H=\\operatorname{{proj}}_{{{a}{b}}}({point_name})", [point_name, a, b])
    missing = _missing_points(points, [point_name, a, b])
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    p = points[point_name]
    line_a = points[a]
    direction = _sub(points[b], line_a)
    if _norm(direction) <= EPS:
        return _with_warning(result, f"Đường thẳng {a}{b} suy biến vì {a} và {b} trùng nhau.")
    foot = _project_point_to_line(p, line_a, direction)
    result["point"] = _as_point(foot)
    return _complete_text_result(
        result,
        f"H={a}+\\frac{{\\overrightarrow{{{a}{point_name}}}\\cdot\\overrightarrow{{{a}{b}}}}}{{\\overrightarrow{{{a}{b}}}\\cdot\\overrightarrow{{{a}{b}}}}}\\overrightarrow{{{a}{b}}}",
        f"H={_vec_latex(line_a)}+\\frac{{{_fmt(_dot(_sub(p, line_a), direction))}}}{{{_fmt(_dot(direction, direction))}}}{_vec_latex(direction)}",
        f"H{_vec_latex(foot)}",
        f"H{_vec_latex(foot)}",
    )


def calculate_point_plane_projection(points: dict[str, Vec3], point_name: str, plane_points: list[str]) -> dict[str, Any]:
    label = "".join(plane_points)
    result = _calculation_result("projection_point_plane", f"H=\\operatorname{{proj}}_{{({label})}}({point_name})", [point_name, *plane_points])
    missing = _missing_points(points, [point_name, *plane_points])
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    plane_data = _plane_data_from_names(points, plane_points)
    if plane_data is None:
        return _with_warning(result, f"Mặt phẳng {label} suy biến vì không xác định được vector pháp tuyến.")
    plane_point, normal = plane_data
    p = points[point_name]
    signed_distance = _dot(normal, _sub(p, plane_point))
    foot = _sub(p, _scale(normal, signed_distance))
    result["point"] = _as_point(foot)
    return _complete_text_result(
        result,
        "H=P-(\\vec n\\cdot\\overrightarrow{AP_0})\\vec n",
        f"H={_vec_latex(p)}-{_fmt(signed_distance)}{_vec_latex(normal)}",
        f"H{_vec_latex(foot)}",
        f"H{_vec_latex(foot)}",
    )


def calculate_point_line_reflection(points: dict[str, Vec3], point_name: str, line_points: tuple[str, str]) -> dict[str, Any]:
    projection = calculate_point_line_projection(points, point_name, line_points)
    projection["kind"] = "reflection_point_line"
    projection["label"] = f"{point_name}'"
    if projection["status"] != "ok":
        return projection
    foot = _point_from_dict(projection["point"])
    reflected = _sub(_scale(foot, 2), points[point_name])
    projection["point"] = _as_point(reflected)
    return _complete_text_result(projection, "P'=2H-P", f"{point_name}'=2{_vec_latex(foot)}-{_vec_latex(points[point_name])}", f"{point_name}'{_vec_latex(reflected)}", f"{point_name}'{_vec_latex(reflected)}")


def calculate_point_plane_reflection(points: dict[str, Vec3], point_name: str, plane_points: list[str]) -> dict[str, Any]:
    projection = calculate_point_plane_projection(points, point_name, plane_points)
    projection["kind"] = "reflection_point_plane"
    projection["label"] = f"{point_name}'"
    if projection["status"] != "ok":
        return projection
    foot = _point_from_dict(projection["point"])
    reflected = _sub(_scale(foot, 2), points[point_name])
    projection["point"] = _as_point(reflected)
    return _complete_text_result(projection, "P'=2H-P", f"{point_name}'=2{_vec_latex(foot)}-{_vec_latex(points[point_name])}", f"{point_name}'{_vec_latex(reflected)}", f"{point_name}'{_vec_latex(reflected)}")


def prove_collinear(points: dict[str, Vec3], names: list[str]) -> dict[str, Any]:
    result = _calculation_result("proof_collinear", f"{''.join(names)} thẳng hàng", names)
    if len(names) < 3:
        return _with_warning(result, "Cần ít nhất 3 điểm để chứng minh thẳng hàng.")
    missing = _missing_points(points, names)
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    a, b = names[0], names[1]
    base = _sub(points[b], points[a])
    if _norm(base) <= EPS:
        return _with_warning(result, f"Không xác định được đường chuẩn vì {a} và {b} trùng nhau.")
    values = [_cross(base, _sub(points[name], points[a])) for name in names[2:]]
    ok = all(_norm(value) <= DISPLAY_EPS for value in values)
    return _complete_text_result(result, f"\\overrightarrow{{{a}{b}}}\\times\\overrightarrow{{{a}X}}=\\vec 0", "; ".join(_vec_latex(value) for value in values), "\\text{ĐÚNG}" if ok else "\\text{SAI}", f"{''.join(names)} thẳng hàng: {'ĐÚNG' if ok else 'SAI'}")


def prove_coplanar(points: dict[str, Vec3], names: list[str]) -> dict[str, Any]:
    result = _calculation_result("proof_coplanar", f"{''.join(names)} đồng phẳng", names)
    if len(names) < 3:
        return _with_warning(result, "Cần ít nhất 3 điểm để xét đồng phẳng.")
    missing = _missing_points(points, names)
    if missing:
        return _with_warning(result, f"Điểm {', '.join(missing)} không có trong scene.")
    if len(names) == 3:
        return _complete_text_result(result, "Ba điểm luôn đồng phẳng", "", "\\text{ĐÚNG}", f"{''.join(names)} đồng phẳng: ĐÚNG")
    plane_data = _raw_plane_data_from_names(points, names[:3])
    if plane_data is None:
        return _complete_text_result(result, "Các điểm đầu thẳng hàng nên tồn tại vô số mặt phẳng chứa chúng", "", "\\text{ĐÚNG}", f"{''.join(names)} đồng phẳng: ĐÚNG")
    anchor, normal, basis = plane_data
    values = [_dot(normal, _sub(points[name], anchor)) for name in names[3:]]
    ok = all(abs(value) <= DISPLAY_EPS for value in values)
    return _complete_text_result(result, f"[\\overrightarrow{{{basis[0]}{basis[1]}}},\\overrightarrow{{{basis[0]}{basis[2]}}},\\overrightarrow{{{basis[0]}X}}]=0", "; ".join(_fmt(value) for value in values), "\\text{ĐÚNG}" if ok else "\\text{SAI}", f"{''.join(names)} đồng phẳng: {'ĐÚNG' if ok else 'SAI'}")


def _is_origin(point: Point3D) -> bool:
    return abs(point.x) < EPS and abs(point.y) < EPS and abs(point.z) < EPS


def _segment_segment_intersection(segment_1: Segment, segment_2: Segment, points: dict[str, Point3D]) -> Vec3 | None:
    start_1 = points.get(segment_1.points[0])
    end_1 = points.get(segment_1.points[1])
    start_2 = points.get(segment_2.points[0])
    end_2 = points.get(segment_2.points[1])
    if start_1 is None or end_1 is None or start_2 is None or end_2 is None:
        return None

    p = _point_tuple(start_1)
    q = _point_tuple(start_2)
    r = _sub(_point_tuple(end_1), p)
    s = _sub(_point_tuple(end_2), q)
    if _norm(r) <= EPS or _norm(s) <= EPS:
        return None

    p_minus_q = _sub(p, q)
    a = _dot(r, r)
    b = _dot(r, s)
    c = _dot(s, s)
    d = _dot(r, p_minus_q)
    e = _dot(s, p_minus_q)
    denom = a * c - b * b
    if abs(denom) <= EPS:
        return None

    t = (b * e - c * d) / denom
    u = (a * e - b * d) / denom
    if t <= DISPLAY_EPS or t >= 1 - DISPLAY_EPS or u <= DISPLAY_EPS or u >= 1 - DISPLAY_EPS:
        return None

    closest_1 = _add(p, _scale(r, t))
    closest_2 = _add(q, _scale(s, u))
    if _distance(closest_1, closest_2) > DISPLAY_EPS:
        return None
    return _scale(_add(closest_1, closest_2), 0.5)


def _next_intersection_name(existing_names: set[str], offset: int = 0) -> str:
    # Natural intersection labels: I, J, K, M, N, P, Q, R...
    candidates = ["I", "J", "K", "M", "N", "P", "Q", "R"]
    
    # First try the primary candidates
    for i in range(offset, len(candidates)):
        name = candidates[i]
        if name not in existing_names:
            return name
            
    # Fallback to I with index if all candidates are taken
    index = 1 + offset
    while True:
        name = f"I{index}"
        if name not in existing_names:
            return name
        index += 1


def _line_line_intersection(line_1: Line3D, line_2: Line3D, points: dict[str, Point3D]) -> dict[str, Any]:
    label_1 = _line_label(line_1)
    label_2 = _line_label(line_2)
    result: dict[str, Any] = {
        "type": "line_line",
        "object_1": label_1,
        "object_2": label_2,
        "status": "degenerate",
        "point": None,
        "parameters": None,
        "distance": None,
    }
    line_data_1 = _line_data(line_1, points)
    line_data_2 = _line_data(line_2, points)
    if line_data_1 is None or line_data_2 is None:
        return result

    p, r = line_data_1
    q, s = line_data_2
    if _norm(r) <= EPS or _norm(s) <= EPS:
        return result

    rxs = _cross(r, s)
    q_minus_p = _sub(q, p)
    if _norm(rxs) <= EPS:
        result["status"] = "coincident" if _norm(_cross(q_minus_p, r)) <= DISPLAY_EPS else "parallel"
        return result

    p_minus_q = _sub(p, q)
    a = _dot(r, r)
    b = _dot(r, s)
    c = _dot(s, s)
    d = _dot(r, p_minus_q)
    e = _dot(s, p_minus_q)
    denom = a * c - b * b
    if abs(denom) <= EPS:
        result["status"] = "degenerate"
        return result

    t = (b * e - c * d) / denom
    u = (a * e - b * d) / denom
    closest_1 = _add(p, _scale(r, t))
    closest_2 = _add(q, _scale(s, u))
    distance = _distance(closest_1, closest_2)
    result["parameters"] = {"t": t, "u": u}
    result["distance"] = distance
    if distance <= DISPLAY_EPS:
        result["status"] = "intersect"
        result["point"] = _as_point(_scale(_add(closest_1, closest_2), 0.5))
    else:
        result["status"] = "skew"
    return result


def _line_plane_intersection(line: Line3D, plane: Plane, points: dict[str, Point3D]) -> dict[str, Any]:
    line_label = _line_label(line)
    plane_label = plane.name or _plane_label(plane)
    result: dict[str, Any] = {
        "type": "line_plane",
        "line": line_label,
        "plane": plane_label,
        "status": "degenerate",
        "point": None,
        "parameter": None,
    }
    line_data = _line_data(line, points)
    plane_data = _plane_data(plane, points)
    if line_data is None or plane_data is None:
        return result

    p0, direction = line_data
    plane_point, normal = plane_data
    if _norm(direction) <= EPS or _norm(normal) <= EPS:
        return result

    denom = _dot(normal, direction)
    offset = _dot(normal, _sub(p0, plane_point))
    if abs(denom) <= EPS:
        result["status"] = "line_in_plane" if abs(offset) <= DISPLAY_EPS else "parallel"
        return result

    t = -offset / denom
    intersection = _add(p0, _scale(direction, t))
    result["status"] = "intersect"
    result["parameter"] = t
    result["point"] = _as_point(intersection)
    return result


def _sphere_plane_distance(sphere: Sphere, plane: Plane, points: dict[str, Point3D]) -> dict[str, Any]:
    sphere_label = sphere.name or sphere.center
    plane_label = plane.name or _plane_label(plane)
    result: dict[str, Any] = {
        "type": "sphere_plane_distance",
        "sphere": sphere_label,
        "plane": plane_label,
        "status": "degenerate",
        "center_distance": None,
        "signed_center_distance": None,
        "minimum_distance": None,
        "radius": sphere.radius,
        "plane_foot": None,
        "nearest_sphere_point": None,
    }
    center = points.get(sphere.center)
    plane_data = _plane_data(plane, points)
    if center is None or plane_data is None or sphere.radius < 0:
        return result

    center_point = _point_tuple(center)
    plane_point, normal = plane_data
    signed_distance = _dot(normal, _sub(center_point, plane_point))
    center_distance = abs(signed_distance)
    minimum_distance = max(center_distance - sphere.radius, 0)
    foot = _sub(center_point, _scale(normal, signed_distance))
    toward_plane = _scale(normal, -1 if signed_distance >= 0 else 1)
    nearest = _add(center_point, _scale(toward_plane, sphere.radius))

    if abs(center_distance - sphere.radius) <= DISPLAY_EPS:
        status = "tangent"
    elif center_distance < sphere.radius:
        status = "intersect"
    else:
        status = "separate"

    result.update({
        "status": status,
        "center_distance": center_distance,
        "signed_center_distance": signed_distance,
        "minimum_distance": minimum_distance,
        "plane_foot": _as_point(foot),
        "nearest_sphere_point": _as_point(nearest),
    })
    return result


def _line_data(line: Line3D, points: dict[str, Point3D]) -> tuple[Vec3, Vec3] | None:
    start = points.get(line.through[0])
    end = points.get(line.through[1])
    if start is None or end is None:
        return None
    p0 = _point_tuple(start)
    return p0, _sub(_point_tuple(end), p0)


def _plane_data(plane: Plane, points: dict[str, Point3D]) -> tuple[Vec3, Vec3] | None:
    resolved = [_point_tuple(points[name]) for name in plane.points if name in points]
    return plane_from_points(resolved, EPS)


def _point_map(scene: MathScene) -> dict[str, Point3D]:
    return {obj.name: obj for obj in scene.objects if isinstance(obj, Point3D)}


def _point_tuple(point: Point3D) -> Vec3:
    return vec3(point.x, point.y, point.z)


def _point_key(point: Vec3) -> tuple[float, float, float]:
    return to_tuple(point)


def _centroid(points: list[Vec3]) -> Vec3:
    return linalg_centroid(points)


def _normal_length(points: dict[str, Point3D]) -> float:
    values = [_point_tuple(point) for point in points.values()]
    if len(values) < 2:
        return 0.8
    diagonal = bbox_diagonal(values)
    return min(max(diagonal * 0.18, 0.4), 1.2)


def _as_point(point: Vec3) -> dict[str, float]:
    return {"x": point[0], "y": point[1], "z": point[2]}


def _calculation_result(kind: str, label: str, highlight: list[str]) -> dict[str, Any]:
    return {
        "kind": kind,
        "status": "degenerate",
        "label": label,
        "formula_latex": None,
        "substitution_latex": None,
        "result_latex": None,
        "result_value": None,
        "highlight": list(dict.fromkeys(highlight)),
        "warnings": [],
    }


def _complete_result(result: dict[str, Any], value: float, formula: str, substitution: str, unit: str) -> dict[str, Any]:
    if unit == "degrees":
        latex = _nsimplify_angle_latex(value)
    else:
        latex = _nsimplify_latex(value) or _fmt(value, 6)
    result.update({
        "status": "ok",
        "formula_latex": formula,
        "substitution_latex": substitution,
        "result_latex": latex,
        "result_value": value,
        "unit": unit,
    })
    return result


# Tập radical thường gặp trong toán phổ thông (3D solid geometry)
_NSIMPLIFY_BASIS: tuple[sp.Expr, ...] = (
    sp.pi,
    sp.sqrt(2),
    sp.sqrt(3),
    sp.sqrt(5),
    sp.sqrt(6),
    sp.sqrt(7),
    sp.sqrt(10),
    sp.sqrt(11),
    sp.sqrt(13),
    sp.sqrt(14),
    sp.sqrt(15),
    sp.sqrt(21),
)
_NSIMPLIFY_TOLERANCE = 1e-9
_NSIMPLIFY_FLOAT_RELTOL = 1e-7


def _nsimplify_latex(value: float) -> str | None:
    """Thử biểu diễn giá trị float dưới dạng đại số đẹp (a*sqrt(n)/b, pi, …).

    Trả về LaTeX nếu tìm thấy biểu thức simple đủ tin cậy (sai số <1e-7 tương đối);
    None nếu fallback float.

    Thuật toán: ưu tiên radical/π (basis_value), nếu kết quả chỉ là Rational thì
    so với ``Rational.limit_denominator(1000)`` để chọn mẫu nhỏ nhất hợp lý.
    """
    if not isfinite(value):
        return None
    abs_v = abs(value)
    if abs_v < _NSIMPLIFY_TOLERANCE:
        return "0"

    relative_tol = max(abs_v, 1.0) * _NSIMPLIFY_FLOAT_RELTOL

    # 1) Thử nsimplify với basis radical/π
    radical_candidate: sp.Expr | None = None
    try:
        nsimp = sp.nsimplify(value, _NSIMPLIFY_BASIS, tolerance=_NSIMPLIFY_TOLERANCE, rational=False)
        nsimp_simplified = sp.simplify(nsimp)
        nsimp_value = float(nsimp_simplified.evalf())
        if isfinite(nsimp_value) and abs(nsimp_value - value) <= relative_tol:
            text = sp.srepr(nsimp_simplified)
            if len(text) <= 200:
                # Nếu chứa pi hoặc sqrt → đây là dạng "đẹp", return ngay
                if any(symbol in text for symbol in ("pi", "sqrt", "Pow")):
                    return sp.latex(nsimp_simplified)
                radical_candidate = nsimp_simplified
    except (TypeError, ValueError, sp.SympifyError):  # pragma: no cover
        pass

    # 2) Thử Rational đơn giản
    try:
        rational = sp.Rational(value).limit_denominator(1000)
        if abs(float(rational) - value) <= relative_tol:
            if rational.q == 1 and abs(rational.p) < 10**6:
                return str(rational.p)
            if rational.q != 1 and abs(rational.p) < 10**4 and rational.q <= 1000:
                return sp.latex(rational)
    except (TypeError, ValueError):
        pass

    # 3) Fallback radical_candidate (Rational mà nsimplify trả về với mẫu lớn)
    if radical_candidate is not None:
        return sp.latex(radical_candidate)
    return None


def _nsimplify_angle_latex(value_deg: float) -> str:
    """LaTeX cho góc theo độ. Ưu tiên giá trị đặc biệt (30°, 45°, 60°, 90°…)."""
    if not isfinite(value_deg):
        return _fmt(value_deg, 6) + "^\\circ"
    if abs(value_deg - round(value_deg)) <= 1e-9:
        return f"{int(round(value_deg))}^\\circ"
    rounded = round(value_deg, 4)
    if abs(value_deg - rounded) <= 1e-9:
        return f"{rounded}^\\circ"
    return f"{_fmt(value_deg, 6)}^\\circ"


def _complete_text_result(result: dict[str, Any], formula: str, substitution: str, result_latex: str, answer: str) -> dict[str, Any]:
    result.update({
        "status": "ok",
        "formula_latex": formula,
        "substitution_latex": substitution,
        "result_latex": result_latex,
        "answer": answer,
    })
    return result


def _with_warning(result: dict[str, Any], warning: str) -> dict[str, Any]:
    result["warnings"].append(warning)
    return result


def _missing_points(points: dict[str, Vec3], names: list[str]) -> list[str]:
    return [name for name in dict.fromkeys(names) if name not in points]


def _plane_data_from_names(points: dict[str, Vec3], names: list[str]) -> tuple[Vec3, Vec3] | None:
    resolved = [points[name] for name in names if name in points]
    return plane_from_points(resolved, EPS)


def _raw_plane_data_from_names(points: dict[str, Vec3], names: list[str]) -> tuple[Vec3, Vec3, tuple[str, str, str]] | None:
    named_points = {name: points[name] for name in names if name in points}
    return raw_plane_from_named_points(named_points, EPS)


def _point_from_dict(point: dict[str, float]) -> Vec3:
    return (float(point["x"]), float(point["y"]), float(point["z"]))


def _plane_equation_latex(normal: Vec3, d_value: float) -> str:
    terms = [
        _signed_term(normal[0], "x", first=True),
        _signed_term(normal[1], "y"),
        _signed_term(normal[2], "z"),
        _signed_constant(d_value),
    ]
    body = "".join(term for term in terms if term)
    return f"{body or '0'}=0"


def _signed_term(value: float, variable: str, first: bool = False) -> str:
    if abs(value) <= DISPLAY_EPS:
        return ""
    sign = "-" if value < 0 else ("" if first else "+")
    size = abs(value)
    coefficient = "" if abs(size - 1) <= DISPLAY_EPS else _fmt(size)
    return f"{sign}{coefficient}{variable}"


def _signed_constant(value: float) -> str:
    if abs(value) <= DISPLAY_EPS:
        return ""
    return f"{'-' if value < 0 else '+'}{_fmt(abs(value))}"


def _project_point_to_line(point: Vec3, line_point: Vec3, direction: Vec3) -> Vec3:
    t = _dot(_sub(point, line_point), direction) / _dot(direction, direction)
    return _add(line_point, _scale(direction, t))


def _angle_between_vectors(first: Vec3, second: Vec3) -> float | None:
    first_norm = _norm(first)
    second_norm = _norm(second)
    if first_norm <= EPS or second_norm <= EPS:
        return None
    ratio = _clamp(abs(_dot(first, second)) / (first_norm * second_norm))
    return degrees(acos(ratio))


def _clamp(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _fmt(value: float, digits: int = 4) -> str:
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return text or "0"


def _exact_distance_latex(delta: Vec3) -> str | None:
    return _exact_norm_over_latex(delta, 1)


def _exact_norm_over_latex(vector: Vec3, divisor: int) -> str | None:
    values = [float(component) for component in vector]
    if not all(abs(value - round(value)) <= DISPLAY_EPS for value in values):
        return None
    squared = sum(int(round(value)) ** 2 for value in values)
    root = int(sqrt(squared))
    numerator = str(root) if root * root == squared else f"\\sqrt{{{squared}}}"
    if divisor == 1:
        return numerator
    return f"\\frac{{{numerator}}}{{{divisor}}}"


def _exact_scalar_over_latex(value: float, divisor: int) -> str | None:
    if abs(value - round(value)) > DISPLAY_EPS:
        return None
    numerator = int(round(value))
    if numerator % divisor == 0:
        return str(numerator // divisor)
    return f"\\frac{{{numerator}}}{{{divisor}}}"


def _vec_latex(value: Vec3) -> str:
    return f"({_fmt(value[0])},{_fmt(value[1])},{_fmt(value[2])})"


def _line_label(line: Line3D) -> str:
    return line.name or "".join(line.through)


def _plane_label(plane: Plane) -> str:
    return f"plane({''.join(plane.points)})"


def _intersection_warning(result: dict[str, Any]) -> str:
    if result["type"] == "line_line":
        return f"Line-line intersection {result['object_1']} and {result['object_2']}: {result['status']}."
    return f"Line-plane intersection {result['line']} and {result['plane']}: {result['status']}."


def _face_edges(points: list[str]) -> list[tuple[str, str]]:
    return [(points[index], points[(index + 1) % len(points)]) for index in range(len(points))]


def _edge_key(start: str, end: str) -> tuple[str, str]:
    return tuple(sorted((start, end)))


def _looks_hidden_edge(start: str, end: str, scene: MathScene) -> bool:
    """Heuristic: edges connecting 'back' points are drawn dashed.

    For typical solid geometry figures viewed from front-right-top,
    edges involving D (and D') in a box, or edges on the 'far' side
    of a base polygon tend to be hidden.
    """
    points_map = {obj.name: obj for obj in scene.objects if isinstance(obj, Point3D)}
    p1 = points_map.get(start)
    p2 = points_map.get(end)

    if not p1 or not p2:
        return False

    # Edges on the far side in z (positive z = away from default camera)
    both_far_z = p1.z > 0.5 and p2.z > 0.5
    # Or edges that go from a far-z bottom point to another far-z bottom point
    if both_far_z and p1.y < 0.1 and p2.y < 0.1:
        return True

    # Vertical edges at far-z positions
    if abs(p1.x - p2.x) < 0.01 and abs(p1.z - p2.z) < 0.01 and p1.z > 0.5:
        return True

    return False
