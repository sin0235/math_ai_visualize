import { useMemo, useState } from 'react';

import type { SceneWorkspaceResponseV3 } from '../types/sceneV3';
import { relationDependenciesV3 } from './sceneInspectorV3State';

type InspectorTab = 'objects' | 'verification';

interface SceneInspectorV3Props {
  response: SceneWorkspaceResponseV3;
  saving: boolean;
  highlightedObjectIds: string[];
  onHighlight: (objectIds: string[]) => void;
  onSetVisibility: (objectId: string, visible: boolean) => void;
  onDelete: (objectId: string) => void;
  onUndo: () => void;
}

export function SceneInspectorV3({
  response,
  saving,
  highlightedObjectIds,
  onHighlight,
  onSetVisibility,
  onDelete,
  onUndo,
}: SceneInspectorV3Props) {
  const [tab, setTab] = useState<InspectorTab>('objects');
  const [deleteProposalId, setDeleteProposalId] = useState<string | null>(null);
  const dependencies = useMemo(() => relationDependenciesV3(response), [response]);

  return (
    <div className="scene-inspector-v3">
      <div className="scene-editor-tabs" role="tablist" aria-label="Dữ liệu scene v3">
        <button type="button" role="tab" aria-selected={tab === 'objects'} className={tab === 'objects' ? 'active' : ''} onClick={() => setTab('objects')}>Đối tượng</button>
        <button type="button" role="tab" aria-selected={tab === 'verification'} className={tab === 'verification' ? 'active' : ''} onClick={() => setTab('verification')}>Kiểm chứng ({response.verification.length})</button>
      </div>

      {tab === 'objects' && (
        <div className="scene-inspector-v3-list">
          {response.scene.objects.map((object) => {
            const hidden = Boolean(object.metadata.tree_hidden);
            const selected = highlightedObjectIds.includes(object.id);
            return (
              <article key={object.id} className={`scene-inspector-v3-object ${selected ? 'selected' : ''}`}>
                <button type="button" className="scene-inspector-v3-object-main" onClick={() => onHighlight(selected ? [] : [object.id])}>
                  <span><strong>{object.label || object.id}</strong><small>{object.type}</small></span>
                  <code>{object.id}</code>
                </button>
                <dl>
                  <div><dt>Nguồn</dt><dd>{object.source}</dd></div>
                  <div><dt>Khóa</dt><dd>{object.locked ? 'Có' : 'Không'}</dd></div>
                  <div><dt>Ràng buộc</dt><dd>{dependencies.get(object.id)?.join(', ') || 'Không'}</dd></div>
                </dl>
                <div className="scene-inspector-v3-actions">
                  <button type="button" className="secondary-button" disabled={saving} onClick={() => onSetVisibility(object.id, hidden)}>{hidden ? 'Hiện' : 'Ẩn'}</button>
                  {!object.locked && deleteProposalId !== object.id && <button type="button" className="secondary-button" disabled={saving} onClick={() => setDeleteProposalId(object.id)}>Đề xuất xóa</button>}
                </div>
                {deleteProposalId === object.id && (
                  <div className="warning-box scene-inspector-v3-proposal">
                    <span>Xóa bị backend chặn nếu object còn dependency.</span>
                    <div>
                      <button type="button" disabled={saving} onClick={() => { setDeleteProposalId(null); onDelete(object.id); }}>Áp dụng đề xuất</button>
                      <button type="button" className="secondary-button" onClick={() => setDeleteProposalId(null)}>Hủy</button>
                    </div>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}

      {tab === 'verification' && (
        <div className="scene-inspector-v3-list">
          {response.verification.length === 0 && <div className="empty-state">Scene không có relation cần kiểm chứng.</div>}
          {response.verification.map((result) => {
            const relation = response.scene.relations.find((item) => item.id === result.relation_id);
            const objectIds = relation?.operands.map((operand) => operand.ref_id) ?? [];
            return (
              <article key={result.relation_id} className={`scene-inspector-v3-verification status-${result.status}`}>
                <button type="button" className="scene-inspector-v3-object-main" onClick={() => onHighlight(objectIds)}>
                  <span><strong>{relation?.type || result.relation_id}</strong><small>{result.status}</small></span>
                  <code>{result.relation_id}</code>
                </button>
                {result.message && <p>{result.message}</p>}
                <dl>
                  <div><dt>Verifier</dt><dd>{result.verifier}</dd></div>
                  {result.residual != null && <div><dt>Residual</dt><dd>{result.residual}</dd></div>}
                  {result.tolerance != null && <div><dt>Tolerance</dt><dd>{result.tolerance}</dd></div>}
                </dl>
                {Object.keys(result.evidence).length > 0 && <details><summary>Evidence</summary><pre>{JSON.stringify(result.evidence, null, 2)}</pre></details>}
                {result.status !== 'verified' && <button type="button" className="secondary-button" disabled={saving} onClick={onUndo}>Hoàn tác chỉnh sửa gần nhất</button>}
              </article>
            );
          })}
          {response.issues.map((issue, index) => (
            <article key={`${issue.code}:${issue.target_id || index}`} className={`scene-inspector-v3-issue severity-${issue.severity}`}>
              <strong>{issue.code}</strong>
              <span>{issue.message}</span>
              <small>{issue.stage}{issue.target_id ? ` · ${issue.target_id}` : ''}</small>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}