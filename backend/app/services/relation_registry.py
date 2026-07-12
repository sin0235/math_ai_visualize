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


@dataclass(frozen=True)
class RelationContractV3:
    required_kinds: tuple[tuple[str, int], ...]
    minimum_kinds: tuple[tuple[str, int], ...] = ()
    dimensions: tuple[str, ...] = ("2d", "3d")
    verifier: str = "geometry-kernel-v3"


RELATION_CONTRACTS_V3: dict[str, RelationContractV3] = {
    "perpendicular": RelationContractV3((("linear", 2),)),
    "parallel": RelationContractV3((("linear", 2),)),
    "equal_length": RelationContractV3((("linear", 2),)),
    "midpoint": RelationContractV3((("point", 1), ("linear", 1))),
    "intersection": RelationContractV3((("point", 1), ("linear", 2))),
    "tangent": RelationContractV3((), minimum_kinds=(("object", 2),)),
    "collinear": RelationContractV3((), minimum_kinds=(("point", 3),)),
    "coplanar": RelationContractV3((), minimum_kinds=(("point", 4),), dimensions=("3d",)),
    "on_line": RelationContractV3((("point", 1), ("linear", 1))),
    "on_plane": RelationContractV3((("point", 1), ("planar", 1)), dimensions=("3d",)),
    "on_sphere": RelationContractV3((("point", 1), ("sphere", 1)), dimensions=("3d",)),
    "on_circle": RelationContractV3((("point", 1), ("circle", 1)), dimensions=("2d",)),
    "distance": RelationContractV3((("point", 2),)),
    "angle": RelationContractV3((("linear", 2),)),
    "point_on_segment": RelationContractV3((("point", 1), ("segment", 1))),
    "line_in_plane": RelationContractV3((("linear", 1), ("planar", 1)), dimensions=("3d",)),
    "parallel_planes": RelationContractV3((("planar", 2),), dimensions=("3d",)),
    "perpendicular_planes": RelationContractV3((("planar", 2),), dimensions=("3d",)),
    "ratio": RelationContractV3((("linear", 2),)),
}

_KIND_GROUPS = {
    "linear": {"line", "segment", "vector"},
    "planar": {"plane", "face"},
    "object": {"point", "segment", "line", "vector", "circle", "face", "sphere", "plane", "object"},
}


def validate_v3_relation_operands(relation_type: str, operand_kinds: list[str], dimension: str) -> list[str]:
    contract = RELATION_CONTRACTS_V3.get(normalize_relation_type(relation_type))
    if contract is None:
        return [f"Relation {relation_type} chưa được đăng ký trong contract v3."]
    errors: list[str] = []
    if dimension not in contract.dimensions:
        errors.append(f"Relation {relation_type} không hỗ trợ dimension={dimension}.")
    for kind, count in contract.required_kinds:
        actual = _kind_count(operand_kinds, kind)
        if actual != count:
            errors.append(f"Relation {relation_type} cần đúng {count} operand kind={kind}, nhận {actual}.")
    for kind, minimum in contract.minimum_kinds:
        actual = _kind_count(operand_kinds, kind)
        if actual < minimum:
            errors.append(f"Relation {relation_type} cần ít nhất {minimum} operand kind={kind}, nhận {actual}.")
    return errors


def relation_v3_dependency_ids(relation) -> frozenset[str]:
    return frozenset(operand.ref_id for operand in relation.operands)


def _kind_count(operand_kinds: list[str], expected: str) -> int:
    accepted = _KIND_GROUPS.get(expected, {expected})
    return sum(kind in accepted for kind in operand_kinds)
