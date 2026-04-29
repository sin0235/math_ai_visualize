import re
from itertools import combinations
from math import sqrt
from typing import Any

from app.schemas.scene import AdvancedRenderSettings, Face, Line3D, MathScene, Plane, Point3D, Segment, Sphere, Vector3D

EPS = 1e-9
DISPLAY_EPS = 1e-6
MAX_COMPUTED_PAIRS = 100

Vec3 = tuple[float, float, float]


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

    existing_points = {_point_tuple(point): point.name for point in points.values()}
    point_names = set(points)
    objects = data.setdefault("objects", [])
    relations = data.setdefault("relations", [])
    added = 0

    for first, second in combinations(segments, 2):
        if set(first.points).intersection(second.points):
            continue
        intersection = _segment_segment_intersection(first, second, points)
        if intersection is None:
            continue
        if any(_distance(intersection, existing) <= DISPLAY_EPS for existing in existing_points):
            continue
        name = _next_intersection_name(point_names, added)
        point_names.add(name)
        existing_points[intersection] = name
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
    has_origin = any(_is_origin(point) for point in points)
    has_o = any(point.name == "O" for point in points)
    if has_origin or has_o:
        return scene

    data = scene.model_dump()
    data["objects"] = [
        {"type": "point_3d", "name": "O", "x": 0, "y": 0, "z": 0},
        *data["objects"],
    ]
    data["annotations"].append({"type": "coordinate_label", "target": "O", "metadata": {}})
    return MathScene.model_validate(data)


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
    index = 1 + offset
    while True:
        name = "I" if index == 1 else f"I{index}"
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
    if len(resolved) < 3:
        return None
    centroid = _centroid(resolved)
    for i in range(len(resolved) - 2):
        for j in range(i + 1, len(resolved) - 1):
            for k in range(j + 1, len(resolved)):
                normal = _cross(_sub(resolved[j], resolved[i]), _sub(resolved[k], resolved[i]))
                normalized = _normalize(normal)
                if _norm(normalized) > EPS:
                    return centroid, normalized
    return None


def _point_map(scene: MathScene) -> dict[str, Point3D]:
    return {obj.name: obj for obj in scene.objects if isinstance(obj, Point3D)}


def _point_tuple(point: Point3D) -> Vec3:
    return (point.x, point.y, point.z)


def _centroid(points: list[Vec3]) -> Vec3:
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
        sum(point[2] for point in points) / len(points),
    )


def _normal_length(points: dict[str, Point3D]) -> float:
    values = [_point_tuple(point) for point in points.values()]
    if len(values) < 2:
        return 0.8
    min_point = (min(p[0] for p in values), min(p[1] for p in values), min(p[2] for p in values))
    max_point = (max(p[0] for p in values), max(p[1] for p in values), max(p[2] for p in values))
    diagonal = _distance(min_point, max_point)
    return min(max(diagonal * 0.18, 0.4), 1.2)


def _as_point(point: Vec3) -> dict[str, float]:
    return {"x": point[0], "y": point[1], "z": point[2]}


def _line_label(line: Line3D) -> str:
    return line.name or "".join(line.through)


def _plane_label(plane: Plane) -> str:
    return f"plane({''.join(plane.points)})"


def _intersection_warning(result: dict[str, Any]) -> str:
    if result["type"] == "line_line":
        return f"Line-line intersection {result['object_1']} and {result['object_2']}: {result['status']}."
    return f"Line-plane intersection {result['line']} and {result['plane']}: {result['status']}."


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(v: Vec3, s: float) -> Vec3:
    return (v[0] * s, v[1] * s, v[2] * s)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(v: Vec3) -> float:
    return sqrt(_dot(v, v))


def _normalize(v: Vec3) -> Vec3:
    size = _norm(v)
    if size <= EPS:
        return (0.0, 0.0, 0.0)
    return _scale(v, 1 / size)


def _distance(a: Vec3, b: Vec3) -> float:
    return _norm(_sub(a, b))


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
