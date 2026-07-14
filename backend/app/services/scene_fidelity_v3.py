from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from app.schemas.scene_v3 import FaceV3, MathSceneV3, Point3DV3, SegmentV3

FACE_PALETTE = ("#5da9ff", "#ffb86b", "#ffd166", "#c9a0dc", "#7fcdbb", "#a8edea")
SOLID_EDGE_COLOR = "#1d3557"
_VERTEX_RE = re.compile(r"[A-Z](?:['’′])?")
_BOX_KEYWORD_RE = re.compile(r"\b(?:hình|khối)\s+(?:lập phương|hộp(?:\s+chữ nhật)?)\b", re.IGNORECASE)
_PRISM_KEYWORD_RE = re.compile(r"\blăng\s+trụ\b", re.IGNORECASE)
_PYRAMID_KEYWORD_RE = re.compile(r"\b(?:hình|khối)\s+chóp\b", re.IGNORECASE)
_TETRAHEDRON_KEYWORD_RE = re.compile(r"\btứ\s+diện\b", re.IGNORECASE)


@dataclass(frozen=True)
class SolidTopology:
    kind: str
    vertex_labels: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]
    faces: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class FidelityIssue:
    code: str
    message: str


def repair_standard_solid_references(raw: dict[str, Any], *, problem_text: str) -> dict[str, Any]:
    """Tạo segment chuẩn bị relation tham chiếu thiếu khi mapping hai đầu mút là duy nhất."""
    topology = _detect_topology(problem_text, _raw_point_labels(raw))
    if topology is None:
        return raw
    points = _raw_point_ids_by_label(raw)
    if not _has_unique_vertices(topology, points):
        return raw

    data = dict(raw)
    objects = list(data.get("objects") or [])
    existing_ids = {str(item.get("id")) for item in objects if isinstance(item, dict) and item.get("id")}
    edge_by_ref: dict[str, tuple[str, str]] = {}
    for start, end in topology.edges:
        for ref_id in _segment_ref_ids(start, end):
            edge_by_ref[ref_id] = (start, end)

    for relation in data.get("relations") or []:
        if not isinstance(relation, dict):
            continue
        for operand in relation.get("operands") or []:
            if not isinstance(operand, dict) or operand.get("ref_kind") != "segment":
                continue
            ref_id = str(operand.get("ref_id") or "")
            edge = edge_by_ref.get(ref_id)
            if not ref_id or ref_id in existing_ids or edge is None:
                continue
            start, end = edge
            objects.append(_raw_segment(ref_id, start, end, points))
            existing_ids.add(ref_id)

    data["objects"] = objects
    return data


