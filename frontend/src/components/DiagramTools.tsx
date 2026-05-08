import React, { useRef, useState } from 'react';
import { diagramOcr, generateProblemVariants } from '../api/client';
import type { MathScene } from '../types/scene';
import type { RuntimeSettings } from '../types/settings';

export interface DiagramToolsProps {
  scene: MathScene | null;
  originalProblem: string;
  runtimeSettings: RuntimeSettings;
  onDiagramRecognized: (description: string) => void;
  onError?: (message: string) => void;
}

const VARIANT_OPTIONS = [2, 3, 5];

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error('Không đọc được ảnh.'));
    reader.readAsDataURL(file);
  });
}

export function DiagramTools(props: DiagramToolsProps): JSX.Element {
  const { scene, originalProblem, runtimeSettings, onDiagramRecognized, onError } = props;
  const [busyOcr, setBusyOcr] = useState(false);
  const [busyVariants, setBusyVariants] = useState<number | null>(null);
  const [variants, setVariants] = useState<string[]>([]);
  const [variantsModel, setVariantsModel] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function handleFile(file: File) {
    setBusyOcr(true);
    try {
      const dataUrl = await fileToDataUrl(file);
      const res = await diagramOcr(dataUrl, runtimeSettings);
      onDiagramRecognized(res.description);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Lỗi không xác định.');
    } finally {
      setBusyOcr(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function handleGenerateVariants(count: number) {
    if (!scene) return;
    setBusyVariants(count);
    try {
      const res = await generateProblemVariants(scene, count, originalProblem || undefined, runtimeSettings);
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
    <div className="diagram-tools">
      <div className="diagram-tools-row">
        <div className="diagram-tools-block">
          <h4 className="diagram-tools-title">Quét hình vẽ → đề bài</h4>
          <p className="diagram-tools-hint">
            Tải ảnh hình vẽ tay/in. AI sẽ mô tả lại thành đề bài để dựng hình.
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            style={{ display: 'none' }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void handleFile(file);
            }}
          />
          <button
            type="button"
            className="diagram-tools-button primary"
            disabled={busyOcr}
            onClick={() => fileInputRef.current?.click()}
          >
            {busyOcr ? 'Đang nhận diện hình…' : 'Chọn ảnh hình vẽ'}
          </button>
        </div>

        <div className="diagram-tools-block">
          <h4 className="diagram-tools-title">Sinh đề biến thể</h4>
          <p className="diagram-tools-hint">
            Giữ nguyên cấu trúc hình, đổi tên điểm và số liệu — mỗi học sinh một đề khác.
          </p>
          <div className="diagram-tools-button-row">
            {VARIANT_OPTIONS.map((count) => (
              <button
                key={count}
                type="button"
                className="diagram-tools-button"
                disabled={!scene || busyVariants !== null}
                onClick={() => handleGenerateVariants(count)}
                title={!scene ? 'Cần có hình đã dựng trước' : `Sinh ${count} đề biến thể`}
              >
                {busyVariants === count ? `Đang sinh ${count}…` : `Sinh ${count} đề`}
              </button>
            ))}
          </div>
        </div>
      </div>

      {variants.length > 0 && (
        <div className="diagram-tools-variants">
          <div className="diagram-tools-variants-header">
            <span>Đã sinh {variants.length} đề biến thể{variantsModel ? ` (${variantsModel})` : ''}</span>
            <button type="button" className="link-button" onClick={() => setVariants([])}>
              Xoá danh sách
            </button>
          </div>
          <ol className="diagram-tools-variants-list">
            {variants.map((text, idx) => (
              <li key={idx} className="diagram-tools-variant-item">
                <p>{text}</p>
                <button type="button" className="link-button" onClick={() => copyVariant(text, idx)}>
                  Copy đề {idx + 1}
                </button>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

export default DiagramTools;
