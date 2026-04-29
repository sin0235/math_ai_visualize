import { FormEvent, useMemo, useState } from 'react';

import type { Line2D, Line3D, MathScene, Point2D, Point3D, SceneObject, Segment } from '../types/scene';

type EditTool = 'move' | 'connect' | 'project_to_segment';

interface SceneEditorPanelProps {
  scene: MathScene | null;
  saving: boolean;
  editTool: EditTool;
  selectedPoint: string | null;
  onEditToolChange: (tool: EditTool) => void;
  onChange: (scene: MathScene) => void;
}

type PointLike = Point2D | Point3D;
type LineLike = Line2D | Line3D | Segment;
type Vec3 = { x: number; y: number; z: number };

const lineColor = '#1d3557';

export function SceneEditorPanel({
  scene,
  saving,
  editTool,
  selectedPoint,
  onEditToolChange,
  onChange,
}: SceneEditorPanelProps) {
  const [error, setError] = useState<string | null>(null);
  const [pointName, setPointName] = useState('');
  const [x, setX] = useState('0');
  const [y, setY] = useState('0');
  const [z, setZ] = useState('0');
  const [startPoint, setStartPoint] = useState('');
  const [endPoint, setEndPoint] = useState('');
  const [connectionKind, setConnectionKind] = useState<'segment' | 'line'>('segment');
  const [lineForPoint, setLineForPoint] = useState('');
  const [lineParameter, setLineParameter] = useState('0.5');
  const [intersectionLineA, setIntersectionLineA] = useState('');
  const [intersectionLineB, setIntersectionLineB] = useState('');

  const points = useMemo(() => (scene ? getPoints(scene) : []), [scene]);
  const lines = useMemo(() => (scene ? getLines(scene) : []), [scene]);
  const dimension = scene?.view.dimension ?? '2d';

  if (!scene) return null;
  const activeScene = scene;

  const nextPointName = pointName.trim() || nextName(points.map((point) => point.name), 'P');
  const hasTwoPoints = points.length >= 2;
  const hasLine = lines.length > 0;
  const canIntersect = lines.length >= 2;

  function submit(nextScene: MathScene) {
    setError(null);
    onChange(nextScene);
  }

  function addPoint(event: FormEvent) {
    event.preventDefault();
    try {
      const name = validateNewName(activeScene, nextPointName);
      const point = dimension === '3d'
        ? { type: 'point_3d' as const, name, x: parseNumber(x, 'x'), y: parseNumber(y, 'y'), z: parseNumber(z, 'z') }
        : { type: 'point_2d' as const, name, x: parseNumber(x, 'x'), y: parseNumber(y, 'y') };
      submit({ ...activeScene, objects: [...activeScene.objects, point] });
      setPointName(nextName([...points.map((point) => point.name), name], 'P'));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thêm được điểm.');
    }
  }

  function connectPoints(event: FormEvent) {
    event.preventDefault();
    try {
      if (!startPoint || !endPoint || startPoint === endPoint) {
        throw new Error('Chọn hai điểm khác nhau.');
      }
      if (connectionKind === 'line') {
        const line = dimension === '3d'
          ? { type: 'line_3d' as const, name: nextLineName(activeScene), through: [startPoint, endPoint] as [string, string], color: lineColor }
          : { type: 'line_2d' as const, name: nextLineName(activeScene), through: [startPoint, endPoint] as [string, string] };
        submit({ ...activeScene, objects: [...activeScene.objects, line] });
      } else {
        submit({
          ...activeScene,
          objects: [
            ...activeScene.objects,
            { type: 'segment' as const, points: [startPoint, endPoint], hidden: false, color: lineColor, line_width: 3, style: 'solid' },
          ],
        });
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không nối được điểm.');
    }
  }

  function addPointOnLine(event: FormEvent) {
    event.preventDefault();
    try {
      const line = lines.find((item) => lineKey(item) === lineForPoint);
      if (!line) throw new Error('Chọn một đường thẳng.');
      const point = pointOnLine(activeScene, line, parseNumber(lineParameter, 't'));
      const name = validateNewName(activeScene, nextPointName);
      submit({ ...activeScene, objects: [...activeScene.objects, makePoint(dimension, name, point)] });
      setPointName(nextName([...points.map((item) => item.name), name], 'P'));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thêm được điểm trên đường.');
    }
  }

  function addLineIntersection(event: FormEvent) {
    event.preventDefault();
    try {
      const lineA = lines.find((item) => lineKey(item) === intersectionLineA);
      const lineB = lines.find((item) => lineKey(item) === intersectionLineB);
      if (!lineA || !lineB || lineKey(lineA) === lineKey(lineB)) {
        throw new Error('Chọn hai đường thẳng khác nhau.');
      }
      const point = dimension === '3d'
        ? intersectLines3d(activeScene, lineA, lineB)
        : intersectLines2d(activeScene, lineA, lineB);
      const name = validateNewName(activeScene, nextPointName);
      submit({ ...activeScene, objects: [...activeScene.objects, makePoint(dimension, name, point)] });
      setPointName(nextName([...points.map((item) => item.name), name], 'P'));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không tạo được giao điểm.');
    }
  }

  return (
    <section className="panel scene-editor">
      <details className="scene-editor-details">
        <summary className="scene-editor-summary">
          <span>Chỉnh hình</span>
          <span className="viewer-hint">Bấm để mở công cụ chỉnh</span>
        </summary>
        <p className="field-hint">{dimension === '3d' ? '3D' : '2D'}: kéo điểm, kéo nối đoạn, thêm điểm và tạo giao điểm.</p>
        <div className="scene-editor-content">
      <div className="click-tool">
        <span className="field-label">Công cụ trên hình</span>
        <div className="tool-mode-grid">
          <ToolModeButton active={editTool === 'move'} disabled={saving} onClick={() => onEditToolChange('move')} title="Kéo điểm" description="Kéo điểm để đổi vị trí." />
          <ToolModeButton active={editTool === 'connect'} disabled={saving || activeScene.renderer !== 'threejs_3d'} onClick={() => onEditToolChange('connect')} title="Kéo nối đoạn" description="Kéo từ điểm này sang điểm khác để tạo đoạn." />
          <ToolModeButton active={editTool === 'project_to_segment'} disabled={saving || activeScene.renderer !== 'threejs_3d'} onClick={() => onEditToolChange('project_to_segment')} title="Tạo chân nối" description="Click điểm nguồn rồi click đoạn đích." />
        </div>
        <span className="field-hint">
          {activeScene.renderer === 'threejs_3d'
            ? toolHint(editTool, selectedPoint)
            : 'Công cụ kéo trực tiếp hiện hỗ trợ Three.js 3D.'}
        </span>
      </div>
      {error && <div className="error-box">{error}</div>}
      {saving && <div className="warning-box">Đang dựng lại hình...</div>}

      <form className="editor-grid" onSubmit={addPoint}>
        <label className="field-label">
          Tên điểm
          <input value={pointName} onChange={(event) => setPointName(event.target.value)} placeholder={nextPointName} />
        </label>
        <label className="field-label">
          x
          <input type="number" step="0.1" value={x} onChange={(event) => setX(event.target.value)} />
        </label>
        <label className="field-label">
          y
          <input type="number" step="0.1" value={y} onChange={(event) => setY(event.target.value)} />
        </label>
        {dimension === '3d' && (
          <label className="field-label">
            z
            <input type="number" step="0.1" value={z} onChange={(event) => setZ(event.target.value)} />
          </label>
        )}
        <button type="submit" className="secondary-button" disabled={saving}>Thêm điểm</button>
      </form>

      <form className="editor-grid" onSubmit={connectPoints}>
        <PointSelect label="Từ điểm" value={startPoint} points={points} onChange={setStartPoint} />
        <PointSelect label="Đến điểm" value={endPoint} points={points} onChange={setEndPoint} />
        <label className="field-label">
          Loại
          <select value={connectionKind} onChange={(event) => setConnectionKind(event.target.value as 'segment' | 'line')}>
            <option value="segment">Đoạn thẳng</option>
            <option value="line">Đường thẳng</option>
          </select>
        </label>
        <button type="submit" className="secondary-button" disabled={saving || !hasTwoPoints}>Nối điểm</button>
      </form>

      <form className="editor-grid" onSubmit={addPointOnLine}>
        <LineSelect label="Đường thẳng" value={lineForPoint} lines={lines} onChange={setLineForPoint} />
        <label className="field-label">
          Tham số t
          <input type="number" step="0.1" value={lineParameter} onChange={(event) => setLineParameter(event.target.value)} />
        </label>
        <button type="submit" className="secondary-button" disabled={saving || !hasLine}>Thêm điểm trên đường</button>
      </form>

      <form className="editor-grid" onSubmit={addLineIntersection}>
        <LineSelect label="Đường 1" value={intersectionLineA} lines={lines} onChange={setIntersectionLineA} />
        <LineSelect label="Đường 2" value={intersectionLineB} lines={lines} onChange={setIntersectionLineB} />
        <button type="submit" className="secondary-button" disabled={saving || !canIntersect}>Tạo giao điểm</button>
      </form>
        </div>
      </details>
    </section>
  );
}

function ToolModeButton({ active, disabled, onClick, title, description }: { active: boolean; disabled: boolean; onClick: () => void; title: string; description: string }) {
  return (
    <button type="button" className={`tool-mode-button ${active ? 'active' : ''}`} disabled={disabled} onClick={onClick}>
      <strong>{title}</strong>
      <span>{description}</span>
    </button>
  );
}

function toolHint(tool: EditTool, selectedPoint: string | null) {
  if (tool === 'connect') return 'Kéo từ một điểm sang điểm khác để nối đoạn thẳng.';
  if (tool === 'project_to_segment') {
    return selectedPoint ? `Đã chọn điểm ${selectedPoint}. Click vào đoạn đích trên hình.` : 'Click điểm nguồn trên hình, sau đó click đoạn đích.';
  }
  return 'Kéo trực tiếp một điểm trên hình để cập nhật vị trí.';
}

function PointSelect({ label, value, points, onChange }: { label: string; value: string; points: PointLike[]; onChange: (value: string) => void }) {
  return (
    <label className="field-label">
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Chọn điểm</option>
        {points.map((point) => <option key={point.name} value={point.name}>{point.name}</option>)}
      </select>
    </label>
  );
}

function LineSelect({ label, value, lines, onChange }: { label: string; value: string; lines: LineLike[]; onChange: (value: string) => void }) {
  return (
    <label className="field-label">
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Chọn đường</option>
        {lines.map((line) => <option key={lineKey(line)} value={lineKey(line)}>{lineLabel(line)}</option>)}
      </select>
    </label>
  );
}

function getPoints(scene: MathScene): PointLike[] {
  return scene.objects.filter((obj): obj is PointLike => obj.type === 'point_2d' || obj.type === 'point_3d');
}

function getLines(scene: MathScene): LineLike[] {
  return scene.objects.filter((obj): obj is LineLike => obj.type === 'line_2d' || obj.type === 'line_3d' || obj.type === 'segment');
}

function lineKey(line: LineLike) {
  const anchors = lineAnchors(line);
  return `${line.type}:${line.name ?? anchors.join('')}:${anchors.join('-')}`;
}

function lineLabel(line: LineLike) {
  const anchors = lineAnchors(line);
  const kind = line.type === 'segment' ? 'đoạn' : 'đường';
  return line.name ? `${line.name} (${anchors.join(', ')})` : `${kind} ${anchors.join('')}`;
}

function lineAnchors(line: LineLike): [string, string] {
  return line.type === 'segment' ? line.points : line.through;
}

function parseNumber(value: string, label: string) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) throw new Error(`${label} không hợp lệ.`);
  return parsed;
}

