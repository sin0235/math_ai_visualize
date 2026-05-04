import React, { useState, useEffect } from 'react';
import { 
  AdminProviderModelSettings, 
  AdminRouter9ModelSettings, 
  AdminOcrModelSettings, 
  RuntimeSettings, 
  OcrProvider 
} from '../../types/settings';
import { 
  scanProviderModels, 
  scanRouter9Models,
  checkAdminProvider,
} from '../../api/client';
import { AdminDetails } from './AdminComponents';
import { buildModelOptionsFromDefaults, buildProviderOptions } from '../../utils/settingsOptions';
import type { ProviderSettingsDefaults, SettingsDefaults } from '../../types/settings';

// --- Utility Functions ---

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
  router9: { api_key: '', base_url: '', model: '', scanned_models: [], last_scanned_at: '', only_mode: false, allowed_model_ids: [] },
  ocr: { provider: 'openrouter', model: '', max_image_mb: 8 },
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
  if (provider === 'openrouter' || provider === 'nvidia' || provider === 'ollama' || provider === 'router9') return defaults[provider];
  return undefined;
}

function getAdminOcrSettings(value: Record<string, unknown>) {
  const item = value.ocr;
  const data = item && typeof item === 'object' ? item as Record<string, unknown> : {};
  const maxImageMb = typeof data.max_image_mb === 'number' ? data.max_image_mb : 8;
  return {
    provider: getStringValue(data.provider, 'openrouter'),
    model: getStringValue(data.model, ''),
    max_image_mb: clamp(maxImageMb, 1, 32),
  };
}

