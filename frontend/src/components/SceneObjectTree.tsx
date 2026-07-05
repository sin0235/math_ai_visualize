import { useMemo, useState } from 'react';

import type { Annotation, Line2D, Line3D, MathScene, Plane, Point2D, Point3D, Relation, SceneObject, Segment } from '../types/scene';

type TreeItemKind = 'object' | 'relation' | 'annotation';
type VerificationFilter = 'all' | 'verified' | 'failed' | 'unsupported' | 'unverifiable' | 'error' | 'none';
type SourceFilter = 'all' | 'given' | 'ai_inferred' | 'construction' | 'user_created' | 'user_edited';

type TreeItem = {
  key: string;
  kind: TreeItemKind;
  index: number;
  group: string;
  label: string;
  source: string;
  verification: VerificationFilter;
  hidden: boolean;
  locked: boolean;
  highlight: string[];
  dependencies: string[];
  relatedRelations: Relation[];
};

type Vec3 = { x: number; y: number; z: number };
type ContextAction = { id: string; label: string; run: () => MathScene | null };

interface SceneObjectTreeProps {
  scene: MathScene;
  saving: boolean;
  onChange: (scene: MathScene) => void;
  onHighlightObjects?: (names: string[]) => void;
}

const groupOrder = ['Điểm', 'Đường', 'Đoạn', 'Vectơ', 'Mặt', 'Mặt phẳng', 'Khối', 'Quan hệ', 'Chú thích', 'Đối tượng phụ'];
const sourceOptions: SourceFilter[] = ['all', 'given', 'ai_inferred', 'construction', 'user_created', 'user_edited'];
const verificationOptions: VerificationFilter[] = ['all', 'verified', 'failed', 'unsupported', 'unverifiable', 'error', 'none'];

export function SceneObjectTree({ scene, saving, onChange, onHighlightObjects }: SceneObjectTreeProps) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [contextKeys, setContextKeys] = useState<string[]>([]);
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all');
  const [verificationFilter, setVerificationFilter] = useState<VerificationFilter>('all');
  const [renameValue, setRenameValue] = useState('');
  const items = useMemo(() => buildTreeItems(scene), [scene]);
  const filtered = items.filter((item) => {
    const sourceOk = sourceFilter === 'all' || item.source === sourceFilter;
    const verificationOk = verificationFilter === 'all' || item.verification === verificationFilter;
    return sourceOk && verificationOk;
  });
  const grouped = groupOrder.map((group) => ({ group, items: filtered.filter((item) => item.group === group) })).filter((group) => group.items.length > 0);
  const selected = items.find((item) => item.key === selectedKey) ?? null;
  const contextItems = contextKeys.map((key) => items.find((item) => item.key === key)).filter(Boolean) as TreeItem[];
  const contextActions = useMemo(() => buildContextActions(scene, contextItems), [scene, contextItems]);

  function selectItem(item: TreeItem) {
    setSelectedKey(item.key);
    setRenameValue(item.label);
    if (item.kind === 'object') {
      setContextKeys((current) => [...current.filter((key) => key !== item.key), item.key].slice(-2));
    }
    onHighlightObjects?.(item.highlight);
  }

  function clearSelection() {
    setSelectedKey(null);
    setContextKeys([]);
    onHighlightObjects?.([]);
  }

  function submit(next: MathScene) {
    onChange({ ...next, revision: (scene.revision ?? 0) + 1 });
  }

  function updateSelected(update: (item: TreeItem) => MathScene | null, options: { allowLocked?: boolean } = {}) {
    if (!selected || saving) return;
    if (selected.locked && !options.allowLocked) return;
    const next = update(selected);
    if (next) submit(next);
  }

  function runContextAction(action: ContextAction) {
    if (saving) return;
    const next = action.run();
    if (next) submit(next);
  }

  return (
    <section className="scene-object-tree" aria-label="Object tree">
      <div className="scene-object-tree-head">
        <div>
          <strong>Object tree</strong>
          <span>Scene</span>
        </div>
        <button type="button" className="secondary-button" onClick={clearSelection} disabled={saving}>Bỏ chọn</button>
      </div>

      <div className="scene-object-tree-filters">
        <label className="field-label">Source
          <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as SourceFilter)}>
            {sourceOptions.map((value) => <option key={value} value={value}>{sourceLabel(value)}</option>)}
          </select>
        </label>
        <label className="field-label">Verification
          <select value={verificationFilter} onChange={(event) => setVerificationFilter(event.target.value as VerificationFilter)}>
            {verificationOptions.map((value) => <option key={value} value={value}>{verificationLabel(value)}</option>)}
          </select>
        </label>
      </div>

      <div className="scene-object-tree-body">
        {grouped.map(({ group, items }) => (
          <details key={group} open>
            <summary>{group} <span>{items.length}</span></summary>
            <div className="scene-object-tree-list">
              {items.map((item) => (
                <button
                  type="button"
                  key={item.key}
                  className={`scene-object-tree-item ${selectedKey === item.key ? 'active' : ''} ${contextKeys.includes(item.key) ? 'context-active' : ''}`}
                  onClick={() => selectItem(item)}
                >
                  <span>{item.label}</span>
                  <small>{item.source}{item.verification !== 'none' ? ` · ${item.verification}` : ''}{item.hidden ? ' · ẩn' : ''}{item.locked ? ' · khóa' : ''}</small>
                </button>
              ))}
            </div>
          </details>
        ))}
        {grouped.length === 0 && <p className="field-hint">Không có object khớp filter.</p>}
      </div>

      {contextItems.length > 0 && (
        <div className="scene-object-tree-detail context-tools">
          <div className="scene-object-tree-detail-title">
            <strong>Công cụ theo ngữ cảnh</strong>
            <span>{contextItems.map((item) => item.label).join(' + ')}</span>
          </div>
          <div className="scene-object-tree-actions">
            {contextActions.length > 0
              ? contextActions.map((action) => <button key={action.id} type="button" onClick={() => runContextAction(action)} disabled={saving}>{action.label}</button>)
              : <span className="field-hint">Chọn thêm object phù hợp.</span>}
          </div>
        </div>
      )}

      {selected && (
        <div className="scene-object-tree-detail">
          <div className="scene-object-tree-detail-title">
            <strong>{selected.label}</strong>
            <span>{selected.group}</span>
          </div>
          <div className="scene-object-tree-actions">
            <button type="button" onClick={() => updateSelected((item) => toggleHidden(scene, item))} disabled={saving || selected.locked}>{selected.hidden ? 'Hiện' : 'Ẩn'}</button>
            <button type="button" onClick={() => updateSelected((item) => toggleLocked(scene, item), { allowLocked: true })} disabled={saving}>{selected.locked ? 'Mở khóa' : 'Khóa'}</button>
            <button type="button" onClick={() => updateSelected((item) => duplicateItem(scene, item))} disabled={saving || selected.kind !== 'object'}>Nhân bản</button>
            <button type="button" className="danger-button" onClick={() => updateSelected((item) => deleteItem(scene, item))} disabled={saving || selected.locked}>Xóa</button>
          </div>
          {selected.kind === 'object' && (
            <form className="scene-object-tree-rename" onSubmit={(event) => {
              event.preventDefault();
              updateSelected((item) => renameObject(scene, item, renameValue));
            }}>
              <input value={renameValue} onChange={(event) => setRenameValue(event.target.value)} disabled={saving || selected.locked} />
              <button type="submit" disabled={saving || selected.locked || !renameValue.trim()}>Đổi tên</button>
            </form>
          )}
          <InfoList title="Dependency" items={selected.dependencies} empty="Không có dependency." />
          <InfoList title="Relation liên quan" items={selected.relatedRelations.map(relationLabel)} empty="Không có relation liên quan." />
        </div>
      )}
    </section>
  );
}