function validateNewName(scene: MathScene, name: string) {
  const clean = name.trim();
  if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(clean)) {
    throw new Error('Tên điểm phải bắt đầu bằng chữ và chỉ gồm chữ, số hoặc _.');
  }
  if (scene.objects.some((obj) => objectName(obj) === clean)) {
    throw new Error(`Tên ${clean} đã tồn tại.`);
  }
  return clean;
}

function objectName(obj: SceneObject) {
  if ('name' in obj && typeof obj.name === 'string') return obj.name;
  return null;
}

function nextName(existing: string[], prefix: string) {
  for (const name of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') {
    if (!existing.includes(name)) return name;
  }
  let index = 1;
  while (existing.includes(`${prefix}${index}`)) index += 1;
  return `${prefix}${index}`;
}

function nextLineName(scene: MathScene) {
  const used = new Set(scene.objects.map(objectName).filter(Boolean));
  let index = 1;
  while (used.has(`d${index}`)) index += 1;
  return `d${index}`;
}

function makePoint(dimension: '2d' | '3d', name: string, point: Vec3): PointLike {
  if (dimension === '3d') {
    return { type: 'point_3d', name, x: round(point.x), y: round(point.y), z: round(point.z) };
  }
  return { type: 'point_2d', name, x: round(point.x), y: round(point.y) };
}