def repair_optional_scene_references(raw: dict[str, Any]) -> dict[str, Any]:
    """Phục hồi lỗi tham chiếu trình bày mà không làm mềm dữ kiện do đề bài cung cấp."""
    data = dict(raw)
    object_kinds = {
        str(item.get("id")): _raw_reference_kind(str(item.get("type") or ""))
        for item in data.get("objects") or []
        if isinstance(item, dict) and item.get("id")
    }
    object_ids = set(object_kinds)
    kept_relations: list[Any] = []
    removed_relation_ids: set[str] = set()
    for relation in data.get("relations") or []:
        if not isinstance(relation, dict):
            continue
        relation_id = str(relation.get("id") or "")
        source = str(relation.get("source") or "ai_inferred").strip().lower()
        can_soft_repair = source in {"ai_inferred", "construction"}
        operands = relation.get("operands")
        if not isinstance(operands, list) or not operands:
            if can_soft_repair:
                removed_relation_ids.add(relation_id)
                continue
            kept_relations.append(relation)
            continue

        missing_reference = any(
            not isinstance(operand, dict)
            or not operand.get("ref_id")
            or str(operand.get("ref_id")) not in object_ids
            for operand in operands
        )
        if missing_reference and can_soft_repair:
            removed_relation_ids.add(relation_id)
            continue

        if can_soft_repair:
            normalized_operands: list[Any] = []
            for operand in operands:
                if not isinstance(operand, dict):
                    normalized_operands.append(operand)
                    continue
                normalized = dict(operand)
                actual_kind = object_kinds.get(str(normalized.get("ref_id") or ""))
                declared_kind = str(normalized.get("ref_kind") or "")
                if actual_kind and declared_kind not in {"object", actual_kind}:
                    normalized["ref_kind"] = actual_kind
                normalized_operands.append(normalized)
            relation = {**relation, "operands": normalized_operands}
        kept_relations.append(relation)

    relation_ids = {
        str(item.get("id"))
        for item in kept_relations
        if isinstance(item, dict) and item.get("id")
    }
    kept_annotations: list[Any] = []
    for annotation in data.get("annotations") or []:
        if not isinstance(annotation, dict):
            continue
        target_ids = annotation.get("target_ids")
        if not isinstance(target_ids, list) or not target_ids:
            continue
        if any(str(target_id) not in object_ids for target_id in target_ids):
            continue
        relation_id = annotation.get("relation_id")
        if relation_id and str(relation_id) not in relation_ids:
            annotation = {key: value for key, value in annotation.items() if key != "relation_id"}
            annotation["provenance"] = "render_only"
        kept_annotations.append(annotation)

    data["relations"] = kept_relations
    data["annotations"] = kept_annotations
    interpretation = data.get("interpretation")
    if isinstance(interpretation, dict):
        interpretation["relation_ids"] = [
            relation_id
            for relation_id in interpretation.get("relation_ids") or []
            if str(relation_id) in relation_ids
        ]
    for step in data.get("construction_steps") or []:
        if isinstance(step, dict):
            step["relation_ids"] = [
                relation_id
                for relation_id in step.get("relation_ids") or []
                if str(relation_id) in relation_ids
            ]
    return data


def _raw_reference_kind(object_type: str) -> str:
    return {
        "point_2d": "point",
        "point_3d": "point",
        "segment": "segment",
        "line_2d": "line",
        "line_3d": "line",
        "vector_2d": "vector",
        "vector_3d": "vector",
        "circle_2d": "circle",
        "face": "face",
        "sphere": "sphere",
        "plane": "plane",
    }.get(object_type, "object")


def complete_standard_solid_topology(scene: MathSceneV3) -> MathSceneV3:
    topology = _detect_topology(scene.problem_text, _scene_point_labels(scene))
    if topology is None:
        return scene
    points = _scene_point_ids_by_label(scene)
    if not _has_unique_vertices(topology, points):
        return scene

    objects = _normalize_standard_solid_appearance(list(scene.objects), topology, points)
    used_ids = {obj.id for obj in objects}
    existing_edges = {
        frozenset(obj.point_ids)
        for obj in objects
        if isinstance(obj, SegmentV3)
    }
    for start, end in topology.edges:
        endpoints = (points[start], points[end])
        key = frozenset(endpoints)
        if key in existing_edges:
            continue
        objects.append(SegmentV3(
            id=_unique_id(_preferred_segment_id(start, end), used_ids),
            label=f"{start}{end}",
            point_ids=endpoints,
            hidden=False,
            color=SOLID_EDGE_COLOR,
            line_width=2.8,
            style="solid",
            source="construction",
            metadata={"topology_rule": topology.kind},
        ))
        existing_edges.add(key)

    existing_faces = {
        frozenset(obj.point_ids)
        for obj in objects
        if isinstance(obj, FaceV3)
    }
    for index, labels in enumerate(topology.faces):
        point_ids = [points[label] for label in labels]
        key = frozenset(point_ids)
        if key in existing_faces:
            continue
        objects.append(FaceV3(
            id=_unique_id(_preferred_face_id(labels), used_ids),
            label="".join(labels),
            point_ids=point_ids,
            color=FACE_PALETTE[index % len(FACE_PALETTE)],
            opacity=0.22,
            source="construction",
            metadata={"topology_rule": topology.kind},
        ))
        existing_faces.add(key)

    return scene.model_copy(update={"objects": _spread_ai_face_colors(objects)})