function adminSettingsToRuntime(value: Record<string, unknown>): RuntimeSettings {
  const router9 = getAdminProviderSettings(value, 'router9');
  return {
    ...defaultRuntimeSettings,
    default_provider: getStringValue(value.default_provider, 'auto'),
    openrouter: { ...defaultRuntimeSettings.openrouter, ...getAdminProviderSettings(value, 'openrouter') },
    nvidia: { ...defaultRuntimeSettings.nvidia, ...getAdminProviderSettings(value, 'nvidia') },
    ollama: { ...defaultRuntimeSettings.ollama, ...getAdminProviderSettings(value, 'ollama') },
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

export function AdminAiSettingsForm({ value, defaults, saving, onSave }: { value: Record<string, unknown>; defaults: SettingsDefaults | null; saving: boolean; onSave: (patch: Record<string, unknown>) => Promise<void> }) {
  const provider = 'router9';
  const providerValue = getAdminProviderSettings(value, provider, defaults);
  const ocrValue = getAdminOcrSettings(value);
  const [baseUrl, setBaseUrl] = useState(providerValue.base_url);
  const [model, setModel] = useState(providerValue.model);
  const [allowedModelIds, setAllowedModelIds] = useState<string[]>(providerValue.allowed_model_ids);
  const [router9OnlyMode, setRouter9OnlyMode] = useState(providerValue.only_mode);
  const [ocrProvider, setOcrProvider] = useState(ocrValue.provider);
  const [ocrModel, setOcrModel] = useState(ocrValue.model);
  const [ocrMaxImageMb, setOcrMaxImageMb] = useState(String(ocrValue.max_image_mb));
  const [scanning, setScanning] = useState(false);
  const [checking, setChecking] = useState(false);
  const [modelFilter, setModelFilter] = useState('');
  const [checkResult, setCheckResult] = useState<{ status: string; message: string } | null>(null);

  useEffect(() => {
    const next = getAdminProviderSettings(value, provider, defaults);
    setBaseUrl(next.base_url);
    setModel(next.model);
    setAllowedModelIds(next.allowed_model_ids);
    setRouter9OnlyMode(next.only_mode);
    setCheckResult(null);
  }, [value, defaults]);

  useEffect(() => {
    const nextOcr = getAdminOcrSettings(value);
    setOcrProvider(nextOcr.provider);
    setOcrModel(nextOcr.model);
    setOcrMaxImageMb(String(nextOcr.max_image_mb));
  }, [value]);

  async function saveProvider() {
    const current = getAdminProviderSettings(value, provider, defaults);
    await onSave({
      [provider]: {
        ...current,
        base_url: baseUrl.trim(),
        model: model.trim(),
        allowed_model_ids: allowedModelIds,
        only_mode: router9OnlyMode,
      },
    });
  }

  async function saveOcr() {
    await onSave({
      ocr: {
        provider: ocrProvider,
        model: ocrModel.trim(),
        max_image_mb: clamp(Number(ocrMaxImageMb) || 8, 1, 32),
      },
    });
  }

  async function scanModels() {
    setScanning(true);
    try {
      const runtime = adminSettingsToRuntime(value);
      const models = await scanRouter9Models(runtime);
      await onSave({
        [provider]: {
          ...getAdminProviderSettings(value, provider, defaults),
          base_url: baseUrl.trim(),
          model: model.trim(),
          allowed_model_ids: allowedModelIds,
          only_mode: router9OnlyMode,
          scanned_models: models,
          last_scanned_at: new Date().toISOString(),
        },
      });
    } finally {
      setScanning(false);
    }
  }

  async function checkProvider() {
    setChecking(true);
    setCheckResult(null);
    try {
      const result = await checkAdminProvider(provider);
      setCheckResult(result);
    } catch (error) {
      setCheckResult({ status: 'error', message: String(error) });
    } finally {
      setChecking(false);
    }
  }

  function toggleModelId(modelId: string) {
    setAllowedModelIds((current) =>
      current.includes(modelId)
        ? current.filter((id) => id !== modelId)
        : [...current, modelId]
    );
  }

  function selectOcrProvider(nextProvider: string) {
    const nextSettings = getAdminProviderSettings(value, nextProvider, defaults);
    const firstScannedModel = nextSettings.scanned_models
      .map((modelItem: any) => typeof modelItem === 'string' ? modelItem : modelItem.id)
      .find(Boolean);
    setOcrProvider(nextProvider);
    setOcrModel(defaults?.ocr.provider === nextProvider ? defaults.ocr.model : nextSettings.model || firstScannedModel || '');
  }

  const modelOptions = adminModelOptions(providerValue, [model]);
  const allowlistOptions = orderedAllowlistModelOptions(providerValue, allowedModelIds);
  const normalizedModelFilter = modelFilter.trim().toLowerCase();
  const filteredAllowlistOptions = normalizedModelFilter
    ? allowlistOptions.filter((modelItem) => modelItem.id.toLowerCase().includes(normalizedModelFilter) || modelItem.name.toLowerCase().includes(normalizedModelFilter))
    : allowlistOptions;
  const ocrProviderValue = getAdminProviderSettings(value, ocrProvider, defaults);
  const ocrModelOptions = adminModelOptions(ocrProviderValue, [ocrModel, defaults?.ocr.provider === ocrProvider ? defaults.ocr.model : '']);

  return (
    <div className="admin-ai-settings">
      <section className="admin-settings-section">
        <h4>Cấu hình 9router</h4>
        <div className="admin-field-grid">
          <label className="field-label">URL cơ sở<input type="url" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://..." /></label>
          <label className="field-label">Model mặc định<select value={model} onChange={(event) => setModel(event.target.value)}><option value="">Chọn model</option>{modelOptions.map((modelItem) => <option key={modelItem.id} value={modelItem.id}>{modelItem.name}</option>)}</select></label>
          <label className="checkbox-label"><input type="checkbox" checked={router9OnlyMode} onChange={(event) => setRouter9OnlyMode(event.target.checked)} /> Chỉ dùng 9router</label>
        </div>
        <div className="admin-field-grid">
          <span><strong>Model đã quét</strong>{providerValue.scanned_models.length} model</span>
          <span><strong>Lần quét gần nhất</strong>{providerValue.last_scanned_at || 'Chưa quét'}</span>
        </div>
        {checkResult && (
          <div className={`admin-status-box ${checkResult.status}`}>
            <strong>{checkResult.status === 'ok' ? 'Thành công' : 'Lỗi'}</strong>
            <p>{checkResult.message}</p>
          </div>
        )}
        <div className="admin-row-actions">
          <button type="button" className="secondary-button" onClick={checkProvider} disabled={saving || checking}>{checking ? 'Đang kiểm tra...' : 'Kiểm tra kết nối'}</button>
          <button type="button" className="secondary-button" onClick={scanModels} disabled={saving || scanning}>{scanning ? 'Đang quét...' : 'Quét model'}</button>
        </div>
      </section>

      <section className="admin-settings-section">
        <h4>Model hiển thị cho người dùng ({allowedModelIds.length} đã chọn)</h4>
        {allowlistOptions.length > 0 && (
          <>
            <p className="field-hint">Chọn model người dùng có thể thấy và sử dụng trong danh sách chọn.</p>
            <label className="field-label">Tìm model<input type="search" value={modelFilter} onChange={(event) => setModelFilter(event.target.value)} placeholder="Nhập tên hoặc ID model" /></label>
            <p className="field-hint">Hiển thị {filteredAllowlistOptions.length}/{allowlistOptions.length} model.</p>
            <div className="admin-model-checklist">
              {filteredAllowlistOptions.map((modelItem) => (
                <label key={modelItem.id} className="checkbox-label admin-model-checkbox">
                  <input
                    type="checkbox"
                    checked={allowedModelIds.includes(modelItem.id)}
                    onChange={() => toggleModelId(modelItem.id)}
                  />
                  <span className="model-label">
                    <strong>{modelItem.name}</strong>
                    {modelItem.id !== modelItem.name && <small>{modelItem.id}</small>}
                  </span>
                </label>
              ))}
            </div>
          </>
        )}
        <button type="button" className="secondary-button" onClick={saveProvider} disabled={saving}>{saving ? 'Đang lưu...' : 'Lưu danh sách model'}</button>
      </section>

      <section className="admin-settings-section">
        <h4>OCR</h4>
        <div className="admin-field-grid">
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

export function AdminAiProfilesForm({ value, aiSettings, onSave }: { value: Record<string, unknown>; aiSettings: Record<string, unknown>; onSave: (value: Record<string, unknown>) => Promise<void> }) {
  const geometry = getAiTaskProfile(value.geometry_reasoning);
  const ocr = getAiTaskProfile(value.ocr);
  const [geometryProvider, setGeometryProvider] = useState(geometry.provider);
  const [geometryModel, setGeometryModel] = useState(geometry.model);
  const [geometryFallbacks, setGeometryFallbacks] = useState<string[]>(geometry.fallbacks);
  const [ocrProvider, setOcrProvider] = useState(ocr.provider);
  const [ocrModel, setOcrModel] = useState(ocr.model);
  const [ocrFallbacks, setOcrFallbacks] = useState<string[]>(ocr.fallbacks);
  const settingsDefaults = adminSettingsToDefaults(aiSettings);
  const providerOptions = buildProviderOptions(settingsDefaults, false);

  function providerDefaults(selectedProvider: string): ProviderSettingsDefaults | undefined {
    if (selectedProvider === 'openrouter' || selectedProvider === 'nvidia' || selectedProvider === 'ollama' || selectedProvider === 'router9') return settingsDefaults[selectedProvider];
    return settingsDefaults.router9;
  }

  function modelOptions(selectedProvider: string, selectedModel: string, fallbackModels: string[] = []) {
    return buildModelOptionsFromDefaults(providerDefaults(selectedProvider), selectedModel, fallbackModels);
  }

  function updateFallbacks(kind: 'geometry' | 'ocr', modelId: string, checked: boolean) {
    const setter = kind === 'geometry' ? setGeometryFallbacks : setOcrFallbacks;
    setter((current) => checked ? [...new Set([...current, modelId])] : current.filter((item) => item !== modelId));
  }

  return (
    <section className="admin-settings-section"><h4>Hồ sơ AI</h4><div className="admin-field-grid">
      <label className="field-label">Provider hình học<select value={geometryProvider} onChange={(event) => setGeometryProvider(event.target.value)}><option value="auto">auto</option>{providerOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
      <label className="field-label">Model hình học<select value={geometryModel} onChange={(event) => setGeometryModel(event.target.value)}><option value="">Chọn model</option>{modelOptions(geometryProvider, geometryModel, geometryFallbacks).map((modelItem) => <option key={modelItem.id} value={modelItem.id}>{modelItem.label}</option>)}</select></label>
      <label className="field-label">Provider OCR<select value={ocrProvider} onChange={(event) => setOcrProvider(event.target.value)}><option value="auto">auto</option>{providerOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
      <label className="field-label">Model OCR<select value={ocrModel} onChange={(event) => setOcrModel(event.target.value)}><option value="">Chọn model</option>{modelOptions(ocrProvider, ocrModel, ocrFallbacks).map((modelItem) => <option key={modelItem.id} value={modelItem.id}>{modelItem.label}</option>)}</select></label>
    </div>
    <div className="admin-model-fallback-grid">
      <ModelFallbackChecklist title="Model dự phòng hình học" options={modelOptions(geometryProvider, geometryModel, geometryFallbacks)} selected={geometryFallbacks} onToggle={(modelId, checked) => updateFallbacks('geometry', modelId, checked)} />
      <ModelFallbackChecklist title="Model dự phòng OCR" options={modelOptions(ocrProvider, ocrModel, ocrFallbacks)} selected={ocrFallbacks} onToggle={(modelId, checked) => updateFallbacks('ocr', modelId, checked)} />
    </div>
    <button type="button" className="secondary-button" onClick={() => void onSave({ version: 1, geometry_reasoning: { provider: geometryProvider, model: geometryModel, fallbacks: geometryFallbacks }, ocr: { provider: ocrProvider, model: ocrModel, fallbacks: ocrFallbacks } })}>Lưu hồ sơ AI</button></section>
  );
}

function ModelFallbackChecklist({ title, options, selected, onToggle }: { title: string; options: Array<{ id: string; label: string }>; selected: string[]; onToggle: (modelId: string, checked: boolean) => void }) {
  return (
    <fieldset className="admin-model-fallback-list">
      <legend>{title}</legend>
      {options.length > 0 ? options.map((option) => (
        <label key={option.id} className="admin-model-checkbox">
          <input type="checkbox" checked={selected.includes(option.id)} onChange={(event) => onToggle(option.id, event.target.checked)} />
          <span className="model-label"><strong>{option.label}</strong><small>{option.id}</small></span>
        </label>
      )) : <p className="field-hint">Chưa có model đã quét hoặc allowlist cho provider này.</p>}
    </fieldset>
  );
}

export function AdminAiPromptsForm({ value, onSave }: { value: Record<string, unknown>; onSave: (value: Record<string, unknown>) => Promise<void> }) {
  const [sceneExtraction, setSceneExtraction] = useState(getStringValue(value.scene_extraction, ''));
  const [reasoning, setReasoning] = useState(getStringValue(value.reasoning, ''));

  useEffect(() => {
    setSceneExtraction(getStringValue(value.scene_extraction, ''));
    setReasoning(getStringValue(value.reasoning, ''));
  }, [value]);

  return (
    <section className="admin-settings-section">
      <h4>Prompt hệ thống AI</h4>
      <p className="field-hint">Nếu để trống, hệ thống sẽ dùng prompt mặc định trong backend.</p>
      <label className="field-label">Prompt dựng scene<textarea rows={10} value={sceneExtraction} onChange={(event) => setSceneExtraction(event.target.value)} placeholder="Prompt cho việc chuyển đề bài thành JSON..." /></label>
      <label className="field-label">Prompt phân tích suy luận<textarea rows={10} value={reasoning} onChange={(event) => setReasoning(event.target.value)} placeholder="Prompt cho việc phân tích suy luận bài toán..." /></label>
      <button type="button" className="secondary-button" onClick={() => void onSave({ version: 1, scene_extraction: sceneExtraction.trim(), reasoning: reasoning.trim() })}>Lưu prompt</button>
    </section>
  );
}
