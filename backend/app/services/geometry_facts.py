from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.relation_registry import normalize_relation_type

REJECTED_VERIFICATION = {"failed", "error"}


@dataclass(frozen=True)
class GeometryFact:
    id: str
    type: str
    args: dict[str, Any]
    source: str
    text: str
    verification_status: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def trusted(self) -> bool:
        confidence = str(self.metadata.get("confidence") or "").lower()
        if self.verification_status in REJECTED_VERIFICATION:
            return False
        if self.source == "construction":
            return confidence in {"verified", "exact"}
        if self.source == "given":
            return True
        if self.verification_status == "verified":
            return True
        if self.source == "inferred":
            return confidence in {"verified", "exact"} or (
                confidence == "partial" and bool(str(self.metadata.get("evidence") or "").strip())
            )
        return self.source == "verified"


@dataclass(frozen=True)
class GeometryFactGraph:
    facts: list[GeometryFact]

    def by_type(self, fact_type: str) -> list[GeometryFact]:
        return [fact for fact in self.facts if fact.type == fact_type and fact.trusted]

    def length_label(self, first: str, second: str) -> str | None:
        fact = self.length_fact(first, second)
        if fact is None:
            return None
        label = fact.args.get("label")
        return str(label) if label else None

    def length_fact(self, first: str, second: str) -> GeometryFact | None:
        target = {first, second}
        for fact in self.by_type("length"):
            points = fact.args.get("points")
            if isinstance(points, tuple) and set(points) == target:
                return fact
        return None

    def length_facts_for(self, points: list[str] | tuple[str, ...]) -> list[GeometryFact]:
        target = set(points)
        return [
            fact
            for fact in self.by_type("length")
            if isinstance(fact.args.get("points"), tuple)
            and set(fact.args["points"]).issubset(target)
        ]


def build_geometry_fact_graph(scene: dict[str, Any]) -> GeometryFactGraph:
    facts: list[GeometryFact] = []
    object_index = _object_index(scene)
    facts.extend(_problem_structure_facts(scene))
    facts.extend(_problem_midpoint_facts(scene))
    for index, annotation in enumerate(scene.get("annotations") or []):
        if isinstance(annotation, dict):
            fact = _annotation_fact(annotation, index)
            if fact:
                facts.append(fact)
    for index, relation in enumerate(scene.get("relations") or []):
        if isinstance(relation, dict):
            fact = _relation_fact(relation, index, object_index)
            if fact:
                facts.append(fact)
    for index, derived in enumerate(scene.get("derived_facts") or []):
        if isinstance(derived, dict):
            fact = _derived_fact(derived, index)
            if fact:
                facts.append(fact)
    for index, obj in enumerate(scene.get("objects") or []):
        if isinstance(obj, dict) and obj.get("type") in {"face", "plane"}:
            points = _point_list(obj.get("points"))
            if len(points) >= 3:
                facts.append(GeometryFact(
                    id=f"object:{index}:plane",
                    type="plane_points",
                    args={"plane": tuple(points)},
                    source=_source_from_metadata(obj.get("metadata"), "verified"),
                    text=f"Các điểm {', '.join(points)} cùng thuộc một mặt phẳng.",
                    metadata=obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {},
                ))
    return GeometryFactGraph(facts)


