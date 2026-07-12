import React, { useState } from 'react';
import { generateProblemVariants } from '../api/client';
import { committedSceneRefV3, downstreamGateMessageV3 } from '../hooks/sceneWorkspaceV3State';
import type { SceneWorkspaceResponseV3 } from '../types/sceneV3';
import type { RuntimeSettings } from '../types/settings';

export interface DiagramToolsProps {
  workspace: SceneWorkspaceResponseV3 | null;
  originalProblem: string;
  runtimeSettings: RuntimeSettings;
  onError?: (message: string) => void;
}

const VARIANT_OPTIONS = [2, 3, 5];

export function ProblemVariantTool({ workspace, originalProblem, runtimeSettings, onError }: DiagramToolsProps): JSX.Element {
  const [busyVariants, setBusyVariants] = useState<number | null>(null);
  const [variants, setVariants] = useState<string[]>([]);
  const [variantsModel, setVariantsModel] = useState<string | null>(null);
  const gateMessage = workspace ? downstreamGateMessageV3(workspace, 'sinh đề biến thể') : null;

  async function handleGenerateVariants(count: number) {
    if (!workspace || gateMessage) return;
    setBusyVariants(count);
    try {
      const res = await generateProblemVariants(
        committedSceneRefV3(workspace),
        count,
        originalProblem || undefined,
        runtimeSettings,
      );
      setVariants(res.variants);
      setVariantsModel(`${res.provider}/${res.model}`);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Lỗi không xác định.');
    } finally {
      setBusyVariants(null);
    }
  }

  async function copyVariant(text: string, index: number) {
    try {
      await navigator.clipboard.writeText(text);
      onError?.(`Đã copy đề ${index + 1} vào clipboard.`);
    } catch {
      onError?.('Trình duyệt không cho phép copy clipboard.');
    }
  }

  return (
    <div className="diagram-tools-block">
      <p className="diagram-tools-hint">Giữ nguyên cấu trúc hình, đổi tên điểm và số liệu.</p>
      {gateMessage && <p className="diagram-tools-hint warning">{gateMessage}</p>}
      <div className="diagram-tools-button-row">
        {VARIANT_OPTIONS.map((count) => (
          <button key={count} type="button" className="diagram-tools-button" disabled={!workspace || Boolean(gateMessage) || busyVariants !== null} onClick={() => handleGenerateVariants(count)} title={!workspace ? 'Cần có hình đã dựng trước' : gateMessage ?? `Sinh ${count} đề biến thể`}>
            {busyVariants === count ? `Đang sinh ${count}…` : `Sinh ${count} đề`}
          </button>
        ))}
      </div>
      {variants.length > 0 && (
        <div className="diagram-tools-variants">
          <div className="diagram-tools-variants-header">
            <span>Đã sinh {variants.length} đề biến thể{variantsModel ? ` (${variantsModel})` : ''}</span>
            <button type="button" className="link-button" onClick={() => setVariants([])}>Xoá danh sách</button>
          </div>
          <ol className="diagram-tools-variants-list">
            {variants.map((text, idx) => (
              <li key={idx} className="diagram-tools-variant-item">
                <p>{text}</p>
                <button type="button" className="link-button" onClick={() => copyVariant(text, idx)}>Copy đề {idx + 1}</button>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

export function DiagramTools(props: DiagramToolsProps): JSX.Element {
  return (
    <div className="diagram-tools">
      <div className="diagram-tools-row">
        <ProblemVariantTool workspace={props.workspace} originalProblem={props.originalProblem} runtimeSettings={props.runtimeSettings} onError={props.onError} />
      </div>
    </div>
  );
}

export default DiagramTools;
