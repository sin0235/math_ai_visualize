import React, { useState, useEffect } from 'react';
import { 
  AdminProviderModelSettings, 
  AdminRouter9ModelSettings, 
  RuntimeSettings,
  OcrProvider 
} from '../../types/settings';
import { 
  scanProviderModels,
  scanRouter9Models,
  checkAdminProvider,
} from '../../api/client';
import { buildModelOptionsFromDefaults, buildProviderOptions, providerLabels } from '../../utils/settingsOptions';
import type { ProviderSettingsDefaults, SettingsDefaults } from '../../types/settings';

// --- Utility Functions ---

type AdminToastKind = 'error' | 'warning' | 'info';
type AdminToast = (title: string, message: string, kind?: AdminToastKind) => void;

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function getStringValue(value: unknown, fallback: string) {
  return typeof value === 'string' ? value : fallback;
}

function parseLines(value: string) {
  return value.split('\n').map((item) => item.trim()).filter(Boolean);
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

const defaultRuntimeSettings: RuntimeSettings = {
  default_provider: 'auto',
  openrouter: { api_key: '', base_url: '', model: '', scanned_models: [], allowed_model_ids: [], last_scanned_at: '' },
  nvidia: { api_key: '', base_url: '', model: '', scanned_models: [], allowed_model_ids: [], last_scanned_at: '' },
  ollama: { api_key: '', base_url: '', model: '', scanned_models: [], allowed_model_ids: [], last_scanned_at: '' },
  openai_compat: { api_key: '', base_url: 'http://localhost:8080/v1', model: '', scanned_models: [], allowed_model_ids: [], last_scanned_at: '' },
  router9: { api_key: '', base_url: '', model: '', scanned_models: [], last_scanned_at: '', only_mode: false, allowed_model_ids: [] },
  ocr: { provider: 'openrouter', model: '', max_image_mb: 5 },
  openrouter_http_referer: '',
  openrouter_x_title: '',
  openrouter_reasoning_enabled: false,
};

function defaultAdminProviderSettings() {
  return { base_url: '', model: '', scanned_models: [] as any[], allowed_model_ids: [] as string[], last_scanned_at: '', only_mode: false };
}

function getAdminProviderSettings(value: Record<string, unknown>, provider: string, defaults?: SettingsDefaults | null) {
  const item = value[provider];
  const data = item && typeof item === 'object' ? item as Record<string, unknown> : {};
  const providerDefaults = providerDefaultsFor(defaults, provider);
  return {
    ...defaultAdminProviderSettings(),
    ...data,
    base_url: typeof data.base_url === 'string' && data.base_url ? data.base_url : providerDefaults?.base_url ?? '',
    model: typeof data.model === 'string' && data.model ? data.model : providerDefaults?.model ?? '',
    scanned_models: Array.isArray(data.scanned_models) && data.scanned_models.length > 0 ? data.scanned_models : providerDefaults?.scanned_models ?? [],
    allowed_model_ids: Array.isArray(data.allowed_model_ids) ? data.allowed_model_ids.map(String) : providerDefaults?.allowed_model_ids ?? [],
    last_scanned_at: typeof data.last_scanned_at === 'string' ? data.last_scanned_at : '',
    only_mode: typeof data.only_mode === 'boolean' ? data.only_mode : provider === 'router9' ? defaults?.router9.only_mode ?? false : false,
  };
}

function providerDefaultsFor(defaults: SettingsDefaults | null | undefined, provider: string): ProviderSettingsDefaults | undefined {
  if (!defaults) return undefined;
  if (provider === 'openrouter' || provider === 'nvidia' || provider === 'ollama' || provider === 'openai_compat' || provider === 'router9') return defaults[provider];
  return undefined;
}

function getAdminOcrSettings(value: Record<string, unknown>) {
  const item = value.ocr;
  const data = item && typeof item === 'object' ? item as Record<string, unknown> : {};
  const maxImageMb = typeof data.max_image_mb === 'number' ? data.max_image_mb : 5;
  return {
    provider: getStringValue(data.provider, 'openrouter'),
    model: getStringValue(data.model, ''),
    max_image_mb: clamp(maxImageMb, 1, 32),
  };
}

function adminSettingsToRuntime(value: Record<string, unknown>, defaults?: SettingsDefaults | null): RuntimeSettings {
  const router9 = getAdminProviderSettings(value, 'router9', defaults);
  return {
    ...defaultRuntimeSettings,
    default_provider: getStringValue(value.default_provider, 'auto'),
    openrouter: { ...defaultRuntimeSettings.openrouter, ...getAdminProviderSettings(value, 'openrouter', defaults) },
    nvidia: { ...defaultRuntimeSettings.nvidia, ...getAdminProviderSettings(value, 'nvidia', defaults) },
    ollama: { ...defaultRuntimeSettings.ollama, ...getAdminProviderSettings(value, 'ollama', defaults) },
    openai_compat: { ...defaultRuntimeSettings.openai_compat, ...getAdminProviderSettings(value, 'openai_compat', defaults) },
    router9: { ...defaultRuntimeSettings.router9, ...router9 },
    ocr: { ...defaultRuntimeSettings.ocr, ...getAdminOcrSettings(value), provider: getAdminOcrSettings(value).provider as OcrProvider },
    openrouter_http_referer: getStringValue(value.openrouter_http_referer, ''),
    openrouter_x_title: getStringValue(value.openrouter_x_title, ''),
    openrouter_reasoning_enabled: value.openrouter_reasoning_enabled === true,
  };
}

function normalizeScannedModels(models: any[]) {
  return models
    .map((modelItem) => {
      const id = typeof modelItem === 'string' ? modelItem : modelItem?.id;
      if (!id) return null;
      return {
        id,
        label: typeof modelItem === 'object' && modelItem.label ? modelItem.label : typeof modelItem === 'object' && modelItem.name ? modelItem.name : id,
        provider: typeof modelItem === 'object' && modelItem.provider ? modelItem.provider : '',
      };
    })
    .filter(Boolean) as ProviderSettingsDefaults['scanned_models'];
}

function adminProviderToDefaults(value: Record<string, unknown>, provider: string): ProviderSettingsDefaults {
  const settings = getAdminProviderSettings(value, provider);
  return {
    api_key_configured: true,
    base_url: settings.base_url,
    model: settings.model,
    scanned_models: normalizeScannedModels(settings.scanned_models),
    allowed_model_ids: settings.allowed_model_ids,
  };
}

function adminModelOptions(providerValue: ReturnType<typeof defaultAdminProviderSettings>, preferredIds: string[] = []) {
  const byId = new Map<string, { id: string; name: string }>();
  function add(id: string, name = id) {
    if (id && !byId.has(id)) byId.set(id, { id, name });
  }
  preferredIds.forEach((id) => add(id));
  add(providerValue.model);
  providerValue.allowed_model_ids.forEach((id) => add(id));
  providerValue.scanned_models.forEach((modelItem: any) => {
    const id = typeof modelItem === 'string' ? modelItem : modelItem?.id;
    const name = typeof modelItem === 'object' ? modelItem.label || modelItem.name || id : id;
    add(id, name);
  });
  return [...byId.values()];
}

function normalizeDefaultModel(providerValue: ReturnType<typeof defaultAdminProviderSettings>) {
  if (providerValue.allowed_model_ids.length > 0 && !providerValue.allowed_model_ids.includes(providerValue.model)) {
    return { ...providerValue, model: providerValue.allowed_model_ids[0] ?? '' };
  }
  return providerValue;
}

function sameJson(left: unknown, right: unknown) {
  return JSON.stringify(left) === JSON.stringify(right);
}

/** Thứ tự cố định theo lần quét; tránh reorder DOM khi tick checkbox làm danh sách nhảy. */
function orderedAllowlistModelOptions(
  providerValue: ReturnType<typeof defaultAdminProviderSettings>,
  allowedModelIds: string[]
) {
  const optionMap = new Map(adminModelOptions(providerValue, allowedModelIds).map((o) => [o.id, o]));
  const ordered: Array<{ id: string; name: string }> = [];
  for (const modelItem of providerValue.scanned_models) {
    const id = typeof modelItem === 'string' ? modelItem : modelItem?.id;
    if (id && optionMap.has(id)) ordered.push(optionMap.get(id)!);
  }
  const seenIds = new Set(ordered.map((o) => o.id));
  const restIds = [...optionMap.keys()].filter((id) => !seenIds.has(id)).sort((a, b) => a.localeCompare(b));
  return [...ordered, ...restIds.map((id) => optionMap.get(id)!)];
}

function adminSettingsToDefaults(value: Record<string, unknown>): SettingsDefaults {
  const openrouter = adminProviderToDefaults(value, 'openrouter');
  return {
    app_name: 'Math Renderer',
    default_provider: getStringValue(value.default_provider, 'auto'),
    openrouter: {
      ...openrouter,
      vision_model: getStringValue(value.openrouter_vision_model, ''),
      http_referer: getStringValue(value.openrouter_http_referer, ''),
      x_title: getStringValue(value.openrouter_x_title, ''),
      reasoning_enabled: value.openrouter_reasoning_enabled === true,
    },
    nvidia: adminProviderToDefaults(value, 'nvidia'),
    ollama: adminProviderToDefaults(value, 'ollama'),
    openai_compat: adminProviderToDefaults(value, 'openai_compat'),
    router9: {
      ...adminProviderToDefaults(value, 'router9'),
      only_mode: getAdminProviderSettings(value, 'router9').only_mode,
    },
    ocr: getAdminOcrSettings(value) as SettingsDefaults['ocr'],
  };
}

function getPlanQuota(value: unknown) {
  const data = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  return {
    daily_render_limit: typeof data.daily_render_limit === 'number' ? data.daily_render_limit : null,
    daily_ocr_limit: typeof data.daily_ocr_limit === 'number' ? data.daily_ocr_limit : null,
  };
}

function optionalNumber(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return null;
  return Math.max(0, Number(trimmed) || 0);
}

function getAiTaskProfile(value: unknown) {
  const data = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  return {
    provider: getStringValue(data.provider, 'auto'),
    model: getStringValue(data.model, ''),
    fallbacks: Array.isArray(data.fallbacks) ? data.fallbacks.map(String) : [],
  };
}

// --- Form Components ---

export function AdminAiSettingsForm({ value, defaults, saving, onSave, onToast }: { value: Record<string, unknown>; defaults: SettingsDefaults | null; saving: boolean; onSave: (patch: Record<string, unknown>) => Promise<void>; onToast?: AdminToast }) {
  const providers = ['openrouter', 'nvidia', 'ollama', 'openai_compat', 'router9'] as const;
  const scannableProviders = new Set<(typeof providers)[number]>(['openrouter', 'openai_compat', 'router9']);
  const ocrValue = getAdminOcrSettings(value);
  const [draft, setDraft] = useState(() => Object.fromEntries(providers.map((provider) => [provider, getAdminProviderSettings(value, provider, defaults)])) as Record<(typeof providers)[number], ReturnType<typeof getAdminProviderSettings>>);
  const [ocrProvider, setOcrProvider] = useState(ocrValue.provider);
  const [ocrModel, setOcrModel] = useState(ocrValue.model);
  const [ocrMaxImageMb, setOcrMaxImageMb] = useState(String(ocrValue.max_image_mb));
  const [scanning, setScanning] = useState<string | null>(null);
  const [checking, setChecking] = useState<string | null>(null);
  const [modelFilter, setModelFilter] = useState('');
  const [manualModelInputs, setManualModelInputs] = useState<Record<string, string>>({});
  const [checkResults, setCheckResults] = useState<Record<string, { status: string; message: string }>>({});

  useEffect(() => {
    setDraft(Object.fromEntries(providers.map((provider) => [provider, getAdminProviderSettings(value, provider, defaults)])) as Record<(typeof providers)[number], ReturnType<typeof getAdminProviderSettings>>);
    setCheckResults({});
  }, [value, defaults]);

  useEffect(() => {
    const nextOcr = getAdminOcrSettings(value);
    setOcrProvider(nextOcr.provider);
    setOcrModel(nextOcr.model);
    setOcrMaxImageMb(String(nextOcr.max_image_mb));
  }, [value]);

  function updateProvider(provider: (typeof providers)[number], patch: Partial<ReturnType<typeof getAdminProviderSettings>>) {
    setDraft((current) => ({ ...current, [provider]: normalizeDefaultModel({ ...current[provider], ...patch }) }));
  }

  async function saveProvider(provider: (typeof providers)[number]) {
    const current = getAdminProviderSettings(value, provider, defaults);
    const providerDraft = draft[provider] as ReturnType<typeof getAdminProviderSettings> & { api_key?: string };
    const nextProvider = normalizeDefaultModel({
      ...current,
      ...providerDraft,
      base_url: providerDraft.base_url.trim(),
      model: providerDraft.model.trim(),
    });
    if (!providerDraft.api_key?.trim()) {
      delete (nextProvider as { api_key?: string }).api_key;
    }
    if (provider !== 'router9') {
      delete (nextProvider as { only_mode?: boolean }).only_mode;
    }
    const providerPatch: Record<string, unknown> = {
      base_url: nextProvider.base_url,
      model: nextProvider.model,
      allowed_model_ids: nextProvider.allowed_model_ids,
    };
    if (provider === 'router9') providerPatch.only_mode = nextProvider.only_mode;
    if ((nextProvider as { api_key?: string }).api_key?.trim()) providerPatch.api_key = (nextProvider as { api_key?: string }).api_key;
    if (!sameJson(current.scanned_models, nextProvider.scanned_models)) {
      providerPatch.scanned_models = nextProvider.scanned_models;
      providerPatch.last_scanned_at = nextProvider.last_scanned_at;
    }
    try {
      await onSave({
        [provider]: providerPatch,
      });
      onToast?.('Cấu hình AI', `Đã lưu provider ${providerLabels[provider]}.`, 'info');
    } catch (error) {
      onToast?.('Cấu hình AI', getErrorMessage(error, `Không thể lưu provider ${providerLabels[provider]}.`), 'error');
    }
  }

  async function saveOcr() {
    try {
      await onSave({
        ocr: {
          provider: ocrProvider,
          model: ocrModel.trim(),
          max_image_mb: clamp(Number(ocrMaxImageMb) || 5, 1, 32),
        },
      });
      onToast?.('OCR', 'Đã lưu cấu hình OCR.', 'info');
    } catch (error) {
      onToast?.('OCR', getErrorMessage(error, 'Không thể lưu cấu hình OCR.'), 'error');
    }
  }

  async function scanProvider(provider: (typeof providers)[number]) {
    setScanning(provider);
    try {
      const runtime = adminSettingsToRuntime({ ...value, [provider]: draft[provider] }, defaults);
      const models = provider === 'router9' ? await scanRouter9Models(runtime) : await scanProviderModels(provider as 'openrouter' | 'openai_compat', runtime);
      const next = normalizeDefaultModel({ ...draft[provider], scanned_models: models, last_scanned_at: new Date().toISOString() });
      updateProvider(provider, next);
      await onSave({ [provider]: next });
      onToast?.('Quét model', `Đã quét ${models.length} model từ ${providerLabels[provider]}.`, 'info');
    } catch (error) {
      onToast?.('Quét model', getErrorMessage(error, `Không thể quét model cho ${providerLabels[provider]}.`), 'error');
    } finally {
      setScanning(null);
    }
  }

  function manualModelOptions(provider: (typeof providers)[number]) {
    return adminModelOptions(draft[provider], [draft[provider].model]);
  }

  async function checkProvider(provider: (typeof providers)[number]) {
    setChecking(provider);
    try {
      const runtime = adminSettingsToRuntime({ ...value, [provider]: draft[provider] }, defaults);
      const result = await checkAdminProvider(provider, runtime);
      setCheckResults((current) => ({ ...current, [provider]: result }));
      onToast?.('Kiểm tra provider', result.message, result.status === 'ok' ? 'info' : 'error');
    } catch (error) {
      const message = getErrorMessage(error, `Không thể kiểm tra ${providerLabels[provider]}.`);
      setCheckResults((current) => ({ ...current, [provider]: { status: 'error', message } }));
      onToast?.('Kiểm tra provider', message, 'error');
    } finally {
      setChecking(null);
    }
  }

  function toggleModelId(provider: (typeof providers)[number], modelId: string) {
    updateProvider(provider, {
      allowed_model_ids: draft[provider].allowed_model_ids.includes(modelId)
        ? draft[provider].allowed_model_ids.filter((id) => id !== modelId)
        : [...draft[provider].allowed_model_ids, modelId],
    });
  }

  function addManualModel(provider: (typeof providers)[number]) {
    const modelId = (manualModelInputs[provider] ?? '').trim();
    if (!modelId) return;
    const providerValue = draft[provider];
    updateProvider(provider, {
      scanned_models: providerValue.scanned_models.some((modelItem: any) => modelItem.id === modelId)
        ? providerValue.scanned_models
        : [...providerValue.scanned_models, { id: modelId, label: modelId, provider }],
      allowed_model_ids: providerValue.allowed_model_ids.includes(modelId)
        ? providerValue.allowed_model_ids
        : [...providerValue.allowed_model_ids, modelId],
      model: providerValue.model || modelId,
    });
    setManualModelInputs((current) => ({ ...current, [provider]: '' }));
  }

  function removeManualModel(provider: (typeof providers)[number], modelId: string) {
    updateProvider(provider, {
      scanned_models: draft[provider].scanned_models.filter((modelItem: any) => modelItem.id !== modelId),
      allowed_model_ids: draft[provider].allowed_model_ids.filter((id) => id !== modelId),
      model: draft[provider].model === modelId ? '' : draft[provider].model,
    });
  }

  function selectOcrProvider(nextProvider: string) {
    const nextSettings = draft[nextProvider as (typeof providers)[number]] ?? getAdminProviderSettings(value, nextProvider, defaults);
    const firstScannedModel = nextSettings.scanned_models
      .map((modelItem: any) => typeof modelItem === 'string' ? modelItem : modelItem.id)
      .find(Boolean);
    setOcrProvider(nextProvider);
    setOcrModel(defaults?.ocr.provider === nextProvider ? defaults.ocr.model : nextSettings.model || firstScannedModel || '');
  }

  const normalizedModelFilter = modelFilter.trim().toLowerCase();
  const ocrProviderValue = draft[ocrProvider as (typeof providers)[number]] ?? getAdminProviderSettings(value, ocrProvider, defaults);
  const ocrModelOptions = adminModelOptions(ocrProviderValue, [ocrModel, defaults?.ocr.provider === ocrProvider ? defaults.ocr.model : '']);

  return (
    <div className="admin-ai-settings">
      <section className="admin-settings-section">
        <h4>Provider & model</h4>
        <p className="field-hint">OpenRouter, OpenAI-compatible và 9router có thể quét endpoint /models. NVIDIA và Ollama quản lý model thủ công.</p>
        <label className="field-label">Tìm model<input type="search" value={modelFilter} onChange={(event) => setModelFilter(event.target.value)} placeholder="Nhập tên hoặc ID model" /></label>
        <div className="admin-provider-grid">
          {providers.map((provider) => {
            const providerValue = draft[provider];
            const modelOptions = manualModelOptions(provider);
            const allowlistOptions = orderedAllowlistModelOptions(providerValue, providerValue.allowed_model_ids);
            const filteredAllowlistOptions = normalizedModelFilter
              ? allowlistOptions.filter((modelItem) => modelItem.id.toLowerCase().includes(normalizedModelFilter) || modelItem.name.toLowerCase().includes(normalizedModelFilter))
              : allowlistOptions;
            const result = checkResults[provider];
            const isManualProvider = provider === 'nvidia' || provider === 'ollama';
            return (
              <article className="admin-provider-card" key={provider}>
                <div className="admin-provider-card-head">
                  <div><strong>{providerLabels[provider]}</strong><span>{providerValue.scanned_models.length} model quét · allowlist {providerValue.allowed_model_ids.length}</span></div>
                  {provider === 'router9' ? (
                    <label className="checkbox-label"><input type="checkbox" checked={providerValue.only_mode} onChange={(event) => updateProvider(provider, { only_mode: event.target.checked })} /> Chỉ dùng 9router</label>
                  ) : (
                    <div className="admin-row-actions admin-provider-card-head-actions">
                      <button type="button" className="secondary-button" onClick={() => void checkProvider(provider)} disabled={saving || checking === provider}>{checking === provider ? 'Đang kiểm tra...' : 'Kiểm tra'}</button>
                      {scannableProviders.has(provider) && <button type="button" className="secondary-button" onClick={() => void scanProvider(provider)} disabled={saving || scanning === provider}>{scanning === provider ? 'Đang quét...' : 'Quét model'}</button>}
                      <button type="button" className="secondary-button" onClick={() => void saveProvider(provider)} disabled={saving}>{saving ? 'Đang lưu...' : 'Lưu provider'}</button>
                    </div>
                  )}
                </div>
                <div className="admin-provider-config">
                <div className={`admin-field-grid ${provider === 'router9' ? 'admin-field-grid-router9' : ''}`}>
                  <label className="field-label">Base URL<input type="url" value={providerValue.base_url} onChange={(event) => updateProvider(provider, { base_url: event.target.value })} placeholder="https://..." /></label>
                  <label className="field-label">API key<input type="password" value={(providerValue as any).api_key ?? ''} onChange={(event) => updateProvider(provider, { ...( { api_key: event.target.value } as any) })} placeholder={defaults?.[provider]?.api_key_configured ? 'Đã cấu hình, nhập để thay' : 'Nhập API key'} /></label>
                  <label className="field-label">Model mặc định hệ thống<select value={providerValue.model} onChange={(event) => updateProvider(provider, { model: event.target.value })}><option value="">Chọn model</option>{modelOptions.map((modelItem) => <option key={modelItem.id} value={modelItem.id}>{modelItem.name}</option>)}</select></label>
                </div>
                {result && <div className={`admin-status-box ${result.status}`}><strong>{result.status === 'ok' ? 'Thành công' : 'Lỗi'}</strong><p>{result.message}</p></div>}
                {provider === 'router9' && (
                  <div className="admin-row-actions">
                    <button type="button" className="secondary-button" onClick={() => void checkProvider(provider)} disabled={saving || checking === provider}>{checking === provider ? 'Đang kiểm tra...' : 'Kiểm tra'}</button>
                    <button type="button" className="secondary-button" onClick={() => void scanProvider(provider)} disabled={saving || scanning === provider}>{scanning === provider ? 'Đang quét...' : 'Quét model'}</button>
                    <button type="button" className="secondary-button" onClick={() => void saveProvider(provider)} disabled={saving}>{saving ? 'Đang lưu...' : 'Lưu provider'}</button>
                  </div>
                )}
                </div>
                <div className="admin-provider-models">
                  <div className="admin-provider-models-head">
                    <strong>{isManualProvider ? 'Model inventory / thủ công' : 'Model inventory'}</strong>
                    <span>{filteredAllowlistOptions.length}/{allowlistOptions.length}</span>
                  </div>
                  {isManualProvider && (
                    <div className="admin-manual-model-row">
                      <input
                        placeholder={`${provider}/model-id hoặc model-id`}
                        value={manualModelInputs[provider] ?? ''}
                        onChange={(event) => setManualModelInputs((current) => ({ ...current, [provider]: event.target.value }))}
                        onKeyDown={(event) => { if (event.key === 'Enter') addManualModel(provider); }}
                      />
                      <button type="button" className="secondary-button" onClick={() => addManualModel(provider)}>Thêm model</button>
                    </div>
                  )}
                  <div className="admin-model-checklist">
                    {filteredAllowlistOptions.map((modelItem) => (
                      <div key={modelItem.id} className="admin-model-checkbox">
                        <label>
                          <input type="checkbox" checked={providerValue.allowed_model_ids.includes(modelItem.id)} onChange={() => toggleModelId(provider, modelItem.id)} />
                          <span className="model-label"><strong>{modelItem.name}</strong>{modelItem.id !== modelItem.name && <small>{modelItem.id}</small>}</span>
                        </label>
                        {isManualProvider && <button type="button" className="history-delete" onClick={() => removeManualModel(provider, modelItem.id)} aria-label={`Xoá ${modelItem.id}`}>×</button>}
                      </div>
                    ))}
                    {filteredAllowlistOptions.length === 0 && <p className="field-hint">Chưa có model thủ công hoặc không khớp bộ lọc.</p>}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="admin-settings-section">
        <h4>OCR</h4>
        <div className="admin-field-grid admin-ocr-grid">
          <label className="field-label">Provider OCR<select value={ocrProvider} onChange={(event) => selectOcrProvider(event.target.value)}><option value="openrouter">OpenRouter</option><option value="router9">9router</option></select></label>
          <label className="field-label">Model OCR<select value={ocrModel} onChange={(event) => setOcrModel(event.target.value)}><option value="">Chọn model</option>{ocrModelOptions.map((modelItem) => <option key={modelItem.id} value={modelItem.id}>{modelItem.name}</option>)}</select></label>
          <label className="field-label">Dung lượng ảnh tối đa (MB)<input type="number" min="1" max="32" value={ocrMaxImageMb} onChange={(event) => setOcrMaxImageMb(event.target.value)} /></label>
        </div>
        <button type="button" className="secondary-button" onClick={saveOcr} disabled={saving}>{saving ? 'Đang lưu...' : 'Lưu OCR'}</button>
      </section>
    </div>
  );
}

export function AdminPlanSettingsForm({ value, onSave }: { value: Record<string, unknown>; onSave: (value: Record<string, unknown>) => Promise<void> }) {
  const plansValue = value.plans && typeof value.plans === 'object' ? value.plans as Record<string, unknown> : { free: {}, pro: {} };
  const planIds = Object.keys(plansValue).length > 0 ? Object.keys(plansValue) : ['free', 'pro'];
  const [quotas, setQuotas] = useState(() => Object.fromEntries(planIds.map((planId) => {
    const quota = getPlanQuota(plansValue[planId]);
    return [planId, { render: String(quota.daily_render_limit ?? ''), ocr: String(quota.daily_ocr_limit ?? '') }];
  })) as Record<string, { render: string; ocr: string }>);

  useEffect(() => {
    setQuotas(Object.fromEntries(planIds.map((planId) => {
      const quota = getPlanQuota(plansValue[planId]);
      return [planId, { render: String(quota.daily_render_limit ?? ''), ocr: String(quota.daily_ocr_limit ?? '') }];
    })) as Record<string, { render: string; ocr: string }>);
  }, [value]);

  function updateQuota(planId: string, field: 'render' | 'ocr', nextValue: string) {
    setQuotas((current) => ({ ...current, [planId]: { ...current[planId], [field]: nextValue } }));
  }

  return (
    <section className="admin-settings-section"><h4>Giới hạn theo gói</h4><div className="admin-field-grid">
      {planIds.map((planId) => (
        <React.Fragment key={planId}>
          <label className="field-label">{planId} render/ngày<input type="number" min="0" value={quotas[planId]?.render ?? ''} onChange={(event) => updateQuota(planId, 'render', event.target.value)} /></label>
          <label className="field-label">{planId} OCR/ngày<input type="number" min="0" value={quotas[planId]?.ocr ?? ''} onChange={(event) => updateQuota(planId, 'ocr', event.target.value)} /></label>
        </React.Fragment>
      ))}
    </div><button type="button" className="secondary-button" onClick={() => void onSave({ version: 1, plans: Object.fromEntries(planIds.map((planId) => [planId, { daily_render_limit: optionalNumber(quotas[planId]?.render ?? ''), daily_ocr_limit: optionalNumber(quotas[planId]?.ocr ?? '') }])) })}>Lưu giới hạn</button></section>
  );
}

export function AdminFeatureFlagsForm({ value, onSave }: { value: Record<string, unknown>; onSave: (value: Record<string, unknown>) => Promise<void> }) {
  const [maintenanceMode, setMaintenanceMode] = useState(value.maintenance_mode === true);
  const [message, setMessage] = useState(getStringValue(value.maintenance_message, 'Hệ thống đang bảo trì. Vui lòng thử lại sau.'));
  const [googleOAuth, setGoogleOAuth] = useState(value.google_oauth_enabled !== false);
  const [ocr, setOcr] = useState(value.ocr_enabled !== false);
  const [render, setRender] = useState(value.render_enabled !== false);
  return (
    <section className="admin-settings-section"><h4>Cờ tính năng</h4><div className="admin-field-grid">
      <label className="checkbox-label"><input type="checkbox" checked={maintenanceMode} onChange={(event) => setMaintenanceMode(event.target.checked)} /> Chế độ bảo trì</label>
      <label className="checkbox-label"><input type="checkbox" checked={render} onChange={(event) => setRender(event.target.checked)} /> Cho phép dựng hình</label>
      <label className="checkbox-label"><input type="checkbox" checked={ocr} onChange={(event) => setOcr(event.target.checked)} /> Cho phép OCR</label>
      <label className="checkbox-label"><input type="checkbox" checked={googleOAuth} onChange={(event) => setGoogleOAuth(event.target.checked)} /> Cho phép đăng nhập Google</label>
    </div><label className="field-label">Thông báo bảo trì<textarea rows={3} value={message} onChange={(event) => setMessage(event.target.value)} /></label><button type="button" className="secondary-button" onClick={() => void onSave({ version: 1, maintenance_mode: maintenanceMode, maintenance_message: message, google_oauth_enabled: googleOAuth, ocr_enabled: ocr, render_enabled: render })}>Lưu cờ tính năng</button></section>
  );
}

export function AdminAiProfilesForm({ value, aiSettings, onSave, onToast }: { value: Record<string, unknown>; aiSettings: Record<string, unknown>; onSave: (value: Record<string, unknown>) => Promise<void>; onToast?: AdminToast }) {
  const geometry = getAiTaskProfile(value.geometry_reasoning);
  const solver = getAiTaskProfile(value.solver_explanation);
  const [geometryProvider, setGeometryProvider] = useState(geometry.provider);
  const [geometryModel, setGeometryModel] = useState(geometry.model);
  const [geometryFallbacks, setGeometryFallbacks] = useState<string[]>(geometry.fallbacks);
  const [solverProvider, setSolverProvider] = useState(solver.provider);
  const [solverModel, setSolverModel] = useState(solver.model);
  const [solverFallbacks, setSolverFallbacks] = useState<string[]>(solver.fallbacks);
  const settingsDefaults = adminSettingsToDefaults(aiSettings);
  const providerOptions = buildProviderOptions(settingsDefaults, false);

  useEffect(() => {
    const nextGeometry = getAiTaskProfile(value.geometry_reasoning);
    const nextSolver = getAiTaskProfile(value.solver_explanation);
    setGeometryProvider(nextGeometry.provider);
    setGeometryModel(nextGeometry.model);
    setGeometryFallbacks(nextGeometry.fallbacks);
    setSolverProvider(nextSolver.provider);
    setSolverModel(nextSolver.model);
    setSolverFallbacks(nextSolver.fallbacks);
  }, [value]);

  function providerDefaults(selectedProvider: string): ProviderSettingsDefaults | undefined {
    if (selectedProvider === 'openrouter' || selectedProvider === 'nvidia' || selectedProvider === 'ollama' || selectedProvider === 'openai_compat' || selectedProvider === 'router9') return settingsDefaults[selectedProvider];
    return undefined;
  }

  function modelOptions(selectedProvider: string, selectedModel: string, fallbackModels: string[] = []) {
    return buildModelOptionsFromDefaults(providerDefaults(selectedProvider), selectedModel, fallbackModels, settingsDefaults, selectedProvider);
  }

  function updateFallbacks(kind: 'geometry' | 'solver', modelId: string, checked: boolean) {
    const setter = kind === 'geometry' ? setGeometryFallbacks : setSolverFallbacks;
    setter((current) => checked ? [...new Set([...current, modelId])] : current.filter((item) => item !== modelId));
  }

  async function saveProfiles() {
    try {
      await onSave({ version: 1, geometry_reasoning: { provider: geometryProvider, model: geometryModel, fallbacks: geometryFallbacks }, solver_explanation: { provider: solverProvider, model: solverModel, fallbacks: solverFallbacks } });
      onToast?.('Hồ sơ AI', 'Đã lưu hồ sơ AI.', 'info');
    } catch (error) {
      onToast?.('Hồ sơ AI', getErrorMessage(error, 'Không thể lưu hồ sơ AI.'), 'error');
    }
  }

  return (
    <section className="admin-settings-section"><h4>Hồ sơ AI</h4><div className="admin-field-grid">
      <label className="field-label">Provider hình học<select value={geometryProvider} onChange={(event) => setGeometryProvider(event.target.value)}><option value="auto">auto</option>{providerOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
      <label className="field-label">Model hình học<select value={geometryModel} onChange={(event) => setGeometryModel(event.target.value)}><option value="">Chọn model</option>{modelOptions(geometryProvider, geometryModel, geometryFallbacks).map((modelItem) => <option key={modelItem.id} value={modelItem.id}>{modelItem.label}</option>)}</select></label>
      <label className="field-label">Provider diễn giải lời giải<select value={solverProvider} onChange={(event) => setSolverProvider(event.target.value)}><option value="auto">auto</option>{providerOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
      <label className="field-label">Model diễn giải lời giải<select value={solverModel} onChange={(event) => setSolverModel(event.target.value)}><option value="">Chọn model</option>{modelOptions(solverProvider, solverModel, solverFallbacks).map((modelItem) => <option key={modelItem.id} value={modelItem.id}>{modelItem.label}</option>)}</select></label>
    </div>
    <div className="admin-model-fallback-grid">
      <ModelFallbackChecklist title="Model dự phòng hình học" options={modelOptions(geometryProvider, geometryModel, geometryFallbacks)} selected={geometryFallbacks} onToggle={(modelId, checked) => updateFallbacks('geometry', modelId, checked)} />
      <ModelFallbackChecklist title="Model dự phòng diễn giải lời giải" options={modelOptions(solverProvider, solverModel, solverFallbacks)} selected={solverFallbacks} onToggle={(modelId, checked) => updateFallbacks('solver', modelId, checked)} />
    </div>
    <button type="button" className="secondary-button" onClick={() => void saveProfiles()}>Lưu hồ sơ AI</button></section>
  );
}

function ModelFallbackChecklist({ title, options, selected, onToggle }: { title: string; options: Array<{ id: string; label: string }>; selected: string[]; onToggle: (modelId: string, checked: boolean) => void }) {
  return (
    <section className="admin-model-fallback-list">
      <div className="admin-provider-models-head">
        <strong>{title}</strong>
        <span>{options.length}</span>
      </div>
      <div className="admin-model-checklist">
        {options.length > 0 ? options.map((option) => (
          <div key={option.id} className="admin-model-checkbox">
            <label>
              <input type="checkbox" checked={selected.includes(option.id)} onChange={(event) => onToggle(option.id, event.target.checked)} />
              <span className="model-label"><strong>{option.id}</strong></span>
            </label>
          </div>
        )) : <p className="field-hint">Chưa có model đã quét hoặc allowlist cho provider này.</p>}
      </div>
    </section>
  );
}

export function AdminAiPromptsForm({ value, onSave, onToast }: { value: Record<string, unknown>; onSave: (value: Record<string, unknown>) => Promise<void>; onToast?: AdminToast }) {
  const [sceneExtraction, setSceneExtraction] = useState(getStringValue(value.scene_extraction, ''));
  const [reasoning, setReasoning] = useState(getStringValue(value.reasoning, ''));

  useEffect(() => {
    setSceneExtraction(getStringValue(value.scene_extraction, ''));
    setReasoning(getStringValue(value.reasoning, ''));
  }, [value]);

  async function savePrompts() {
    try {
      await onSave({ version: 1, scene_extraction: sceneExtraction.trim(), reasoning: reasoning.trim() });
      onToast?.('Prompt hệ thống', 'Đã lưu prompt hệ thống.', 'info');
    } catch (error) {
      onToast?.('Prompt hệ thống', getErrorMessage(error, 'Không thể lưu prompt hệ thống.'), 'error');
    }
  }

  return (
    <section className="admin-settings-section">
      <h4>Prompt hệ thống AI</h4>
      <p className="field-hint">Nếu để trống, hệ thống sẽ dùng prompt mặc định trong backend.</p>
      <label className="field-label">Prompt dựng scene<textarea rows={10} value={sceneExtraction} onChange={(event) => setSceneExtraction(event.target.value)} placeholder="Prompt cho việc chuyển đề bài thành JSON..." /></label>
      <label className="field-label">Prompt phân tích suy luận<textarea rows={10} value={reasoning} onChange={(event) => setReasoning(event.target.value)} placeholder="Prompt cho việc phân tích suy luận bài toán..." /></label>
      <button type="button" className="secondary-button" onClick={() => void savePrompts()}>Lưu prompt</button>
    </section>
  );
}