def _problem_structure_facts(scene: dict[str, Any]) -> list[GeometryFact]:
    """Chuẩn hóa cấu trúc khối được nêu trực tiếp trong đề, không đọc tọa độ render."""
    text = str(scene.get("problem_text") or "")
    signature = re.search(
        r"(?:hình|hinh)\s+(?:lập|lap)\s+(?:phương|phuong)\s*\(?\s*([A-Za-z]{4})\s*\.\s*([A-Za-z]{4})\s*\)?",
        text,
        flags=re.IGNORECASE,
    )
    structure = "cube"
    if signature is None:
        signature = re.search(
            r"(?:(?:hình|hinh)\s+)?(?:hộp|hop)\s+(?:chữ|chu)\s+(?:nhật|nhat)\s*\(?\s*([A-Za-z]{4})\s*\.\s*([A-Za-z]{4})\s*\)?",
            text,
            flags=re.IGNORECASE,
        )
        structure = "rectangular_cuboid"
    if signature is None:
        return []
    base = tuple(signature.group(1).upper())
    top = tuple(signature.group(2).upper())
    if structure == "cube":
        side_match = re.search(
            r"(?:cạnh|canh)(?:\s+(?:có|co)\s+(?:độ|do)\s+(?:dài|dai))?\s*(?:(?:bằng|bang)|=)?\s*\(?\s*(\d+(?:[.,]\d+)?)\s*\)?",
            text,
            flags=re.IGNORECASE,
        )
        side = side_match.group(1).replace(",", ".") if side_match is not None else None
        axis_lengths = (side, side, side) if side is not None else ()
    else:
        axis_edges = ((base[0], base[1]), (base[0], base[3]), (base[0], top[0]))
        parsed_lengths = tuple(_problem_edge_length(scene, edge) for edge in axis_edges)
        axis_lengths = parsed_lengths if all(parsed_lengths) else ()
    structure_name = "hình lập phương" if structure == "cube" else "hình hộp chữ nhật"
    return [GeometryFact(
        id=f"problem:orthogonal-frame:{''.join(base)}:{''.join(top)}",
        type="orthogonal_frame",
        args={
            "base": base,
            "top": top,
            "axis_lengths": axis_lengths,
            "structure": structure,
        },
        source="given",
        text=(
            f"{''.join(base)}.{''.join(top)} là {structure_name} có ba phương cạnh đôi một vuông góc"
            + (f" với độ dài {', '.join(axis_lengths)}." if axis_lengths else ".")
        ),
        metadata={"source": "given", "evidence": signature.group(0)},
    )]


def _problem_edge_length(scene: dict[str, Any], edge: tuple[str, str]) -> str | None:
    target = set(edge)
    for annotation in scene.get("annotations") or []:
        if not isinstance(annotation, dict) or annotation.get("type") != "length":
            continue
        annotated_edge = parse_edge_token(str(annotation.get("target") or ""))
        label = annotation.get("label")
        if annotated_edge and set(annotated_edge) == target and isinstance(label, str) and label.strip():
            return label.strip().replace(",", ".")
    text = str(scene.get("problem_text") or "")
    edge_name = "".join(edge)
    match = re.search(
        rf"\b{re.escape(edge_name)}\s*(?:(?:bằng|bang)|=)\s*\(?\s*(\d+(?:[.,]\d+)?)\s*\)?",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).replace(",", ".") if match is not None else None


def _problem_midpoint_facts(scene: dict[str, Any]) -> list[GeometryFact]:
    """Lấy premise trung điểm được phát biểu rõ trong đề, độc lập với relation do renderer sinh."""
    text = str(scene.get("problem_text") or "")
    pattern = re.compile(
        r"(?:gọi|goi)?\s*\(?\s*([A-Za-z])\s*\)?\s+(?:là|la)\s+trung\s+(?:điểm|diem)"
        r"(?:\s+(?:của|cua))?\s*(?:(?:đoạn|doan)\s+(?:thẳng|thang))?\s*\(?\s*([A-Za-z])\s*-?\s*([A-Za-z])\s*\)?",
        flags=re.IGNORECASE,
    )
    facts: list[GeometryFact] = []
    for match in pattern.finditer(text):
        point, first, second = (group.upper() for group in match.groups())
        facts.append(GeometryFact(
            id=f"problem:midpoint:{point}:{first}{second}",
            type="midpoint",
            args={"point": point, "segment": (first, second)},
            source="given",
            text=f"{point} là trung điểm của {first}{second}.",
            metadata={"source": "given", "evidence": match.group(0)},
        ))
    return facts