function InfoList({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div className="scene-object-tree-info">
      <strong>{title}</strong>
      {items.length > 0 ? <ul>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p>{empty}</p>}
    </div>
  );
}

function buildTreeItems(scene: MathScene): TreeItem[] {
  const pointNames = new Set(scene.objects.flatMap((obj) => (obj.type === 'point_2d' || obj.type === 'point_3d') ? [obj.name] : []));
  const objectItems = scene.objects.map((obj, index): TreeItem => {
    const refs = objectReferences(obj);
    const label = objectLabel(obj, index);
    const key = `object:${index}`;
    const relatedRelations = scene.relations.filter((relation) => refs.some((ref) => relationReferencesToken(relation, ref)));
    return {
      key,
      kind: 'object',
      index,
      group: objectGroup(obj),
      label,
      source: obj.source ?? 'ai_inferred',
      verification: verificationForRelations(relatedRelations),
      hidden: isHidden(obj),
      locked: Boolean(obj.locked),
      highlight: refs.filter((ref) => pointNames.has(ref)),
      dependencies: refs,
      relatedRelations,
    };
  });
  const relationItems = scene.relations.map((relation, index): TreeItem => ({
    key: `relation:${index}`,
    kind: 'relation',
    index,
    group: 'Quan hệ',
    label: relationLabel(relation),
    source: relation.source ?? 'ai_inferred',
    verification: (relation.verification?.status ?? 'none') as VerificationFilter,
    hidden: Boolean(relation.metadata?.tree_hidden),
    locked: Boolean(relation.metadata?.locked),
    highlight: relationReferences(relation).filter((ref) => pointNames.has(ref)),
    dependencies: relationReferences(relation),
    relatedRelations: [relation],
  }));
  const annotationItems = scene.annotations.map((annotation, index): TreeItem => ({
    key: `annotation:${index}`,
    kind: 'annotation',
    index,
    group: 'Chú thích',
    label: annotationLabel(annotation),
    source: annotation.source ?? 'ai_inferred',
    verification: 'none',
    hidden: Boolean(annotation.metadata?.tree_hidden),
    locked: Boolean(annotation.metadata?.locked),
    highlight: annotationReferences(annotation).filter((ref) => pointNames.has(ref)),
    dependencies: annotationReferences(annotation),
    relatedRelations: scene.relations.filter((relation) => annotationReferences(annotation).some((ref) => relationReferencesToken(relation, ref))),
  }));
  return [...objectItems, ...relationItems, ...annotationItems];
}

function objectGroup(obj: SceneObject) {
  if (obj.type === 'point_2d' || obj.type === 'point_3d') return 'Điểm';
  if (obj.type === 'line_2d' || obj.type === 'line_3d' || obj.type === 'circle_2d' || obj.type === 'function_graph') return 'Đường';
  if (obj.type === 'segment') return 'Đoạn';
  if (obj.type === 'vector_2d' || obj.type === 'vector_3d') return 'Vectơ';
  if (obj.type === 'face') return 'Mặt';
  if (obj.type === 'plane') return 'Mặt phẳng';
  if (obj.type === 'sphere') return 'Khối';
  return 'Đối tượng phụ';
}

