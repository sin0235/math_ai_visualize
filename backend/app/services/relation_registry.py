from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RelationSupport = Literal["supported", "unsupported", "unverifiable"]
AutoFixPolicy = Literal["none", "safe", "proposal"]


@dataclass(frozen=True)
class RelationSpec:
    type: str
    verify: RelationSupport = "unsupported"
    semantic_validate: bool = True
    renderer_support: tuple[str, ...] = ("geogebra_2d", "geogebra_3d", "threejs_3d")
    auto_fix_policy: AutoFixPolicy = "none"
    aliases: tuple[str, ...] = ()


RELATION_REGISTRY: dict[str, RelationSpec] = {
    "perpendicular": RelationSpec("perpendicular", verify="supported", auto_fix_policy="proposal"),
    "parallel": RelationSpec("parallel", verify="supported", auto_fix_policy="proposal"),
    "equal_length": RelationSpec("equal_length", verify="supported", auto_fix_policy="proposal"),
    "midpoint": RelationSpec("midpoint", verify="supported", auto_fix_policy="safe"),
    "intersection": RelationSpec("intersection", verify="unsupported", auto_fix_policy="none"),
    "tangent": RelationSpec("tangent", verify="supported", auto_fix_policy="proposal"),
    "collinear": RelationSpec("collinear", verify="supported", auto_fix_policy="proposal"),
    "coplanar": RelationSpec("coplanar", verify="supported", auto_fix_policy="proposal"),
    "on_line": RelationSpec("on_line", verify="supported", auto_fix_policy="safe"),
    "on_plane": RelationSpec("on_plane", verify="supported", auto_fix_policy="proposal"),
    "on_sphere": RelationSpec("on_sphere", verify="supported", auto_fix_policy="safe"),
    "on_circle": RelationSpec("on_circle", verify="supported", auto_fix_policy="safe"),
    "distance": RelationSpec("distance", verify="supported", auto_fix_policy="none"),
    "angle": RelationSpec("angle", verify="supported", auto_fix_policy="none"),
    "point_on_segment": RelationSpec("point_on_segment", verify="supported", auto_fix_policy="safe"),
    "line_in_plane": RelationSpec("line_in_plane", verify="supported", auto_fix_policy="proposal"),
    "parallel_planes": RelationSpec("parallel_planes", verify="supported", auto_fix_policy="proposal", aliases=("parallel_plane_plane",)),
    "perpendicular_planes": RelationSpec("perpendicular_planes", verify="supported", auto_fix_policy="proposal", aliases=("perpendicular_plane_plane",)),
    "ratio": RelationSpec("ratio", verify="supported", auto_fix_policy="safe", aliases=("segment_ratio", "ratio_length")),
}

_ALIAS_TO_CANONICAL = {
    alias: relation_type
    for relation_type, spec in RELATION_REGISTRY.items()
    for alias in spec.aliases
}


def normalize_relation_type(relation_type: str | None) -> str:
    normalized = (relation_type or "").strip().lower()
    return _ALIAS_TO_CANONICAL.get(normalized, normalized)


def relation_spec(relation_type: str | None) -> RelationSpec | None:
    return RELATION_REGISTRY.get(normalize_relation_type(relation_type))


def known_relation_types() -> set[str]:
    return set(RELATION_REGISTRY) | set(_ALIAS_TO_CANONICAL)


def cas_supported_relation_types() -> set[str]:
    return {
        relation_type
        for relation_type, spec in RELATION_REGISTRY.items()
        if spec.verify == "supported"
    } | {
        alias
        for relation_type, spec in RELATION_REGISTRY.items()
        if spec.verify == "supported"
        for alias in spec.aliases
    }
