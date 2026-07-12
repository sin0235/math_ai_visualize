import type { Annotation, ThreeScene } from '../types/scene';
import type { RenderProjectionV3 } from '../types/sceneV3';

export function threeSceneFromProjectionV3(projection: RenderProjectionV3): ThreeScene {
  const linear = new Map(projection.linear.map((item) => [item.object_id, item]));
  return {
    points: Object.fromEntries(projection.points.map((point) => [
      point.object_id,
      {
        object_id: point.object_id,
        label: point.label || point.name,
        x: point.position[0],
        y: point.position[1],
        z: point.position[2],
        hidden: !point.visible,
      },
    ])),
    segments: projection.linear
      .filter((item) => item.kind === 'segment')
      .map((item) => ({
        object_id: item.object_id,
        points: item.point_ids,
        hidden: !item.visible,
        name: item.name,
        color: item.color,
        line_width: item.line_width,
        style: item.style,
      })),
    lines: projection.linear
      .filter((item) => item.kind === 'line' && item.visible)
      .map((item) => ({ through: item.point_ids, name: item.name, color: item.color || '#1d3557', extent: item.extent })),
    vectors: projection.linear
      .filter((item) => item.kind === 'vector' && item.visible)
      .map((item) => ({ from_point: item.point_ids[0], to_point: item.point_ids[1], name: item.name, color: item.color || '#7c3aed' })),
    faces: projection.surfaces
      .filter((item) => item.kind === 'face' && item.visible)
      .map((item) => ({ points: item.point_ids, name: item.name, color: item.color, opacity: item.opacity })),
    planes: projection.surfaces
      .filter((item) => item.kind === 'plane' && item.visible)
      .map((item) => ({ points: item.point_ids, name: item.name, color: item.color, opacity: item.opacity, show_normal: item.show_normal, extent: item.extent })),
    spheres: projection.spheres
      .filter((item) => item.visible)
      .map((item) => ({ center: item.center_point_id, radius: item.radius, name: item.name, color: item.color, opacity: item.opacity })),
    annotations: projection.annotations.map((annotation) => legacyAnnotation(annotation, linear)).filter((item): item is Annotation => item !== null),
    relations: [],
    bounds: projection.bounds,
    view: projection.view,
  };
}

function legacyAnnotation(
  annotation: RenderProjectionV3['annotations'][number],
  linear: Map<string, RenderProjectionV3['linear'][number]>,
): Annotation | null {
  const metadata = { ...annotation.metadata, provenance: annotation.provenance, relation_id: annotation.relation_id };
  if (annotation.type === 'coordinate_label' && annotation.target_ids.length === 1) {
    return { id: annotation.annotation_id, type: annotation.type, target: annotation.target_ids[0], label: annotation.label, color: annotation.color, metadata };
  }
  if ((annotation.type === 'length' || annotation.type === 'measurement' || annotation.type === 'equal_marks') && annotation.target_ids.length === 1) {
    const target = linear.get(annotation.target_ids[0]);
    if (!target) return null;
    return {
      id: annotation.annotation_id,
      type: annotation.type === 'measurement' ? 'length' : annotation.type,
      target: target.point_ids.join('-'),
      label: annotation.label,
      color: annotation.color,
      metadata,
    };
  }
  if ((annotation.type === 'angle' || annotation.type === 'right_angle') && annotation.target_ids.length === 3) {
    return {
      id: annotation.annotation_id,
      type: annotation.type,
      target: annotation.target_ids[1],
      label: annotation.label,
      color: annotation.color,
      metadata: { ...metadata, arms: [annotation.target_ids[0], annotation.target_ids[2]] },
    };
  }
  return null;
}