function objectLabel(obj: SceneObject, index: number) {
  const named = objectName(obj);
  if (named) return named;
  if (obj.type === 'segment') return `${obj.points[0]}${obj.points[1]}`;
  return `${obj.type} #${index + 1}`;
}

function objectName(obj: SceneObject) {
  return 'name' in obj && typeof obj.name === 'string' && obj.name.trim() ? obj.name : null;
}

function objectReferences(obj: SceneObject): string[] {
  if (obj.type === 'point_2d' || obj.type === 'point_3d') return [obj.name];
  if (obj.type === 'segment') return [...obj.points, edgeKey(obj.points), obj.name].filter(Boolean) as string[];
  if (obj.type === 'line_2d' || obj.type === 'line_3d') return [...obj.through, edgeKey(obj.through), obj.name].filter(Boolean) as string[];
  if (obj.type === 'vector_2d' || obj.type === 'vector_3d') return [obj.from_point, obj.to_point, `${obj.from_point}-${obj.to_point}`, obj.name].filter(Boolean) as string[];
  if (obj.type === 'circle_2d') return [obj.center, obj.through, obj.name].filter(Boolean) as string[];
  if (obj.type === 'face' || obj.type === 'plane') return [...obj.points, obj.name].filter(Boolean) as string[];
  if (obj.type === 'sphere') return [obj.center, obj.name].filter(Boolean) as string[];
  if (obj.type === 'function_graph') return [obj.name];
  return [];
}

function relationReferences(relation: Relation): string[] {
  return [...tokensFromString(relation.object_1), ...tokensFromString(relation.object_2), ...tokensFromUnknown(relation.args), ...tokensFromUnknown(relation.metadata)];
}

function annotationReferences(annotation: Annotation): string[] {
  return [...tokensFromString(annotation.target), ...tokensFromUnknown(annotation.metadata)];
}

function relationReferencesToken(relation: Relation, token: string) {
  return relationReferences(relation).includes(token);
}

function tokensFromString(value: unknown): string[] {
  if (typeof value !== 'string') return [];
  const raw = value.match(/[A-Za-z][A-Za-z0-9_]*/g) ?? [];
  return raw.flatMap((token) => {
    if (token === 'plane') return [];
    if (/^[A-Z]{2,}$/.test(token)) return [token, ...token.split('')];
    return [token];
  });
}

function tokensFromUnknown(value: unknown): string[] {
  if (value == null) return [];
  if (typeof value === 'string') return tokensFromString(value);
  if (Array.isArray(value)) return value.flatMap(tokensFromUnknown);
  if (typeof value === 'object') return Object.values(value).flatMap(tokensFromUnknown);
  return [];
}

function edgeKey(points: readonly string[]) {
  return `${points[0]}-${points[1]}`;
}

function isHidden(obj: SceneObject) {
  if (obj.type === 'segment' && obj.hidden) return true;
  return Boolean(obj.metadata?.tree_hidden);
}

function verificationForRelations(relations: Relation[]): VerificationFilter {
  const statuses = relations.map((relation) => relation.verification?.status).filter(Boolean) as VerificationFilter[];
  if (statuses.includes('failed')) return 'failed';
  if (statuses.includes('error')) return 'error';
  if (statuses.includes('unverifiable')) return 'unverifiable';
  if (statuses.includes('unsupported')) return 'unsupported';
  if (statuses.includes('verified')) return 'verified';
  return 'none';
}

function relationLabel(relation: Relation) {
  const right = relation.object_2 ? `, ${relation.object_2}` : '';
  return `${relation.type}(${relation.object_1}${right})`;
}

function annotationLabel(annotation: Annotation) {
  return `${annotation.type}: ${annotation.label ?? annotation.target}`;
}

function toggleHidden(scene: MathScene, item: TreeItem): MathScene | null {
  if (item.kind === 'object') {
    return {
      ...scene,
      objects: scene.objects.map((obj, index) => index === item.index ? toggleObjectHidden(obj) : obj),
    };
  }
  if (item.kind === 'annotation') {
    return { ...scene, annotations: scene.annotations.map((annotation, index) => index === item.index ? { ...annotation, metadata: { ...annotation.metadata, tree_hidden: !item.hidden } } : annotation) };
  }
  return { ...scene, relations: scene.relations.map((relation, index) => index === item.index ? { ...relation, metadata: { ...relation.metadata, tree_hidden: !item.hidden } } : relation) };
}

function toggleObjectHidden(obj: SceneObject): SceneObject {
  if (obj.type === 'segment') return { ...obj, hidden: !obj.hidden, metadata: { ...obj.metadata, tree_hidden: !isHidden(obj) } };
  return { ...obj, metadata: { ...obj.metadata, tree_hidden: !isHidden(obj) } };
}

function toggleLocked(scene: MathScene, item: TreeItem): MathScene | null {
  if (item.kind === 'object') return { ...scene, objects: scene.objects.map((obj, index) => index === item.index ? { ...obj, locked: !item.locked } : obj) };
  if (item.kind === 'annotation') return { ...scene, annotations: scene.annotations.map((annotation, index) => index === item.index ? { ...annotation, metadata: { ...annotation.metadata, locked: !item.locked } } : annotation) };
  return { ...scene, relations: scene.relations.map((relation, index) => index === item.index ? { ...relation, metadata: { ...relation.metadata, locked: !item.locked } } : relation) };
}