def _normalize_standard_solid_appearance(
    objects: list[Any],
    topology: SolidTopology,
    points: dict[str, str],
) -> list[Any]:
    edge_keys = {
        frozenset((points[start], points[end]))
        for start, end in topology.edges
    }
    face_palette = {
        frozenset(points[label] for label in labels): FACE_PALETTE[index % len(FACE_PALETTE)]
        for index, labels in enumerate(topology.faces)
    }
    normalized: list[Any] = []
    for obj in objects:
        if _style_is_user_owned(obj):
            normalized.append(obj)
            continue
        if isinstance(obj, SegmentV3) and frozenset(obj.point_ids) in edge_keys:
            normalized.append(obj.model_copy(update={
                "hidden": False,
                "color": SOLID_EDGE_COLOR,
                "line_width": 2.8,
                "style": "solid",
            }))
            continue
        if isinstance(obj, FaceV3):
            color = face_palette.get(frozenset(obj.point_ids))
            if color is not None and obj.metadata.get("role") not in {"section", "cross_section"}:
                normalized.append(obj.model_copy(update={"color": color, "opacity": 0.22}))
                continue
        normalized.append(obj)
    return normalized


def _style_is_user_owned(obj: Any) -> bool:
    return bool(
        getattr(obj, "locked", False)
        or getattr(obj, "user_edited", False)
        or getattr(obj, "source", None) in {"user_created", "user_edited"}
    )


def validate_scene_fidelity(scene: MathSceneV3) -> tuple[FidelityIssue, ...]:
    keyword_kind = _solid_keyword_kind(scene.problem_text)
    if keyword_kind is None:
        return ()
    topology = _detect_topology(scene.problem_text, _scene_point_labels(scene))
    if topology is None:
        return (FidelityIssue(
            "SOLID_TOPOLOGY_AMBIGUOUS",
            "Đề yêu cầu khối chuẩn nhưng không xác định duy nhất được ký hiệu các đỉnh.",
        ),)
    if scene.view.dimension != "3d":
        return (FidelityIssue(
            "SOLID_DIMENSION_INVALID",
            "Khối không gian phải dùng view.dimension='3d'.",
        ),)

    points = _scene_point_ids_by_label(scene)
    missing_vertices = [label for label in topology.vertex_labels if label not in points]
    if missing_vertices:
        return (FidelityIssue(
            "SOLID_VERTICES_INCOMPLETE",
            f"Khối {topology.kind} thiếu đỉnh: {missing_vertices}.",
        ),)

    expected_edges = {frozenset((points[start], points[end])) for start, end in topology.edges}
    actual_edges = {
        frozenset(obj.point_ids)
        for obj in scene.objects
        if isinstance(obj, SegmentV3)
    }
    expected_faces = {frozenset(points[label] for label in labels) for labels in topology.faces}
    actual_faces = {
        frozenset(obj.point_ids)
        for obj in scene.objects
        if isinstance(obj, FaceV3)
    }
    issues: list[FidelityIssue] = []
    missing_edges = expected_edges - actual_edges
    missing_faces = expected_faces - actual_faces
    if missing_edges or missing_faces:
        issues.append(FidelityIssue(
            "SOLID_TOPOLOGY_INCOMPLETE",
            f"Khối {topology.kind} còn thiếu {len(missing_edges)} cạnh và {len(missing_faces)} mặt.",
        ))

    face_colors = {
        obj.color.lower()
        for obj in scene.objects
        if isinstance(obj, FaceV3) and frozenset(obj.point_ids) in expected_faces
    }
    if len(topology.faces) > 1 and len(face_colors) < 2:
        issues.append(FidelityIssue(
            "SOLID_APPEARANCE_INCOMPLETE",
            f"Các mặt của khối {topology.kind} chưa có màu phân biệt.",
        ))
    return tuple(issues)


