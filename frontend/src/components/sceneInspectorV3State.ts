import type { SceneObjectV3, SceneWorkspaceResponseV3 } from '../types/sceneV3';

export function relationDependenciesV3(response: SceneWorkspaceResponseV3): Map<string, string[]> {
  const dependencies = new Map<string, string[]>();
  response.scene.relations.forEach((relation) => relation.operands.forEach((operand) => {
    dependencies.set(operand.ref_id, [...(dependencies.get(operand.ref_id) ?? []), relation.id]);
  }));
  response.scene.objects.forEach((object) => objectReferenceIdsV3(object).forEach((referenceId) => {
    dependencies.set(referenceId, [...(dependencies.get(referenceId) ?? []), object.id]);
  }));
  return dependencies;
}

export function objectReferenceIdsV3(object: SceneObjectV3): string[] {
  if (object.type === 'segment' || object.type === 'line_2d' || object.type === 'line_3d' || object.type === 'face' || object.type === 'plane') return object.point_ids;
  if (object.type === 'vector_2d' || object.type === 'vector_3d') return [object.from_point_id, object.to_point_id];
  if (object.type === 'circle_2d') return [object.center_point_id, object.through_point_id].filter((id): id is string => Boolean(id));
  if (object.type === 'sphere') return [object.center_point_id];
  return [];
}