def _annotation_fact(annotation: dict[str, Any], index: int) -> GeometryFact | None:
    metadata = annotation.get("metadata") if isinstance(annotation.get("metadata"), dict) else {}
    if annotation.get("type") == "length":
        edge = parse_edge_token(str(annotation.get("target") or ""))
        label = annotation.get("label")
        if edge and isinstance(label, str) and label.strip():
            first, second = edge
            return GeometryFact(
                id=str(annotation.get("id") or f"annotation:{index}"),
                type="length",
                args={"points": edge, "label": label.strip()},
                source=_source_from_metadata(metadata, "given"),
                text=f"{first}{second} = {label.strip()}",
                metadata=metadata,
            )
    if annotation.get("type") == "measure":
        name = str(annotation.get("target") or metadata.get("name") or "").strip().lower()
        label = annotation.get("label")
        if name and isinstance(label, str) and label.strip():
            return GeometryFact(
                id=str(annotation.get("id") or f"annotation:{index}"),
                type="scalar_measure",
                args={"name": name, "label": label.strip()},
                source=_source_from_metadata(metadata, "given"),
                text=f"{name} = {label.strip()}",
                metadata=metadata,
            )
    if annotation.get("type") == "angle":
        vertex = str(annotation.get("target") or "").strip().upper()
        arms = _point_list(metadata.get("arms"))
        label = annotation.get("label")
        if vertex and len(arms) == 2 and vertex not in arms and isinstance(label, str) and label.strip():
            return GeometryFact(
                id=str(annotation.get("id") or f"annotation:{index}"),
                type="angle_measure",
                args={"vertex": vertex, "arms": tuple(arms), "label": label.strip()},
                source=_source_from_metadata(metadata, "given"),
                text=f"Góc {arms[0]}{vertex}{arms[1]} = {label.strip()}",
                metadata=metadata,
            )
    if annotation.get("type") == "right_angle":
        vertex = str(annotation.get("target") or "").strip().upper()
        arms = _point_list(metadata.get("arms"))
        if vertex and len(arms) == 2 and vertex not in arms:
            return GeometryFact(
                id=str(annotation.get("id") or f"annotation:{index}"),
                type="right_angle",
                args={"vertex": vertex, "arms": tuple(arms)},
                source=_source_from_metadata(metadata, str(annotation.get("source") or "given")),
                text=f"Góc {arms[0]}{vertex}{arms[1]} vuông.",
                metadata=metadata,
            )
    return None


def _derived_fact(derived: dict[str, Any], index: int) -> GeometryFact | None:
    kind = str(derived.get("kind") or "").strip()
    provenance = str(derived.get("provenance") or "").strip().lower()
    if not kind or provenance == "render_only":
        return None
    value = derived.get("value") if isinstance(derived.get("value"), dict) else {}
    source_ids = tuple(str(item) for item in derived.get("source_ids") or [] if str(item))
    return GeometryFact(
        id=str(derived.get("id") or f"derived:{index}"),
        type=f"derived_{kind}",
        args={"source_ids": source_ids, **value},
        source="verified" if provenance == "verified" else "inferred",
        text=str(value.get("text") or f"Dữ kiện {kind} được suy ra từ scene."),
        verification_status="verified" if provenance == "verified" else None,
        metadata={"provenance": provenance, "relation_id": derived.get("relation_id")},
    )