def _detect_topology(problem_text: str, point_labels: Iterable[str]) -> SolidTopology | None:
    labels = {_normalize_label(label) for label in point_labels if label}
    if _BOX_KEYWORD_RE.search(problem_text):
        bases = _extract_two_bases(problem_text)
        if bases is None:
            bases = _canonical_two_bases(labels, minimum_size=4, maximum_size=4)
        if bases is not None:
            return _prism_topology("box", *bases)
    if _PRISM_KEYWORD_RE.search(problem_text):
        bases = _extract_two_bases(problem_text)
        if bases is None:
            bases = _canonical_two_bases(labels, minimum_size=3, maximum_size=4)
        if bases is not None:
            return _prism_topology("prism", *bases)
    if _PYRAMID_KEYWORD_RE.search(problem_text):
        parts = _extract_dot_notation(problem_text)
        if parts is not None and len(parts[0]) == 1 and len(parts[1]) >= 3:
            return _pyramid_topology(parts[0][0], parts[1])
        inferred_base = tuple(label for label in ("A", "B", "C", "D") if label in labels)
        if "S" in labels and len(inferred_base) >= 3:
            return _pyramid_topology("S", inferred_base)
    if _TETRAHEDRON_KEYWORD_RE.search(problem_text):
        vertices = _extract_vertices_after_keyword(problem_text, _TETRAHEDRON_KEYWORD_RE)
        if len(vertices) != 4 and {"A", "B", "C", "D"}.issubset(labels):
            vertices = ("A", "B", "C", "D")
        if len(vertices) == 4:
            return _tetrahedron_topology(vertices)
    return None


def _prism_topology(kind: str, lower: tuple[str, ...], upper: tuple[str, ...]) -> SolidTopology:
    count = len(lower)
    edges = tuple(
        [(lower[i], lower[(i + 1) % count]) for i in range(count)]
        + [(upper[i], upper[(i + 1) % count]) for i in range(count)]
        + [(lower[i], upper[i]) for i in range(count)]
    )
    faces = (lower, upper, *tuple(
        (lower[i], lower[(i + 1) % count], upper[(i + 1) % count], upper[i])
        for i in range(count)
    ))
    return SolidTopology(kind, (*lower, *upper), edges, faces)


def _pyramid_topology(apex: str, base: tuple[str, ...]) -> SolidTopology:
    count = len(base)
    edges = tuple(
        [(base[i], base[(i + 1) % count]) for i in range(count)]
        + [(apex, label) for label in base]
    )
    faces = (base, *tuple((apex, base[i], base[(i + 1) % count]) for i in range(count)))
    return SolidTopology("pyramid", (apex, *base), edges, faces)


def _tetrahedron_topology(vertices: tuple[str, ...]) -> SolidTopology:
    a, b, c, d = vertices
    return SolidTopology(
        "tetrahedron",
        vertices,
        ((a, b), (a, c), (a, d), (b, c), (b, d), (c, d)),
        ((a, b, c), (a, b, d), (a, c, d), (b, c, d)),
    )


def _extract_two_bases(text: str) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    parts = _extract_dot_notation(text)
    if parts is None or len(parts[0]) != len(parts[1]) or len(parts[0]) < 3:
        return None
    return parts


def _extract_dot_notation(text: str) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    match = re.search(r"([A-Z](?:['’′])?(?:[A-Z](?:['’′])?){0,7})\s*[.]\s*([A-Z](?:['’′])?(?:[A-Z](?:['’′])?){2,7})", text)
    if not match:
        return None
    return _vertex_sequence(match.group(1)), _vertex_sequence(match.group(2))


def _extract_vertices_after_keyword(text: str, keyword: re.Pattern[str]) -> tuple[str, ...]:
    match = keyword.search(text)
    if not match:
        return ()
    tail = text[match.end():match.end() + 32]
    sequence = re.search(r"([A-Z](?:['’′])?(?:[A-Z](?:['’′])?){2,7})", tail)
    return _vertex_sequence(sequence.group(1)) if sequence else ()


def _canonical_two_bases(
    labels: set[str],
    *,
    minimum_size: int,
    maximum_size: int,
) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    for count in range(maximum_size, minimum_size - 1, -1):
        lower = tuple(chr(ord("A") + index) for index in range(count))
        prime_upper = tuple(f"{label}'" for label in lower)
        if set((*lower, *prime_upper)).issubset(labels):
            return lower, prime_upper
        upper = tuple(chr(ord("A") + count + index) for index in range(count))
        if set((*lower, *upper)).issubset(labels):
            return lower, upper
    return None