function deleteItem(scene: MathScene, item: TreeItem): MathScene | null {
  if (item.kind === 'relation') return { ...scene, relations: scene.relations.filter((_, index) => index !== item.index) };
  if (item.kind === 'annotation') return { ...scene, annotations: scene.annotations.filter((_, index) => index !== item.index) };
  const obj = scene.objects[item.index];
  if (!obj) return null;
  const refs = objectReferences(obj);
  const removesDependents = obj.type === 'point_2d' || obj.type === 'point_3d';
  return {
    ...scene,
    objects: scene.objects.filter((candidate, index) => index !== item.index && (!removesDependents || !refs.some((ref) => objectReferences(candidate).includes(ref)))),
    relations: scene.relations.filter((relation) => !refs.some((ref) => relationReferencesToken(relation, ref))),
    annotations: scene.annotations.filter((annotation) => !refs.some((ref) => annotationReferences(annotation).includes(ref))),
  };
}

function duplicateItem(scene: MathScene, item: TreeItem): MathScene | null {
  const obj = scene.objects[item.index];
  if (!obj) return null;
  const clone = duplicateObject(scene, obj);
  return clone ? { ...scene, objects: [...scene.objects, clone] } : null;
}

function duplicateObject(scene: MathScene, obj: SceneObject): SceneObject | null {
  const used = scene.objects.map(objectName).filter(Boolean) as string[];
  const name = objectName(obj);
  const nextName = name ? nextAvailableName(used, `${name}_copy`) : null;
  const metadata = { ...obj.metadata, duplicated_from: name ?? obj.type };
  if (obj.type === 'point_2d') return { ...obj, id: null, name: nextName ?? nextAvailableName(used, 'P'), x: obj.x + 0.25, y: obj.y + 0.25, locked: false, metadata };
  if (obj.type === 'point_3d') return { ...obj, id: null, name: nextName ?? nextAvailableName(used, 'P'), x: obj.x + 0.25, y: obj.y + 0.25, z: obj.z + 0.25, locked: false, metadata };
  if (obj.type === 'segment') return { ...obj, id: null, name: nextName ?? nextAvailableName(used, `${obj.points[0]}${obj.points[1]}_copy`), locked: false, metadata };
  if (name && 'name' in obj) return { ...obj, id: null, name: nextName, locked: false, metadata } as SceneObject;
  return null;
}

function renameObject(scene: MathScene, item: TreeItem, rawName: string): MathScene | null {
  const clean = rawName.trim();
  if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(clean)) return null;
  const obj = scene.objects[item.index];
  const oldName = obj ? objectName(obj) : null;
  if (!obj || oldName === clean) return null;
  if (scene.objects.some((candidate, index) => index !== item.index && objectName(candidate) === clean)) return null;
  if (!oldName) {
    return {
      ...scene,
      objects: scene.objects.map((candidate, index) => index === item.index ? ({ ...candidate, name: clean } as SceneObject) : candidate),
    };
  }
  return {
    ...scene,
    objects: scene.objects.map((candidate, index) => index === item.index ? ({ ...candidate, name: clean } as SceneObject) : renameObjectPointRefs(candidate, oldName, clean)),
    relations: scene.relations.map((relation) => renameRelationRefs(relation, oldName, clean)),
    annotations: scene.annotations.map((annotation) => renameAnnotationRefs(annotation, oldName, clean)),
  };
}

function renameObjectPointRefs(obj: SceneObject, oldName: string, newName: string): SceneObject {
  if (obj.type === 'segment') return { ...obj, points: obj.points.map((point) => point === oldName ? newName : point) as [string, string] };
  if (obj.type === 'line_2d' || obj.type === 'line_3d') return { ...obj, through: obj.through.map((point) => point === oldName ? newName : point) as [string, string] };
  if (obj.type === 'vector_2d' || obj.type === 'vector_3d') return { ...obj, from_point: obj.from_point === oldName ? newName : obj.from_point, to_point: obj.to_point === oldName ? newName : obj.to_point };
  if (obj.type === 'circle_2d') return { ...obj, center: obj.center === oldName ? newName : obj.center, through: obj.through === oldName ? newName : obj.through };
  if (obj.type === 'face' || obj.type === 'plane') return { ...obj, points: obj.points.map((point) => point === oldName ? newName : point) };
  if (obj.type === 'sphere') return { ...obj, center: obj.center === oldName ? newName : obj.center };
  return obj;
}

function renameRelationRefs(relation: Relation, oldName: string, newName: string): Relation {
  return {
    ...relation,
    object_1: replaceToken(relation.object_1, oldName, newName),
    object_2: relation.object_2 ? replaceToken(relation.object_2, oldName, newName) : relation.object_2,
    args: replaceUnknownTokens(relation.args, oldName, newName) as Record<string, unknown>,
    metadata: replaceUnknownTokens(relation.metadata, oldName, newName) as Record<string, unknown>,
  };
}

function renameAnnotationRefs(annotation: Annotation, oldName: string, newName: string): Annotation {
  return {
    ...annotation,
    target: replaceToken(annotation.target, oldName, newName),
    metadata: replaceUnknownTokens(annotation.metadata, oldName, newName) as Record<string, unknown>,
  };
}

function replaceToken(value: string, oldName: string, newName: string) {
  return value.replace(/[A-Za-z][A-Za-z0-9_]*/g, (token) => token === oldName ? newName : token);
}

function replaceUnknownTokens(value: unknown, oldName: string, newName: string): unknown {
  if (typeof value === 'string') return replaceToken(value, oldName, newName);
  if (Array.isArray(value)) return value.map((item) => replaceUnknownTokens(item, oldName, newName));
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, replaceUnknownTokens(item, oldName, newName)]));
  }
  return value;
}