function pointMap(scene: MathScene) {
  const points = new Map<string, Vec3>();
  getPoints(scene).forEach((point) => {
    points.set(point.name, { x: point.x, y: point.y, z: point.type === 'point_3d' ? point.z : 0 });
  });
  return points;
}

function pointOnLine(scene: MathScene, line: LineLike, t: number): Vec3 {
  const points = pointMap(scene);
  const anchors = lineAnchors(line);
  const start = points.get(anchors[0]);
  const end = points.get(anchors[1]);
  if (!start || !end) throw new Error('Đường thẳng thiếu điểm neo.');
  return add(start, scale(sub(end, start), t));
}

function intersectLines2d(scene: MathScene, lineA: LineLike, lineB: LineLike): Vec3 {
  const points = pointMap(scene);
  const anchorsA = lineAnchors(lineA);
  const anchorsB = lineAnchors(lineB);
  const p = points.get(anchorsA[0]);
  const p2 = points.get(anchorsA[1]);
  const q = points.get(anchorsB[0]);
  const q2 = points.get(anchorsB[1]);
  if (!p || !p2 || !q || !q2) throw new Error('Đường thẳng thiếu điểm neo.');
  const r = sub(p2, p);
  const s = sub(q2, q);
  const denom = cross2(r, s);
  if (Math.abs(denom) < 1e-9) throw new Error('Hai đường song song hoặc trùng nhau.');
  const t = cross2(sub(q, p), s) / denom;
  return add(p, scale(r, t));
}

