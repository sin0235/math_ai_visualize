import { useEffect, useMemo, useRef, useState } from 'react';

import { previewPointMove } from '../hooks/sceneWorkspaceV3State';
import { useSceneWorkspaceV3 } from '../hooks/useSceneWorkspaceV3';
import type { MathSceneV3, SceneCommand, SceneWorkspaceResponseV3 } from '../types/sceneV3';
import { RendererPanelV3 } from './RendererPanelV3';
import { SceneInspectorV3 } from './SceneInspectorV3';
import type { ThreeSceneInteraction } from './ThreeGeometryView';

type EditToolV3 = ThreeSceneInteraction['mode'];
type Vec3 = { x: number; y: number; z: number };

interface SceneWorkspaceEditorV3Props {
  initialResponse: SceneWorkspaceResponseV3;
  onCommitted?: (response: SceneWorkspaceResponseV3) => void;
}

export function SceneWorkspaceEditorV3({ initialResponse, onCommitted }: SceneWorkspaceEditorV3Props) {
  const workspace = useSceneWorkspaceV3();
  const [tool, setTool] = useState<EditToolV3>('move');
  const [selectedPointId, setSelectedPointId] = useState<string | null>(null);
  const [placementPlane, setPlacementPlane] = useState<'xy' | 'xz' | 'yz'>('xy');
  const [placementDepth, setPlacementDepth] = useState(0);
  const [highlightedObjectIds, setHighlightedObjectIds] = useState<string[]>([]);
  const [localError, setLocalError] = useState<string | null>(null);
  const hydratedSceneId = useRef<string | null>(null);
  const parameterTimer = useRef<number | null>(null);
  const response = workspace.state.committed;
  const scene = response?.scene ?? null;
  const saving = workspace.state.pendingCommand !== null;

  useEffect(() => {
    if (hydratedSceneId.current === initialResponse.scene.scene_id) return;
    hydratedSceneId.current = initialResponse.scene.scene_id;
    workspace.hydrate(initialResponse);
  }, [initialResponse, workspace.hydrate]);

  useEffect(() => {
    if (response) onCommitted?.(response);
  }, [onCommitted, response]);

  useEffect(() => () => {
    if (parameterTimer.current !== null) window.clearTimeout(parameterTimer.current);
  }, []);

  const interaction = useMemo<ThreeSceneInteraction | undefined>(() => {
    if (!scene || scene.renderer !== 'threejs_3d') return undefined;
    return {
      mode: tool,
      selectedPoint: selectedPointId,
      pointPlacementPlane: placementPlane,
      pointPlacementDepth: placementDepth,
      saving,
      onPointClick: setSelectedPointId,
      onSegmentClick: (_points, objectId) => projectSelectedPoint(objectId),
      onPointDragEnd: (pointId, point) => movePoint(pointId, point),
      onConnectPoints: (startPointId, endPointId) => connectPoints(startPointId, endPointId),
      onCanvasClick: addPoint,
      onBlockedPointClick: () => setLocalError('Chọn vùng trống để thêm điểm.'),
    };
  }, [placementDepth, placementPlane, saving, scene, selectedPointId, tool]);

  function commandBase(): Pick<SceneCommand, 'command_id' | 'scene_id' | 'base_revision'> {
    if (!scene) throw new Error('Scene workspace chưa sẵn sàng.');
    return { command_id: newId('cmd'), scene_id: scene.scene_id, base_revision: scene.revision };
  }

  async function submit(command: SceneCommand) {
    setLocalError(null);
    try {
      return await workspace.commit(command);
    } catch (caught) {
      setLocalError(errorMessage(caught, 'Không thể áp dụng chỉnh sửa.'));
      return null;
    }
  }

  function movePoint(pointId: string, point: Vec3) {
    if (!scene || saving) return;
    const target = scene.objects.find((object) => object.id === pointId);
    if (target?.locked) {
      setLocalError(`Điểm ${target.label || target.id} đang bị khóa.`);
      return;
    }
    const position: [number, number, number] = [point.x, point.y, point.z];
    workspace.preview(previewPointMove(scene, pointId, position));
    void submit({ ...commandBase(), type: 'move_point', point_id: pointId, position });
  }

  function connectPoints(startPointId: string, endPointId: string) {
    if (!scene || saving || startPointId === endPointId) return;
    void submit({
      ...commandBase(),
      type: 'connect_points',
      object_id: newId('segment'),
      start_point_id: startPointId,
      end_point_id: endPointId,
      connection: 'segment',
    });
  }

  function addPoint(point: Vec3) {
    if (!scene || saving) return;
    const id = newId('point');
    const common = { id, label: nextPointLabel(scene), source: 'user_created' as const, locked: false, user_edited: true, metadata: {} };
    const object = scene.view.dimension === '3d'
      ? { ...common, type: 'point_3d' as const, x: point.x, y: point.y, z: point.z }
      : { ...common, type: 'point_2d' as const, x: point.x, y: point.y };
    void submit({ ...commandBase(), type: 'add_point', point: object });
  }

  function projectSelectedPoint(targetId?: string) {
    if (!scene || saving || !selectedPointId) {
      setLocalError('Chọn điểm nguồn trước, sau đó chọn đoạn đích.');
      return;
    }
    if (!targetId) {
      setLocalError('Projection cũ không có stable object ID cho đoạn đích.');
      return;
    }
    const sourcePointId = selectedPointId;
    setSelectedPointId(null);
    void submit({
      ...commandBase(),
      type: 'project_point',
      source_point_id: sourcePointId,
      target_id: targetId,
      target_kind: 'segment',
      result_point_id: newId('projection'),
    });
  }

  function setVisibility(objectId: string, visible: boolean) {
    if (!scene || saving) return;
    void submit({ ...commandBase(), type: 'set_visibility', object_id: objectId, visible });
  }

  function deleteObject(objectId: string) {
    if (!scene || saving) return;
    void submit({ ...commandBase(), type: 'delete_object', object_id: objectId });
  }

  function undoLatest() {
    if (saving || workspace.state.undoStack.length === 0) return;
    void workspace.undo().catch(() => undefined);
  }

  function previewParameter(parameterId: string, value: number) {
    if (!scene || saving || !Number.isFinite(value)) return;
    workspace.preview({
      ...scene,
      parameters: scene.parameters.map((parameter) => parameter.id === parameterId ? { ...parameter, default: value } : parameter),
    });
    if (parameterTimer.current !== null) window.clearTimeout(parameterTimer.current);
    parameterTimer.current = window.setTimeout(() => {
      parameterTimer.current = null;
      void submit({ ...commandBase(), type: 'set_parameter', parameter_id: parameterId, value });
    }, 450);
  }

  if (!response) {
    return <section className="panel scene-workspace-v3"><div className="info-box">Đang khởi tạo workspace v3...</div>{localError && <div className="error-box">{localError}</div>}</section>;
  }

  return (
    <section className="scene-workspace-v3">
      <RendererPanelV3
        response={response}
        previewScene={workspace.state.previewScene}
        interaction={interaction}
        highlightedObjectIds={highlightedObjectIds}
        saving={saving}
        onPointChange={movePoint}
      />

      <div className="panel scene-editor scene-editor-v3">
        <div className="scene-editor-v3-header">
          <div>
            <strong>Chỉnh sửa có ràng buộc</strong>
            <span className="field-hint">Revision {scene?.revision} · backend xác minh trước khi commit</span>
          </div>
          <div className="scene-editor-v3-history">
            <button type="button" className="secondary-button" disabled={saving || workspace.state.undoStack.length === 0} onClick={() => void workspace.undo().catch(() => undefined)}>Hoàn tác</button>
            <button type="button" className="secondary-button" disabled={saving || workspace.state.redoStack.length === 0} onClick={() => void workspace.redo().catch(() => undefined)}>Làm lại</button>
          </div>
        </div>

        <div className="tool-mode-grid" role="toolbar" aria-label="Công cụ chỉnh sửa scene v3">
          <ToolButton active={tool === 'move'} disabled={saving} onClick={() => setTool('move')} label="Di chuyển" detail="Kéo điểm, thả để kiểm chứng." />
          <ToolButton active={tool === 'connect'} disabled={saving || scene?.renderer !== 'threejs_3d'} onClick={() => setTool('connect')} label="Nối đoạn" detail="Kéo giữa hai điểm." />
          <ToolButton active={tool === 'project_to_segment'} disabled={saving || scene?.renderer !== 'threejs_3d'} onClick={() => setTool('project_to_segment')} label="Chiếu lên đoạn" detail="Chọn điểm rồi chọn đoạn." />
          <ToolButton active={tool === 'add_point'} disabled={saving || scene?.renderer !== 'threejs_3d'} onClick={() => setTool('add_point')} label="Thêm điểm" detail="Chọn mặt phẳng và vị trí." />
        </div>

        {tool === 'add_point' && scene?.view.dimension === '3d' && (
          <div className="editor-grid scene-editor-v3-placement">
            <label className="field-label">Mặt phẳng<select value={placementPlane} disabled={saving} onChange={(event) => setPlacementPlane(event.target.value as typeof placementPlane)}><option value="xy">Oxy</option><option value="xz">Oxz</option><option value="yz">Oyz</option></select></label>
            <label className="field-label">Tọa độ cố định<input type="number" step="any" value={placementDepth} disabled={saving} onChange={(event) => setPlacementDepth(Number(event.target.value))} /></label>
          </div>
        )}

        {scene && scene.parameters.length > 0 && (
          <div className="scene-editor-v3-parameters">
            <strong>Tham số</strong>
            {scene.parameters.map((parameter) => {
              const value = workspace.state.previewScene?.parameters.find((item) => item.id === parameter.id)?.default ?? parameter.default;
              return <label key={parameter.id} className="field-label">{parameter.label || parameter.name}: {value}<input type="range" min={parameter.min} max={parameter.max} step={parameter.step} value={value} disabled={saving} onChange={(event) => previewParameter(parameter.id, Number(event.target.value))} /></label>;
            })}
            {workspace.state.previewScene && <span className="warning-box">Preview tham số chưa được xác minh.</span>}
          </div>
        )}

        {scene && <SceneInspectorV3
          response={response}
          saving={saving}
          highlightedObjectIds={highlightedObjectIds}
          onHighlight={setHighlightedObjectIds}
          onSetVisibility={setVisibility}
          onDelete={deleteObject}
          onUndo={undoLatest}
        />}

        {response.requires_user_confirmation && !workspace.trusted && <button type="button" className="secondary-button" disabled={saving} onClick={workspace.confirm}>Xác nhận revision này</button>}
        {saving && <div className="warning-box">Đang kiểm chứng chỉnh sửa...</div>}
        {(localError || workspace.state.error) && <div className="error-box">{localError || workspace.state.error}</div>}
      </div>
    </section>
  );
}

function ToolButton({ active, disabled, onClick, label, detail }: { active: boolean; disabled: boolean; onClick: () => void; label: string; detail: string }) {
  return <button type="button" className={`tool-mode-button ${active ? 'active' : ''}`} disabled={disabled} onClick={onClick}><strong>{label}</strong><span>{detail}</span></button>;
}

function nextPointLabel(scene: MathSceneV3) {
  const labels = new Set(scene.objects.map((object) => object.label).filter(Boolean));
  for (const label of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') if (!labels.has(label)) return label;
  return `P${scene.objects.length + 1}`;
}

function newId(prefix: string) {
  return `${prefix}:${crypto.randomUUID()}`;
}

function errorMessage(caught: unknown, fallback: string) {
  return caught instanceof Error ? caught.message : fallback;
}