function nextAvailableName(used: string[], base: string) {
  if (!used.includes(base)) return base;
  let index = 1;
  while (used.includes(`${base}${index}`)) index += 1;
  return `${base}${index}`;
}

function buildContextActions(scene: MathScene, items: TreeItem[]): ContextAction[] {
  if (items.length !== 2 || items.some((item) => item.kind !== 'object')) return [];
  const objects = items.map((item) => scene.objects[item.index]);
  const point = objects.find(isPoint);
  const line = objects.find(isLineLike);
  const plane = objects.find(isPlane);
  const [first, second] = objects;

  if (isPoint(first) && isPoint(second)) {
    return [
      { id: 'segment', label: 'Tạo đoạn', run: () => addSegmentBetweenPoints(scene, first.name, second.name) },
      { id: 'line', label: 'Tạo đường', run: () => addLineThroughPoints(scene, first.name, second.name) },
      { id: 'vector', label: 'Tạo vector', run: () => addVectorBetweenPoints(scene, first.name, second.name) },
      { id: 'midpoint', label: 'Trung điểm', run: () => addMidpoint(scene, first.name, second.name) },
      { id: 'distance', label: 'Đo khoảng cách', run: () => addPointDistance(scene, first.name, second.name) },
    ];
  }

  if (point && line) {
    const lineInfo = lineLike(scene, line);
    if (!lineInfo) return [];
    const actions: ContextAction[] = [
      { id: 'project-line', label: 'Hình chiếu lên đường', run: () => addPointLineProjection(scene, point.name, lineInfo, false, false) },
      { id: 'parallel-line', label: 'Đường song song', run: () => addParallelLine(scene, point.name, lineInfo) },
      { id: 'perpendicular-line', label: 'Đường vuông góc', run: () => addPerpendicularLine(scene, point.name, lineInfo) },
      { id: 'distance-line', label: 'Khoảng cách', run: () => addPointLineProjection(scene, point.name, lineInfo, false, true) },
    ];
    if (lineInfo.segment) actions.splice(1, 0, { id: 'project-segment', label: 'Hình chiếu lên đoạn', run: () => addPointLineProjection(scene, point.name, lineInfo, true, false) });
    return actions;
  }

  if (point && plane) {
    return [
      { id: 'project-plane', label: 'Hình chiếu', run: () => addPointPlaneProjection(scene, point.name, plane, false, false) },
      { id: 'perpendicular-plane', label: 'Đường vuông góc', run: () => addPointPlaneProjection(scene, point.name, plane, true, false) },
      { id: 'parallel-plane', label: 'Mặt phẳng song song', run: () => addParallelPlane(scene, point.name, plane) },
      { id: 'distance-plane', label: 'Khoảng cách', run: () => addPointPlaneProjection(scene, point.name, plane, true, true) },
    ];
  }

  if (isLineLike(first) && isLineLike(second)) {
    const a = lineLike(scene, first);
    const b = lineLike(scene, second);
    if (!a || !b) return [];
    return [
      { id: 'intersection', label: 'Giao điểm', run: () => addLineIntersection(scene, a, b) },
      { id: 'angle', label: 'Góc', run: () => addLineAngle(scene, a, b) },
      { id: 'skew-distance', label: 'Khoảng cách chéo nhau', run: () => addLineDistance(scene, a, b) },
      { id: 'check-parallel', label: 'Kiểm tra song song', run: () => addLineCheck(scene, a, b, 'parallel') },
      { id: 'check-perpendicular', label: 'Kiểm tra vuông góc', run: () => addLineCheck(scene, a, b, 'perpendicular') },
    ];
  }

  return [];
}

type LineInfo = { points: [string, string]; label: string; segment: boolean; direction: Vec3; a: Vec3; b: Vec3 };

function isPoint(obj: SceneObject): obj is Point2D | Point3D {
  return obj.type === 'point_2d' || obj.type === 'point_3d';
}

function isLineLike(obj: SceneObject): obj is Line2D | Line3D | Segment {
  return obj.type === 'line_2d' || obj.type === 'line_3d' || obj.type === 'segment';
}

function isPlane(obj: SceneObject): obj is Plane {
  return obj.type === 'plane';
}

function pointVec(scene: MathScene, name: string): Vec3 | null {
  const point = scene.objects.find((obj): obj is Point2D | Point3D => isPoint(obj) && obj.name === name);
  if (!point) return null;
  return point.type === 'point_3d' ? { x: point.x, y: point.y, z: point.z } : { x: point.x, y: point.y, z: 0 };
}

function lineLike(scene: MathScene, obj: Line2D | Line3D | Segment): LineInfo | null {
  const points = obj.type === 'segment' ? obj.points : obj.through;
  const a = pointVec(scene, points[0]);
  const b = pointVec(scene, points[1]);
  if (!a || !b) return null;
  const direction = normalize(sub(b, a));
  if (length(direction) < 1e-9) return null;
  return { points, label: objectName(obj) ?? edgeKey(points), segment: obj.type === 'segment', direction, a, b };
}

function addSegmentBetweenPoints(scene: MathScene, a: string, b: string): MathScene | null {
  if (a === b) return null;
  return { ...scene, objects: [...scene.objects, makeSegment(a, b)] };
}

