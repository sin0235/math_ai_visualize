import { useMemo, useState } from 'react';

import { scanRouter9Models } from '../api/client';
import type { RuntimeSettings, ScannedModelInfo, SettingsDefaults } from '../types/settings';

interface Router9SettingsPanelProps {
  value: RuntimeSettings;
  defaults: SettingsDefaults | null;
  onChange: (next: RuntimeSettings) => void;
  onForgetApiKeys: () => void;
}

export function Router9SettingsPanel({ value, defaults, onChange, onForgetApiKeys }: Router9SettingsPanelProps) {
  const [scanError, setScanError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [query, setQuery] = useState('');
  const router9 = value.router9;
  const selected = new Set(router9.allowed_model_ids);
  const filteredModels = useMemo(() => {
    const text = query.trim().toLowerCase();
    if (!text) return router9.scanned_models;
    return router9.scanned_models.filter((model) => model.id.toLowerCase().includes(text) || model.label.toLowerCase().includes(text));
  }, [query, router9.scanned_models]);

  function updateRouter9(next: Partial<RuntimeSettings['router9']>) {
    onChange({ ...value, router9: { ...router9, ...next } });
  }

  async function scanModels() {
    setScanning(true);
    setScanError(null);
    try {
      const models = await scanRouter9Models(value);
      const availableIds = new Set(models.map((model) => model.id));
      const preferredRenderIds = selectRouter9RenderModelIds(models);
      const preferredOcrIds = selectRouter9OcrModelIds(models);
      const allowed_model_ids = mergeUnique([
        ...router9.allowed_model_ids.filter((id) => availableIds.has(id)),
        ...preferredOcrIds,
        ...preferredRenderIds,
      ]);
      onChange({
        ...value,
        ocr: preferredOcrIds.length > 0 ? { ...value.ocr, provider: 'router9', model: '' } : value.ocr,
        router9: {
          ...router9,
          scanned_models: models,
          allowed_model_ids,
          model: preferredRenderIds[0] ?? (availableIds.has(router9.model) ? router9.model : allowed_model_ids[0] ?? ''),
          last_scanned_at: new Date().toISOString(),
        },
      });
    } catch (caught) {
      setScanError(caught instanceof Error ? caught.message : 'Không thể quét model 9router.');
    } finally {
      setScanning(false);
    }
  }

  function toggleModel(modelId: string) {
    const nextSelected = new Set(router9.allowed_model_ids);
    if (nextSelected.has(modelId)) {
      nextSelected.delete(modelId);
    } else {
      nextSelected.add(modelId);
    }
    const allowed_model_ids = [...nextSelected];
    updateRouter9({
      allowed_model_ids,
      model: allowed_model_ids.includes(router9.model) ? router9.model : allowed_model_ids[0] ?? '',
    });
  }

  function selectFilteredModels() {
    const nextSelected = new Set(router9.allowed_model_ids);
    filteredModels.forEach((model) => nextSelected.add(model.id));
    const allowed_model_ids = [...nextSelected];
    updateRouter9({ allowed_model_ids, model: router9.model || allowed_model_ids[0] || '' });
  }

  function clearFilteredModels() {
    const filteredIds = new Set(filteredModels.map((model) => model.id));
    const allowed_model_ids = router9.allowed_model_ids.filter((id) => !filteredIds.has(id));
    updateRouter9({
      allowed_model_ids,
      model: allowed_model_ids.includes(router9.model) ? router9.model : allowed_model_ids[0] ?? '',
    });
  }

  return (
    <section className="settings-layout router9-page">
      <div className="panel settings-hero">
        <div className="panel-title">9router</div>
        <p className="field-hint">Quét model từ endpoint OpenAI-compatible của 9router, chọn model hiển thị trong trang dựng hình, và bật chế độ chỉ dùng 9router nếu cần.</p>
      </div>

      <div className="settings-grid">
        <section className="panel settings-section">
          <div className="panel-title">Kết nối 9router</div>
          <label className="field-label">
            API key override
            <input type="password" value={router9.api_key} onChange={(event) => updateRouter9({ api_key: event.target.value })} placeholder={defaults?.router9.api_key_configured ? 'Configured in backend .env' : 'Nhập API key nếu muốn override'} autoComplete="off" />
          </label>
          <label className="field-label">
            Base URL override
            <input type="url" value={router9.base_url} onChange={(event) => updateRouter9({ base_url: event.target.value })} placeholder={defaults?.router9.base_url || 'Backend default'} />
          </label>
          <label className="checkbox-label settings-checkbox">
            <input type="checkbox" checked={router9.only_mode} onChange={(event) => updateRouter9({ only_mode: event.target.checked })} />
            9router only: chỉ hiển thị và chỉ gọi các model 9router đã chọn
          </label>
          <button type="button" className="secondary-button" onClick={scanModels} disabled={scanning}>
            {scanning ? 'Đang quét...' : 'Quét model khả dụng'}
          </button>
          <button type="button" className="secondary-button" onClick={onForgetApiKeys}>Quên tất cả API key override</button>
          <p className="field-hint">API key override chỉ giữ trong state của tab hiện tại và sẽ mất khi refresh. Để trống field override để backend dùng `.env`/default.</p>
          {scanError && <div className="error-box">{scanError}</div>}
          {router9.last_scanned_at && <p className="field-hint">Lần quét gần nhất: {new Date(router9.last_scanned_at).toLocaleString()}</p>}
        </section>

        <section className="panel settings-section">
          <div className="panel-title">Model hiển thị trong web render hình</div>
          <p className="field-hint">Đã chọn {router9.allowed_model_ids.length}/{router9.scanned_models.length} model.</p>
          <label className="field-label">
            Model mặc định
            <select value={router9.model} onChange={(event) => updateRouter9({ model: event.target.value })} disabled={router9.allowed_model_ids.length === 0}>
              <option value="">Chưa chọn model</option>
              {router9.allowed_model_ids.map((id) => <option key={id} value={id}>{id}</option>)}
            </select>
          </label>
          <input className="model-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Lọc model..." />
          <div className="model-actions">
            <button type="button" className="secondary-button" onClick={selectFilteredModels} disabled={filteredModels.length === 0}>Chọn danh sách đang lọc</button>
            <button type="button" className="secondary-button" onClick={clearFilteredModels} disabled={filteredModels.length === 0}>Bỏ chọn danh sách đang lọc</button>
          </div>
          <div className="model-list">
            {filteredModels.length === 0 ? (
              <p className="field-hint">Chưa có model. Hãy quét model 9router trước.</p>
            ) : filteredModels.map((model) => (
              <label className="model-row" key={model.id}>
                <input type="checkbox" checked={selected.has(model.id)} onChange={() => toggleModel(model.id)} />
                <span>
                  <strong>{model.label}</strong>
                  <small>{model.owned_by ? `Owned by ${model.owned_by}` : model.id}</small>
                </span>
              </label>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}

const renderCodexVersions = ['5.5', '5.4', '5.3'];
const ocrCodexVersions = ['5.5', '5.4'];

function selectRouter9RenderModelIds(models: ScannedModelInfo[]) {
  return selectByScore(models, renderModelScore);
}

function selectRouter9OcrModelIds(models: ScannedModelInfo[]) {
  const selected = selectByScore(models, ocrModelScore);
  const primary = selected.filter((id) => (ocrModelScore(id)?.[0] ?? 9) < 3);
  return primary.length > 0 ? primary : selected;
}

function selectByScore(models: ScannedModelInfo[], scoreModel: (id: string) => [number, number] | null) {
  return models
    .map((model) => ({ id: model.id, score: scoreModel(model.id) }))
    .filter((item): item is { id: string; score: [number, number] } => item.score !== null)
    .sort((left, right) => left.score[0] - right.score[0] || left.score[1] - right.score[1] || left.id.localeCompare(right.id))
    .map((item) => item.id);
}

function renderModelScore(modelId: string): [number, number] | null {
  const version = codexVersion(modelId);
  const codexIndex = version ? renderCodexVersions.indexOf(version) : -1;
  if (codexIndex >= 0) return [0, codexIndex * 2 + (looksImageModel(modelId) ? 1 : 0)];
  if (isGithubGpt52(modelId)) return [1, 0];
  if (gptVersion(modelId) === '5.2') return [2, 0];
  return null;
}

function ocrModelScore(modelId: string): [number, number] | null {
  const version = codexVersion(modelId);
  const codexIndex = version ? ocrCodexVersions.indexOf(version) : -1;
  if (codexIndex >= 0 && looksImageModel(modelId)) return [0, codexIndex];
  if (isGithubGpt52(modelId)) return [1, 0];
  if (gptVersion(modelId) === '5.2') return [2, 0];
  if (codexIndex >= 0) return [3, codexIndex];
  return null;
}

function codexVersion(modelId: string) {
  return modelId.match(/codex[^0-9]*(\d+(?:\.\d+)*)/i)?.[1] ?? null;
}

function gptVersion(modelId: string) {
  return modelId.match(/gpt[^0-9]*(\d+(?:\.\d+)*)/i)?.[1] ?? null;
}

function looksImageModel(modelId: string) {
  const lowered = modelId.toLowerCase();
  return lowered.includes('image') || lowered.includes('vision') || lowered.includes('vl');
}

function isGithubGpt52(modelId: string) {
  const lowered = modelId.toLowerCase();
  return gptVersion(modelId) === '5.2' && (lowered.includes('github') || lowered.includes('copilot') || /(^|[/:_-])gh([/:_-]|$)/.test(lowered));
}

function mergeUnique(modelIds: string[]) {
  return [...new Set(modelIds.filter(Boolean))];
}