def _object_index(scene: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for obj in scene.get("objects") or []:
        if not isinstance(obj, dict):
            continue
        for key in (obj.get("object_id"), obj.get("id"), obj.get("name")):
            if key:
                index[str(key)] = obj
    return index


def _relation_fact(
    relation: dict[str, Any],
    index: int,
    object_index: dict[str, dict[str, Any]] | None = None,
) -> GeometryFact | None:
    object_index = object_index or {}
    metadata = relation.get("metadata") if isinstance(relation.get("metadata"), dict) else {}
    rel_type = normalize_relation_type(str(relation.get("type") or ""))
    verification = _verification_status(relation)
    if verification in REJECTED_VERIFICATION:
        return None
    source = _source_from_metadata(metadata, str(relation.get("source") or "verified"))
    tokens = _relation_tokens(relation, object_index)

    if rel_type == "perpendicular":
        segment, plane = perpendicular_segment_plane(relation, object_index)
        if segment and plane:
            return GeometryFact(
                id=str(relation.get("id") or f"relation:{index}"),
                type="perpendicular_line_plane",
                args={"line": segment, "plane": tuple(plane)},
                source=source,
                text=f"{segment[0]}{segment[1]} vuông góc với ({''.join(plane)}).",
                verification_status=verification,
                metadata=metadata,
            )
        edges = [parse_edge_token(token) for token in tokens[:2]]
        if edges[0] and edges[1] if len(edges) >= 2 else False:
            first, second = edges[0], edges[1]
            return GeometryFact(
                id=str(relation.get("id") or f"relation:{index}"),
                type="perpendicular_lines",
                args={"first": first, "second": second},
                source=source,
                text=f"{first[0]}{first[1]} vuông góc với {second[0]}{second[1]}.",
                verification_status=verification,
                metadata=metadata,
            )
    if rel_type == "on_plane":
        point = tokens[0] if tokens else str(relation.get("object_1") or "").strip()
        plane = parse_plane_token(tokens[1] if len(tokens) > 1 else str(relation.get("object_2") or ""))
        # Typed operands: point name + plane expanded token
        if point and "-" not in point and plane:
            return GeometryFact(
                id=str(relation.get("id") or f"relation:{index}"),
                type="point_on_plane",
                args={"point": point, "plane": tuple(plane)},
                source=source,
                text=f"{point} thuộc ({''.join(plane)}).",
                verification_status=verification,
                metadata=metadata,
            )
    if rel_type == "midpoint":
        point = tokens[0] if tokens else str(relation.get("object_1") or "").strip()
        edge = parse_edge_token(tokens[1] if len(tokens) > 1 else str(relation.get("object_2") or ""))
        if point and edge:
            return GeometryFact(
                id=str(relation.get("id") or f"relation:{index}"),
                type="midpoint",
                args={"point": point, "segment": edge},
                source=source,
                text=f"{point} là trung điểm của {edge[0]}{edge[1]}.",
                verification_status=verification,
                metadata=metadata,
            )
    if rel_type == "intersection":
        names = tuple(tokens or [str(item) for item in relation.get("operand_names") or [] if str(item)])
        if len(names) >= 3:
            return GeometryFact(
                id=str(relation.get("id") or f"relation:{index}"),
                type="intersection",
                args={"point": names[0], "objects": names[1:]},
                source=source,
                text=f"{names[0]} là giao điểm của {names[1]} và {names[2]}.",
                verification_status=verification,
                metadata=metadata,
            )
    if rel_type == "parallel":
        edges = [parse_edge_token(token) for token in tokens[:2]]
        if len(edges) >= 2 and edges[0] and edges[1]:
            first, second = edges[0], edges[1]
            return GeometryFact(
                id=str(relation.get("id") or f"relation:{index}"),
                type="parallel_lines",
                args={"first": first, "second": second},
                source=source,
                text=f"{first[0]}{first[1]} song song với {second[0]}{second[1]}.",
                verification_status=verification,
                metadata=metadata,
            )
    if rel_type in {"collinear", "coplanar"}:
        names = tuple(tokens or [str(item) for item in relation.get("operand_names") or [] if str(item)])
        minimum = 3 if rel_type == "collinear" else 4
        if len(names) >= minimum:
            description = "thẳng hàng" if rel_type == "collinear" else "đồng phẳng"
            return GeometryFact(
                id=str(relation.get("id") or f"relation:{index}"),
                type=rel_type,
                args={"points": names},
                source=source,
                text=f"Các điểm {', '.join(names)} {description}.",
                verification_status=verification,
                metadata=metadata,
            )
    if rel_type == "equal_length":
        edges = [parse_edge_token(token) for token in tokens[:2]]
        if len(edges) >= 2 and edges[0] and edges[1]:
            first, second = edges[0], edges[1]
            return GeometryFact(
                id=str(relation.get("id") or f"relation:{index}"),
                type="equal_length",
                args={"first": first, "second": second},
                source=source,
                text=f"{first[0]}{first[1]} = {second[0]}{second[1]}.",
                verification_status=verification,
                metadata=metadata,
            )
    if rel_type == "distance":
        value = (relation.get("args") or {}).get("value") if isinstance(relation.get("args"), dict) else None
        if value is None:
            value = metadata.get("value") or metadata.get("length")
        edge = parse_edge_token(tokens[0]) if tokens else None
        if edge is None and len(tokens) >= 2:
            edge = (tokens[0], tokens[1])
        if edge and value is not None:
            return GeometryFact(
                id=str(relation.get("id") or f"relation:{index}"),
                type="length",
                args={"points": edge, "label": str(value), "value": value},
                source=source,
                text=f"{edge[0]}{edge[1]} = {value}.",
                verification_status=verification,
                metadata=metadata,
            )
    return None


def _relation_tokens(relation: dict[str, Any], object_index: dict[str, dict[str, Any]]) -> list[str]:
    """Prefer classical tokens (object_1/2), then operand_names, then expand typed operands."""
    tokens: list[str] = []
    for key in ("object_1", "object_2"):
        value = relation.get(key)
        if value:
            tokens.append(str(value))
    if tokens:
        return tokens
    names = [str(item) for item in relation.get("operand_names") or [] if str(item)]
    if names:
        return names
    for operand in relation.get("operands") or []:
        if not isinstance(operand, dict):
            continue
        ref_id = str(operand.get("ref_id") or "")
        obj = object_index.get(ref_id)
        if obj is None:
            if ref_id:
                tokens.append(ref_id)
            continue
        name = str(obj.get("name") or obj.get("label") or ref_id)
        obj_type = str(obj.get("type") or "")
        if obj_type in {"segment", "line_2d", "line_3d"}:
            pts = obj.get("points") or obj.get("through") or obj.get("point_ids") or []
            if isinstance(pts, list) and len(pts) >= 2:
                a = str(pts[0])
                b = str(pts[1])
                # Expand point_ids through object_index to labels when available.
                a_obj = object_index.get(a)
                b_obj = object_index.get(b)
                if a_obj and a_obj.get("type") in {"point_2d", "point_3d"}:
                    a = str(a_obj.get("name") or a_obj.get("label") or a)
                if b_obj and b_obj.get("type") in {"point_2d", "point_3d"}:
                    b = str(b_obj.get("name") or b_obj.get("label") or b)
                tokens.append(f"{a}-{b}")
                continue
        if obj_type in {"face", "plane"}:
            pts = obj.get("points") or obj.get("point_ids") or []
            if isinstance(pts, list) and len(pts) >= 3:
                labels = []
                for pid in pts:
                    pobj = object_index.get(str(pid))
                    if pobj and pobj.get("type") in {"point_2d", "point_3d"}:
                        labels.append(str(pobj.get("name") or pobj.get("label") or pid))
                    else:
                        labels.append(str(pid))
                tokens.append(f"plane({''.join(labels)})")
                continue
        tokens.append(name)
    return tokens


def perpendicular_segment_plane(
    relation: dict[str, Any],
    object_index: dict[str, dict[str, Any]] | None = None,
) -> tuple[tuple[str, str] | None, list[str] | None]:
    tokens = _relation_tokens(relation, object_index or {})
    if len(tokens) >= 2:
        segment = parse_edge_token(tokens[0])
        plane = parse_plane_token(tokens[1])
        if segment and plane:
            return segment, plane
        segment = parse_edge_token(tokens[1])
        plane = parse_plane_token(tokens[0])
        if segment and plane:
            return segment, plane
    object_1 = str(relation.get("object_1") or "")
    object_2 = str(relation.get("object_2") or "")
    segment = parse_edge_token(object_1)
    plane = parse_plane_token(object_2)
    if segment and plane:
        return segment, plane
    segment = parse_edge_token(object_2)
    plane = parse_plane_token(object_1)
    return segment, plane


def point_on_plane(graph: GeometryFactGraph, point: str, plane: tuple[str, ...]) -> bool:
    if point in set(plane):
        return True
    for fact in graph.by_type("point_on_plane"):
        if fact.args.get("point") == point and set(fact.args.get("plane") or ()) == set(plane):
            return True
    for fact in graph.by_type("plane_points"):
        if point in set(fact.args.get("plane") or ()) and set(plane).issubset(set(fact.args.get("plane") or ())):
            return True
    return False


def parse_edge_token(value: str | None) -> tuple[str, str] | None:
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


def parse_plane_token(value: str | None) -> list[str] | None:
    if not value:
        return None
    cleaned = value.strip()
    match = re.fullmatch(r"(?:plane|mp)?\(?([A-Za-z0-9'\s]+)\)?", cleaned, flags=re.IGNORECASE)
    if cleaned.startswith("(") and cleaned.endswith(")"):
        inside = cleaned[1:-1]
    elif cleaned.lower().startswith("plane(") and cleaned.endswith(")"):
        inside = cleaned[6:-1]
    elif match and len(_point_list(match.group(1))) >= 3:
        inside = match.group(1)
    else:
        return None
    points = _point_list(inside)
    return points if len(points) >= 3 else None


def _point_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip().upper() for item in value if str(item).strip()]
    return [match.group(0).upper() for match in re.finditer(r"[A-Za-z](?:[0-9]+|')?", str(value or ""))]


def _source_from_metadata(metadata: Any, default: str) -> str:
    if not isinstance(metadata, dict):
        return default
    raw = str(metadata.get("source") or metadata.get("origin") or default).lower()
    if raw == "ai_inferred":
        return "inferred"
    return raw


def _verification_status(relation: dict[str, Any]) -> str | None:
    verification = relation.get("verification")
    if isinstance(verification, dict):
        status = verification.get("status")
        return str(status).lower() if status else None
    return None