function intersectLines3d(scene: MathScene, lineA: LineLike, lineB: LineLike): Vec3 {
  const points = pointMap(scene);
  const anchorsA = lineAnchors(lineA);
  const anchorsB = lineAnchors(lineB);
  const p = points.get(anchorsA[0]);
  const p2 = points.get(anchorsA[1]);
  const q = points.get(anchorsB[0]);
  const q2 = points.get(anchorsB[1]);
  if (!p || !p2 || !q || !q2) throw new Error('Đường thẳng thiếu điểm neo.');
  const r = sub(p2, p);
  const s = sub(q2, q);
  const a = dot(r, r);
  const b = dot(r, s);
  const c = dot(s, s);
  const w = sub(p, q);
  const d = dot(r, w);
  const e = dot(s, w);
  const denom = a * c - b * b;
  if (Math.abs(denom) < 1e-9) throw new Error('Hai đường song song hoặc trùng nhau.');
  const t = (b * e - c * d) / denom;
  const u = (a * e - b * d) / denom;
  const pClosest = add(p, scale(r, t));
  const qClosest = add(q, scale(s, u));
  if (length(sub(pClosest, qClosest)) > 1e-5) {
    throw new Error('Hai đường thẳng chéo nhau, không có giao điểm.');
  }
  return scale(add(pClosest, qClosest), 0.5);
}

function sub(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
}

function add(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z };
}

function scale(v: Vec3, s: number): Vec3 {
  return { x: v.x * s, y: v.y * s, z: v.z * s };
}

function dot(a: Vec3, b: Vec3): number {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

function cross2(a: Vec3, b: Vec3): number {
  return a.x * b.y - a.y * b.x;
}

function length(v: Vec3): number {
  return Math.sqrt(dot(v, v));
}

function round(value: number) {
  return Math.round(value * 1_000_000) / 1_000_000;
}