function addLineThroughPoints(scene: MathScene, a: string, b: string): MathScene | null {
  if (a === b) return null;
  return { ...scene, objects: [...scene.objects, makeLine(scene, nextObjectName(scene, 'l'), a, b)] };
}

function addVectorBetweenPoints(scene: MathScene, a: string, b: string): MathScene | null {
  if (a === b) return null;
  return { ...scene, objects: [...scene.objects, makeVector(scene, nextObjectName(scene, 'v'), a, b)] };
}

function addMidpoint(scene: MathScene, aName: string, bName: string): MathScene | null {
  const a = pointVec(scene, aName);
  const b = pointVec(scene, bName);
  if (!a || !b) return null;
  const name = nextObjectName(scene, 'M');
  return {
    ...scene,
    objects: [...scene.objects, makePoint(scene, name, midpoint(a, b), { constructed_by: 'midpoint', points: [aName, bName] })],
    relations: [...scene.relations, makeRelation('midpoint', name, edgeKey([aName, bName]), { points: [aName, bName] })],
  };
}

function addPointDistance(scene: MathScene, a: string, b: string): MathScene | null {
  const pa = pointVec(scene, a);
  const pb = pointVec(scene, b);
  if (!pa || !pb) return null;
  return { ...scene, annotations: [...scene.annotations, makeLengthAnnotation(edgeKey([a, b]), distance(pa, pb), { measured_by: 'context_tool' })] };
}

function addPointLineProjection(scene: MathScene, pointName: string, line: LineInfo, clamp: boolean, withDistance: boolean): MathScene | null {
  const point = pointVec(scene, pointName);
  if (!point) return null;
  const projection = projectPointToLine(point, line.a, line.b, clamp);
  const footName = nextObjectName(scene, 'H');
  const target = edgeKey(line.points);
  const foot = makePoint(scene, footName, projection.point, { constructed_by: clamp ? 'project_to_segment' : 'project_to_line', source_point: pointName, target });
  const connector = makeSegment(pointName, footName, { style: 'dashed' });
  const annotations = withDistance ? [makeLengthAnnotation(edgeKey([pointName, footName]), distance(point, projection.point), { measured_by: 'context_tool', target })] : [];
  return {
    ...scene,
    objects: [...scene.objects, foot, connector],
    relations: [
      ...scene.relations,
      makeRelation('on_line', footName, line.label, { t: projection.t, target }),
      makeRelation('perpendicular', edgeKey([pointName, footName]), line.label, { target }),
    ],
    annotations: [...scene.annotations, ...annotations],
  };
}

function addParallelLine(scene: MathScene, pointName: string, line: LineInfo): MathScene | null {
  const point = pointVec(scene, pointName);
  if (!point) return null;
  const helperName = nextObjectName(scene, 'P');
  const helper = makePoint(scene, helperName, add(point, line.direction), { constructed_by: 'parallel_line', target: line.label }, true);
  return {
    ...scene,
    objects: [...scene.objects, helper, makeLine(scene, nextObjectName(scene, 'l'), pointName, helperName)],
    relations: [...scene.relations, makeRelation('parallel', edgeKey([pointName, helperName]), line.label, { target: line.label })],
  };
}

function addPerpendicularLine(scene: MathScene, pointName: string, line: LineInfo): MathScene | null {
  const point = pointVec(scene, pointName);
  if (!point) return null;
  const projection = projectPointToLine(point, line.a, line.b, false).point;
  const fromProjection = sub(projection, point);
  const direction = length(fromProjection) > 1e-9
    ? normalize(fromProjection)
    : (scene.view.dimension === '2d' ? normalize({ x: -line.direction.y, y: line.direction.x, z: 0 }) : perpendicularAxis(line.direction));
  const helperName = nextObjectName(scene, 'P');
  const helper = makePoint(scene, helperName, add(point, direction), { constructed_by: 'perpendicular_line', target: line.label }, true);
  return {
    ...scene,
    objects: [...scene.objects, helper, makeLine(scene, nextObjectName(scene, 'l'), pointName, helperName)],
    relations: [...scene.relations, makeRelation('perpendicular', edgeKey([pointName, helperName]), line.label, { target: line.label })],
  };
}

function addPointPlaneProjection(scene: MathScene, pointName: string, plane: Plane, withLine: boolean, withDistance: boolean): MathScene | null {
  const point = pointVec(scene, pointName);
  const basis = planeBasis(scene, plane);
  if (!point || !basis) return null;
  const signed = dot(sub(point, basis.origin), basis.normal);
  const footPoint = sub(point, scale(basis.normal, signed));
  const footName = nextObjectName(scene, 'H');
  const target = objectName(plane) ?? plane.points.join('');
  const objects: SceneObject[] = [makePoint(scene, footName, footPoint, { constructed_by: 'project_to_plane', source_point: pointName, target })];
  const annotations: Annotation[] = [];
  if (withLine || withDistance) objects.push(makeSegment(pointName, footName, { style: 'dashed' }));
  if (withDistance) annotations.push(makeLengthAnnotation(edgeKey([pointName, footName]), Math.abs(signed), { measured_by: 'context_tool', target }));
  return {
    ...scene,
    objects: [...scene.objects, ...objects],
    relations: [...scene.relations, makeRelation('perpendicular', edgeKey([pointName, footName]), target, { target })],
    annotations: [...scene.annotations, ...annotations],
  };
}

