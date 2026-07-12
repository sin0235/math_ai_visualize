from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.schemas.scene_v3 import MathSceneV3, object_reference_ids
from app.services.relation_registry import relation_v3_dependency_ids


@dataclass(frozen=True)
class ConstraintGraph:
    relation_dependencies: Mapping[str, frozenset[str]]
    object_relations: Mapping[str, frozenset[str]]

    def affected_relations(self, changed_object_ids: set[str] | frozenset[str]) -> frozenset[str]:
        return frozenset(
            relation_id
            for object_id in changed_object_ids
            for relation_id in self.object_relations.get(object_id, ())
        )


def build_constraint_graph(scene: MathSceneV3) -> ConstraintGraph:
    objects = {obj.id: obj for obj in scene.objects}
    relation_dependencies = {}
    for relation in scene.relations:
        direct = relation_v3_dependency_ids(relation)
        nested = {
            nested_id
            for object_id in direct
            if (obj := objects.get(object_id)) is not None
            for nested_id in object_reference_ids(obj)
        }
        relation_dependencies[relation.id] = direct | nested
    object_relations: dict[str, set[str]] = {}
    for relation_id, object_ids in relation_dependencies.items():
        for object_id in object_ids:
            object_relations.setdefault(object_id, set()).add(relation_id)
    return ConstraintGraph(
        relation_dependencies=MappingProxyType(relation_dependencies),
        object_relations=MappingProxyType({key: frozenset(value) for key, value in object_relations.items()}),
    )