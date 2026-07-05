from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

TRUSTED_SOURCES = {"given", "verified", "inferred"}
TRUSTED_VERIFICATION = {"verified", "unsupported", "unverifiable", None}


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
        if self.source == "construction" and confidence not in {"verified", "exact"}:
            return False
        return self.source in TRUSTED_SOURCES or confidence in {"verified", "exact"}


@dataclass(frozen=True)
class GeometryFactGraph:
    facts: list[GeometryFact]

    def by_type(self, fact_type: str) -> list[GeometryFact]:
        return [fact for fact in self.facts if fact.type == fact_type and fact.trusted]

    def length_label(self, first: str, second: str) -> str | None:
        target = {first, second}
        for fact in self.by_type("length"):
            points = fact.args.get("points")
            if isinstance(points, tuple) and set(points) == target:
                label = fact.args.get("label")
                return str(label) if label else None
        return None


def build_geometry_fact_graph(scene: dict[str, Any]) -> GeometryFactGraph:
    facts: list[GeometryFact] = []
    for index, annotation in enumerate(scene.get("annotations") or []):
        if isinstance(annotation, dict):
            fact = _annotation_fact(annotation, index)
            if fact:
                facts.append(fact)
    for index, relation in enumerate(scene.get("relations") or []):
        if isinstance(relation, dict):
            fact = _relation_fact(relation, index)
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
    return None


def _relation_fact(relation: dict[str, Any], index: int) -> GeometryFact | None:
    metadata = relation.get("metadata") if isinstance(relation.get("metadata"), dict) else {}
    rel_type = str(relation.get("type") or "").strip().lower()
    verification = _verification_status(relation)
    if verification not in TRUSTED_VERIFICATION:
        return None

    if rel_type == "perpendicular":
        segment, plane = perpendicular_segment_plane(relation)
        if segment and plane:
            return GeometryFact(
                id=str(relation.get("id") or f"relation:{index}"),
                type="perpendicular_line_plane",
                args={"line": segment, "plane": tuple(plane)},
                source=_source_from_metadata(metadata, "verified"),
                text=f"{segment[0]}{segment[1]} vuông góc với ({''.join(plane)}).",
                verification_status=verification,
                metadata=metadata,
            )
        first = parse_edge_token(str(relation.get("object_1") or ""))
        second = parse_edge_token(str(relation.get("object_2") or ""))
        if first and second:
            return GeometryFact(
                id=str(relation.get("id") or f"relation:{index}"),
                type="perpendicular_lines",
                args={"first": first, "second": second},
                source=_source_from_metadata(metadata, "verified"),
                text=f"{first[0]}{first[1]} vuông góc với {second[0]}{second[1]}.",
                verification_status=verification,
                metadata=metadata,
            )
    if rel_type == "on_plane":
        point = str(relation.get("object_1") or "").strip()
        plane = parse_plane_token(str(relation.get("object_2") or ""))
        if point and plane:
            return GeometryFact(
                id=str(relation.get("id") or f"relation:{index}"),
                type="point_on_plane",
                args={"point": point, "plane": tuple(plane)},
                source=_source_from_metadata(metadata, "verified"),
                text=f"{point} thuộc ({''.join(plane)}).",
                verification_status=verification,
                metadata=metadata,
            )
    if rel_type == "midpoint":
        point = str(relation.get("object_1") or "").strip()
        edge = parse_edge_token(str(relation.get("object_2") or ""))
        if point and edge:
            return GeometryFact(
                id=str(relation.get("id") or f"relation:{index}"),
                type="midpoint",
                args={"point": point, "segment": edge},
                source=_source_from_metadata(metadata, "verified"),
                text=f"{point} là trung điểm của {edge[0]}{edge[1]}.",
                verification_status=verification,
                metadata=metadata,
            )
    return None


def perpendicular_segment_plane(relation: dict[str, Any]) -> tuple[tuple[str, str] | None, list[str] | None]:
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