function addParallelPlane(scene: MathScene, pointName: string, plane: Plane): MathScene | null {
  const point = pointVec(scene, pointName);
  const basis = planeBasis(scene, plane);
  if (!point || !basis) return null;
  const aName = nextObjectName(scene, 'P');
  const bName = nextObjectName({ ...scene, objects: [...scene.objects, makePoint(scene, aName, point, {}, true)] }, 'P');
  const target = objectName(plane) ?? plane.points.join('');
  const helpers = [
    makePoint(scene, aName, add(point, basis.u), { constructed_by: 'parallel_plane', target }, true),
    makePoint(scene, bName, add(point, basis.v), { constructed_by: 'parallel_plane', target }, true),
  ];
  const newPlane: Plane = { type: 'plane', name: nextObjectName(scene, 'mp'), points: [pointName, aName, bName], color: plane.color, opacity: plane.opacity, show_normal: false, source: 'construction', metadata: { constructed_by: 'parallel_plane', target } };
  return { ...scene, objects: [...scene.objects, ...helpers, newPlane], relations: [...scene.relations, makeRelation('parallel', newPlane.name ?? 'mp', target, { target })] };
}

function addLineIntersection(scene: MathScene, a: LineInfo, b: LineInfo): MathScene | null {
  const closest = closestLinePoints(a, b);
  if (!closest || closest.parallel || distance(closest.p, closest.q) > 1e-6) return null;
  return { ...scene, objects: [...scene.objects, makePoint(scene, nextObjectName(scene, 'I'), midpoint(closest.p, closest.q), { constructed_by: 'line_intersection', lines: [a.label, b.label] })] };
}

function addLineAngle(scene: MathScene, a: LineInfo, b: LineInfo): MathScene | null {
  const closest = closestLinePoints(a, b);
  if (!closest) return null;
  const vertexName = nextObjectName(scene, 'V');
  const armA = nextObjectName({ ...scene, objects: [...scene.objects, makePoint(scene, vertexName, closest.p, {}, true)] }, 'P');
  const armB = nextObjectName({ ...scene, objects: [...scene.objects, makePoint(scene, vertexName, closest.p, {}, true), makePoint(scene, armA, closest.p, {}, true)] }, 'P');
  const vertex = midpoint(closest.p, closest.q);
  const angle = angleBetween(a.direction, b.direction);
  return {
    ...scene,
    objects: [
      ...scene.objects,
      makePoint(scene, vertexName, vertex, { constructed_by: 'line_angle', lines: [a.label, b.label] }, true),
      makePoint(scene, armA, add(vertex, a.direction), { constructed_by: 'line_angle_arm' }, true),
      makePoint(scene, armB, add(vertex, b.direction), { constructed_by: 'line_angle_arm' }, true),
    ],
    annotations: [...scene.annotations, { type: 'angle', target: vertexName, label: `${formatNumber(angle)}°`, source: 'construction', color: '#b45309', metadata: { arms: [armA, armB], measured_by: 'context_tool' } }],
  };
}

function addLineDistance(scene: MathScene, a: LineInfo, b: LineInfo): MathScene | null {
  const closest = closestLinePoints(a, b);
  if (!closest) return null;
  const firstName = nextObjectName(scene, 'D');
  const secondName = nextObjectName({ ...scene, objects: [...scene.objects, makePoint(scene, firstName, closest.p, {}, true)] }, 'D');
  const dist = distance(closest.p, closest.q);
  return {
    ...scene,
    objects: [...scene.objects, makePoint(scene, firstName, closest.p, { constructed_by: 'line_distance' }, true), makePoint(scene, secondName, closest.q, { constructed_by: 'line_distance' }, true), makeSegment(firstName, secondName, { style: 'dashed' })],
    annotations: [...scene.annotations, makeLengthAnnotation(edgeKey([firstName, secondName]), dist, { measured_by: 'context_tool', lines: [a.label, b.label] })],
  };
}

function addLineCheck(scene: MathScene, a: LineInfo, b: LineInfo, type: 'parallel' | 'perpendicular'): MathScene {
  const crossLen = length(cross(a.direction, b.direction));
  const dotAbs = Math.abs(dot(a.direction, b.direction));
  const passed = type === 'parallel' ? crossLen < 1e-6 : dotAbs < 1e-6;
  const evidence = type === 'parallel' ? `cross=${formatNumber(crossLen)}` : `dot=${formatNumber(dotAbs)}`;
  return { ...scene, relations: [...scene.relations, makeRelation(type, a.label, b.label, { checked_by: 'context_tool', passed, evidence }, passed)] };
}

function makePoint(scene: MathScene, name: string, point: Vec3, metadata: Record<string, unknown> = {}, hidden = false): Point2D | Point3D {
  const base = { name, source: 'construction' as const, metadata: hidden ? { ...metadata, tree_hidden: true } : metadata };
  return scene.view.dimension === '3d'
    ? { ...base, type: 'point_3d', x: round(point.x), y: round(point.y), z: round(point.z) }
    : { ...base, type: 'point_2d', x: round(point.x), y: round(point.y) };
}

function makeSegment(a: string, b: string, options: { style?: 'solid' | 'dashed' | 'dotted' } = {}): Segment {
  return { type: 'segment', points: [a, b], hidden: false, color: '#111111', line_width: 3, style: options.style ?? 'solid', source: 'construction', metadata: { constructed_by: 'context_tool' } };
}

function makeLine(scene: MathScene, name: string, a: string, b: string): Line2D | Line3D {
  return scene.view.dimension === '3d'
    ? { type: 'line_3d', name, through: [a, b], color: '#334155', source: 'construction', metadata: { constructed_by: 'context_tool' } }
    : { type: 'line_2d', name, through: [a, b], source: 'construction', metadata: { constructed_by: 'context_tool' } };
}