def _solid_keyword_kind(problem_text: str) -> str | None:
    for kind, pattern in (
        ("box", _BOX_KEYWORD_RE),
        ("prism", _PRISM_KEYWORD_RE),
        ("pyramid", _PYRAMID_KEYWORD_RE),
        ("tetrahedron", _TETRAHEDRON_KEYWORD_RE),
    ):
        if pattern.search(problem_text):
            return kind
    return None


def _raw_point_labels(raw: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(item.get("label") or "")
        for item in raw.get("objects") or []
        if isinstance(item, dict) and item.get("type") == "point_3d"
    )


def _raw_point_ids_by_label(raw: dict[str, Any]) -> dict[str, str]:
    pairs = [
        (_normalize_label(str(item.get("label") or "")), str(item.get("id") or ""))
        for item in raw.get("objects") or []
        if isinstance(item, dict) and item.get("type") == "point_3d"
    ]
    return _unique_label_map(pairs)


def _scene_point_labels(scene: MathSceneV3) -> tuple[str, ...]:
    return tuple(obj.label or "" for obj in scene.objects if isinstance(obj, Point3DV3))


def _scene_point_ids_by_label(scene: MathSceneV3) -> dict[str, str]:
    return _unique_label_map(
        (_normalize_label(obj.label or ""), obj.id)
        for obj in scene.objects
        if isinstance(obj, Point3DV3)
    )


def _unique_label_map(pairs: Iterable[tuple[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    duplicates: set[str] = set()
    for label, object_id in pairs:
        if not label or not object_id:
            continue
        if label in result:
            duplicates.add(label)
        else:
            result[label] = object_id
    for label in duplicates:
        result.pop(label, None)
    return result


def _has_unique_vertices(topology: SolidTopology, points: dict[str, str]) -> bool:
    return all(label in points for label in topology.vertex_labels)


def _spread_ai_face_colors(objects: list[Any]) -> list[Any]:
    faces = [
        obj
        for obj in objects
        if isinstance(obj, FaceV3)
        and obj.source in {"ai_inferred", "construction"}
        and not obj.locked
        and not obj.user_edited
    ]
    if len(faces) < 2 or len({face.color.lower() for face in faces}) > 1:
        return objects
    recolored = {
        face.id: face.model_copy(update={"color": FACE_PALETTE[index % len(FACE_PALETTE)]})
        for index, face in enumerate(faces)
    }
    return [recolored.get(obj.id, obj) for obj in objects]


def _raw_segment(ref_id: str, start: str, end: str, points: dict[str, str]) -> dict[str, Any]:
    return {
        "id": ref_id,
        "type": "segment",
        "label": f"{start}{end}",
        "point_ids": [points[start], points[end]],
        "hidden": False,
        "color": SOLID_EDGE_COLOR,
        "line_width": 2,
        "style": "solid",
        "source": "construction",
        "metadata": {"topology_rule": "missing_relation_segment"},
    }


def _segment_ref_ids(start: str, end: str) -> tuple[str, ...]:
    first, second = _label_slug(start), _label_slug(end)
    return (
        f"seg_{first}{second}",
        f"seg_{second}{first}",
        f"seg_{first}_{second}",
        f"seg_{second}_{first}",
    )


def _preferred_segment_id(start: str, end: str) -> str:
    return f"seg_{_label_slug(start)}{_label_slug(end)}"


def _preferred_face_id(labels: tuple[str, ...]) -> str:
    return "face_" + "".join(_label_slug(label) for label in labels)


def _unique_id(preferred: str, used_ids: set[str]) -> str:
    if preferred not in used_ids:
        used_ids.add(preferred)
        return preferred
    suffix = 2
    while f"{preferred}_{suffix}" in used_ids:
        suffix += 1
    result = f"{preferred}_{suffix}"
    used_ids.add(result)
    return result


def _vertex_sequence(value: str) -> tuple[str, ...]:
    return tuple(_normalize_label(match.group(0)) for match in _VERTEX_RE.finditer(value))


def _normalize_label(value: str) -> str:
    return value.strip().upper().replace("’", "'").replace("′", "'")


def _label_slug(label: str) -> str:
    return _normalize_label(label).lower().replace("'", "_prime")
