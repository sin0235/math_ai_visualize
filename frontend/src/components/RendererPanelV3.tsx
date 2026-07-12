import { lazy, Suspense, useMemo } from 'react';

import type { MathScene } from '../types/scene';
import type { MathSceneV3, SceneWorkspaceResponseV3 } from '../types/sceneV3';
import { threeSceneFromProjectionV3 } from '../utils/renderProjectionV3';
import { GeoGebraView } from './GeoGebraView';
import type { ThreeSceneImageCapture, ThreeSceneInteraction } from './ThreeGeometryView';

const ThreeGeometryView = lazy(() => import('./ThreeGeometryView').then((module) => ({ default: module.ThreeGeometryView })));

type Vec3 = { x: number; y: number; z: number };

interface RendererPanelV3Props {
  response: SceneWorkspaceResponseV3 | null;
  previewScene?: MathSceneV3 | null;
  interaction?: ThreeSceneInteraction;
  highlightedObjectIds?: string[];
  saving?: boolean;
  onPointChange?: (objectId: string, point: Vec3) => void | Promise<void>;
  onImageCaptureReady?: (capture: ThreeSceneImageCapture | null) => void;
}

export function RendererPanelV3({
  response,
  previewScene,
  interaction,
  highlightedObjectIds = [],
  saving = false,
  onPointChange,
  onImageCaptureReady,
}: RendererPanelV3Props) {
  const projection = useMemo(() => {
    if (!response?.projection || !previewScene) return response?.projection;
    const positions = new Map(previewScene.objects.flatMap((object) => {
      if (object.type === 'point_2d') return [[object.id, [object.x, object.y, 0] as [number, number, number]]];
      if (object.type === 'point_3d') return [[object.id, [object.x, object.y, object.z] as [number, number, number]]];
      return [];
    }));
    return {
      ...response.projection,
      points: response.projection.points.map((point) => ({ ...point, position: positions.get(point.object_id) ?? point.position })),
    };
  }, [previewScene, response]);
  const threeScene = useMemo(() => projection?.renderer === 'threejs_3d' ? threeSceneFromProjectionV3(projection) : null, [projection]);
  const aliasToId = useMemo(
    () => new Map(Object.entries(projection?.object_names ?? {}).map(([id, name]) => [name, id])),
    [projection?.object_names],
  );

  if (!response || !projection) return <div className="renderer-frame"><div className="empty-state">Chưa có projection v3.</div></div>;
  const trustLabels = response.status === 'verified' && !response.requires_user_confirmation
    ? ['Dựng theo dữ kiện']
    : ['Hình cần xác nhận'];

  if (projection.renderer === 'geogebra_2d' || projection.renderer === 'geogebra_3d') {
    return (
      <div className="renderer-frame">
        <GeoGebraView
          commands={response.payload.geogebra_commands ?? []}
          renderer={projection.renderer}
          scene={legacyPointScene(response)}
          view={projection.view}
          onPointChange={onPointChange ? (name, point) => {
            const objectId = aliasToId.get(name);
            if (objectId) return onPointChange(objectId, point);
          } : undefined}
        />
        {saving && <div className="renderer-saving-overlay">Đang kiểm chứng chỉnh sửa...</div>}
      </div>
    );
  }

  if (threeScene) {
    return (
      <div className="renderer-frame">
        <Suspense fallback={<div className="renderer-loading-state">Đang tải trình dựng 3D...</div>}>
          <ThreeGeometryView
            scene={threeScene}
            interaction={interaction}
            highlightedObjects={highlightedObjectIds}
            trustLabels={trustLabels}
            onImageCaptureReady={onImageCaptureReady}
          />
        </Suspense>
        {saving && <div className="renderer-saving-overlay">Đang kiểm chứng chỉnh sửa...</div>}
      </div>
    );
  }

  return <div className="renderer-frame"><div className="error-box">Projection không có payload renderer tương thích.</div></div>;
}

function legacyPointScene(response: SceneWorkspaceResponseV3): MathScene {
  return {
    scene_id: response.scene.scene_id,
    schema_version: '3.0-projection',
    revision: response.scene.revision,
    problem_text: response.scene.problem_text,
    grade: response.scene.grade,
    topic: response.scene.topic,
    renderer: response.projection.renderer,
    objects: response.projection.points.map((point) => response.projection.dimension === '3d'
      ? {
          id: point.object_id,
          type: 'point_3d',
          name: point.name,
          x: point.position[0],
          y: point.position[1],
          z: point.position[2],
          source: 'user_edited',
          metadata: {},
        }
      : {
          id: point.object_id,
          type: 'point_2d',
          name: point.name,
          x: point.position[0],
          y: point.position[1],
          source: 'user_edited',
          metadata: {},
        }),
    relations: [],
    annotations: [],
    view: response.projection.view,
  };
}