function makeVector(scene: MathScene, name: string, a: string, b: string): SceneObject {
  return scene.view.dimension === '3d'
    ? { type: 'vector_3d', name, from_point: a, to_point: b, color: '#525252', source: 'construction', metadata: { constructed_by: 'context_tool' } }
    : { type: 'vector_2d', name, from_point: a, to_point: b, source: 'construction', metadata: { constructed_by: 'context_tool' } };
}

function makeRelation(type: string, object1: string, object2: string, metadata: Record<string, unknown>, verified?: boolean): Relation {
  const relationId = `${type}:${object1}:${object2}:${Date.now()}`;
  return {
    id: relationId,
    type,
    object_1: object1,
    object_2: object2,
    source: 'construction',
    args: metadata,
    metadata,
    verification: verified == null ? null : {
      relation_id: relationId,
      status: verified ? 'verified' : 'failed',
      method: 'numeric_scene_context',
      evidence: String(metadata.evidence ?? ''),
      message: verified ? 'Đúng theo tọa độ hiện tại.' : 'Không đúng theo tọa độ hiện tại.',
      verifier_version: 'frontend-context-tools',
      metadata,
    },
  };
}

function makeLengthAnnotation(target: string, value: number, metadata: Record<string, unknown>): Annotation {
  return { type: 'length', target, label: formatNumber(value), source: 'construction', color: '#7c3aed', metadata };
}

function nextObjectName(scene: MathScene, base: string): string {
  return nextAvailableName(scene.objects.map(objectName).filter(Boolean) as string[], base);
}

function planeBasis(scene: MathScene, plane: Plane): { origin: Vec3; normal: Vec3; u: Vec3; v: Vec3 } | null {
  const points = plane.points.map((name) => pointVec(scene, name)).filter(Boolean) as Vec3[];
  if (points.length < 3) return null;
  const normal = normalize(cross(sub(points[1], points[0]), sub(points[2], points[0])));
  if (length(normal) < 1e-9) return null;
  const u = normalize(sub(points[1], points[0]));
  const v = normalize(cross(normal, u));
  if (length(u) < 1e-9 || length(v) < 1e-9) return null;
  return { origin: points[0], normal, u, v };
}

function projectPointToLine(point: Vec3, a: Vec3, b: Vec3, clamp: boolean) {
  const ab = sub(b, a);
  const denom = dot(ab, ab);
  const rawT = denom < 1e-12 ? 0 : dot(sub(point, a), ab) / denom;
  const t = clamp ? Math.max(0, Math.min(1, rawT)) : rawT;
  return { point: add(a, scale(ab, t)), t };
}

function closestLinePoints(a: LineInfo, b: LineInfo): { p: Vec3; q: Vec3; parallel: boolean } | null {
  const p13 = sub(a.a, b.a);
  const d1343 = dot(p13, b.direction);
  const d4321 = dot(b.direction, a.direction);
  const d1321 = dot(p13, a.direction);
  const d4343 = dot(b.direction, b.direction);
  const d2121 = dot(a.direction, a.direction);
  const denom = d2121 * d4343 - d4321 * d4321;
  if (Math.abs(denom) < 1e-9) {
    const projected = projectPointToLine(a.a, b.a, b.b, false).point;
    return { p: a.a, q: projected, parallel: true };
  }
  const numer = d1343 * d4321 - d1321 * d4343;
  const mua = numer / denom;
  const mub = (d1343 + d4321 * mua) / d4343;
  return { p: add(a.a, scale(a.direction, mua)), q: add(b.a, scale(b.direction, mub)), parallel: false };
}

function angleBetween(a: Vec3, b: Vec3): number {
  const cosine = Math.max(-1, Math.min(1, Math.abs(dot(normalize(a), normalize(b)))));
  return Math.acos(cosine) * 180 / Math.PI;
}

function distance(a: Vec3, b: Vec3): number {
  return length(sub(a, b));
}

function midpoint(a: Vec3, b: Vec3): Vec3 {
  return scale(add(a, b), 0.5);
}

function add(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z };
}

function sub(a: Vec3, b: Vec3): Vec3 {
  return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
}

function scale(a: Vec3, factor: number): Vec3 {
  return { x: a.x * factor, y: a.y * factor, z: a.z * factor };
}

function dot(a: Vec3, b: Vec3): number {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

function cross(a: Vec3, b: Vec3): Vec3 {
  return { x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x };
}

function length(a: Vec3): number {
  return Math.hypot(a.x, a.y, a.z);
}

function normalize(a: Vec3): Vec3 {
  const size = length(a);
  return size < 1e-12 ? { x: 0, y: 0, z: 0 } : scale(a, 1 / size);
}

function perpendicularAxis(direction: Vec3): Vec3 {
  const axis = Math.abs(direction.y) < 0.9 ? { x: 0, y: 1, z: 0 } : { x: 1, y: 0, z: 0 };
  return normalize(cross(direction, axis));
}

function round(value: number): number {
  return Math.round(value * 1_000_000) / 1_000_000;
}

function formatNumber(value: number): string {
  return String(Math.round(value * 1000) / 1000).replace(/\.0+$/, '');
}

function sourceLabel(value: SourceFilter) {
  if (value === 'all') return 'Tất cả';
  return value;
}

function verificationLabel(value: VerificationFilter) {
  if (value === 'all') return 'Tất cả';
  if (value === 'none') return 'Chưa có';
  return value;
}