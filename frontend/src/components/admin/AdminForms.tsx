import React, { useState, useEffect } from 'react';
import type { AdminPlanResponse } from '../../api/client';
import {
  AdminProviderModelSettings,
  AdminRouter9ModelSettings,
  RuntimeSettings,
  OcrProvider,
  ScannedModelInfo,
} from '../../types/settings';
import { 
  scanProviderModels,
  scanRouter9Models,
  checkAdminProvider,
  checkAllAdminProviders,
} from '../../api/client';
import { buildModelOptionsFromDefaults, buildProviderOptions, planLabel, providerLabels } from '../../utils/settingsOptions';
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

function splitRolloutRules(value: string) {
  return Array.from(new Set(value.split(',').map((item) => item.trim().toLowerCase()).filter(Boolean)));
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

const defaultRuntimeSettings: RuntimeSettings = {
  default_provider: 'auto',
  openrouter: { model: '', scanned_models: [], allowed_model_ids: [], last_scanned_at: '' },
  nvidia: { model: '', scanned_models: [], allowed_model_ids: [], last_scanned_at: '' },
  ollama: { model: '', scanned_models: [], allowed_model_ids: [], last_scanned_at: '' },
  openai_compat: { model: '', scanned_models: [], allowed_model_ids: [], last_scanned_at: '' },
  router9: { model: '', scanned_models: [], last_scanned_at: '', only_mode: false, allowed_model_ids: [] },
  ocr: { provider: 'openrouter', model: '', max_image_mb: 5 },
  openrouter_http_referer: '',
  openrouter_x_title: '',
  openrouter_reasoning_enabled: false,
};

function defaultAdminProviderSettings() {
  return { base_url: '', scanned_models: [] as any[], allowed_model_ids: [] as string[], last_scanned_at: '', only_mode: false };
}

function getAdminProviderSettings(value: Record<string, unknown>, provider: string, defaults?: SettingsDefaults | null) {
  const item = value[provider];
  const data = item && typeof item === 'object' ? item as Record<string, unknown> : {};
  const providerDefaults = providerDefaultsFor(defaults, provider);
  return {
    ...defaultAdminProviderSettings(),
    ...data,
    base_url: typeof data.base_url === 'string' && data.base_url ? data.base_url : providerDefaults?.base_url ?? '',
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
  return uniqueScannedModels(models
    .map((modelItem) => {
      const id = typeof modelItem === 'string' ? modelItem : modelItem?.id;
      if (!id) return null;
      return {
        ...(typeof modelItem === 'object' ? modelItem : {}),
        id,
        label: typeof modelItem === 'object' && modelItem.label ? modelItem.label : typeof modelItem === 'object' && modelItem.name ? modelItem.name : id,
        provider: typeof modelItem === 'object' && modelItem.provider ? modelItem.provider : '',
      };
    })
    .filter(Boolean) as ProviderSettingsDefaults['scanned_models']);
}

function uniqueScannedModels(models: ScannedModelInfo[]) {
  const byId = new Map<string, ScannedModelInfo>();
  for (const model of models) {
    const id = String(model.id || '').trim();
    if (!id || byId.has(id)) continue;
    byId.set(id, { ...model, id, label: model.label || id });
  }
  return [...byId.values()];
}

function adminProviderToDefaults(value: Record<string, unknown>, provider: string): ProviderSettingsDefaults {
  const settings = getAdminProviderSettings(value, provider);
  return {
    api_key_configured: true,
    base_url: settings.base_url,
    scanned_models: normalizeScannedModels(settings.scanned_models),
    allowed_model_ids: settings.allowed_model_ids,
  };
}

function adminModelOptions(providerValue: ReturnType<typeof defaultAdminProviderSettings>, preferredIds: string[] = []) {
  const byId = new Map<string, { id: string; name: string; model?: ScannedModelInfo }>();
  function add(id: string, name = id, model?: ScannedModelInfo) {
    if (id && !byId.has(id)) byId.set(id, { id, name, model });
  }
  preferredIds.forEach((id) => add(id));
  providerValue.allowed_model_ids.forEach((id) => add(id));
  providerValue.scanned_models.forEach((modelItem: any) => {
    const id = typeof modelItem === 'string' ? modelItem : modelItem?.id;
    const name = typeof modelItem === 'object' ? modelItem.label || modelItem.name || id : id;
    add(id, name, typeof modelItem === 'object' ? modelItem : undefined);
  });
  return [...byId.values()];
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
  const ordered: Array<{ id: string; name: string; model?: ScannedModelInfo }> = [];
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

function mergeAdminProfileDefaults(defaults: SettingsDefaults | null | undefined, aiSettingsDefaults: SettingsDefaults): SettingsDefaults {
  if (!defaults) return aiSettingsDefaults;
  return {
    ...defaults,
    default_provider: defaults.default_provider || aiSettingsDefaults.default_provider,
    openrouter: mergeProviderDefaults(defaults.openrouter, aiSettingsDefaults.openrouter),
    nvidia: mergeProviderDefaults(defaults.nvidia, aiSettingsDefaults.nvidia),
    ollama: mergeProviderDefaults(defaults.ollama, aiSettingsDefaults.ollama),
    openai_compat: mergeProviderDefaults(defaults.openai_compat, aiSettingsDefaults.openai_compat),
    router9: {
      ...mergeProviderDefaults(defaults.router9, aiSettingsDefaults.router9),
      only_mode: defaults.router9.only_mode || aiSettingsDefaults.router9.only_mode,
    },
    ocr: defaults.ocr ?? aiSettingsDefaults.ocr,
  };
}

function mergeProviderDefaults<T extends ProviderSettingsDefaults>(defaults: T, aiSettingsDefaults: T): T {
  return {
    ...defaults,
    api_key_configured: defaults.api_key_configured || aiSettingsDefaults.api_key_configured,
    base_url: defaults.base_url || aiSettingsDefaults.base_url,
    scanned_models: defaults.scanned_models.length > 0 ? defaults.scanned_models : aiSettingsDefaults.scanned_models,
    allowed_model_ids: mergeModelIds(defaults.allowed_model_ids, aiSettingsDefaults.allowed_model_ids),
  };
}

function mergeModelIds(primary: string[], secondary: string[]) {
  return [...new Set([...primary, ...secondary].filter(Boolean))];
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

function formatProfileModelId(provider: string, model: string) {
  if (!model) return '';
  if (model.includes('::')) return model;
  // Reuse tier helper: strip legacy provider/ prefixes before adding provider::
  const legacyProvider = adminProviderFromPrefixedModel(model);
  const bare = legacyProvider ? model.slice(legacyProvider.length + 1) : model;
  const resolvedProvider = legacyProvider || provider;
  if (resolvedProvider === 'openrouter' || resolvedProvider === 'nvidia' || resolvedProvider === 'ollama' || resolvedProvider === 'openai_compat' || resolvedProvider === 'router9') {
    return `${resolvedProvider}::${bare}`;
  }
  return bare;
}

function parseProfileModelId(value: string) {
  const modelId = value.trim();
  const splitAt = modelId.indexOf('::');
  if (splitAt > 0) {
    const provider = modelId.slice(0, splitAt) === 'openai-compat' ? 'openai_compat' : modelId.slice(0, splitAt);
    return { provider, model: modelId.slice(splitAt + 2) };
  }
  for (const provider of ['openrouter', 'nvidia', 'ollama', 'openai_compat', 'router9'] as const) {
    const prefix = `${provider}/`;
    if (modelId.startsWith(prefix)) return { provider, model: modelId.slice(prefix.length) };
  }
  return { provider: 'openrouter', model: modelId };
}

function adminProviderFromPrefixedModel(modelId: string) {
  for (const provider of ['openrouter', 'nvidia', 'ollama', 'openai_compat', 'router9'] as const) {
    if (modelId.startsWith(`${provider}/`)) return provider;
  }
  if (modelId.startsWith('openai-compat/')) return 'openai_compat';
  return '';
}

function formatTierModelId(provider: string, model: string) {
  const modelId = model.trim();
  if (!modelId) return '';
  const splitAt = modelId.indexOf('::');
  if (splitAt > 0) return modelId;
  const legacyProvider = adminProviderFromPrefixedModel(modelId);
  if (legacyProvider) return `${legacyProvider}::${modelId.slice(modelId.indexOf('/') + 1)}`;
  if (provider === 'openrouter' || provider === 'nvidia' || provider === 'ollama' || provider === 'openai_compat' || provider === 'router9') return `${provider}::${modelId}`;
  return modelId;
}

function adminProviderFromTierModel(modelId: string) {
  const splitAt = modelId.indexOf('::');
  if (splitAt > 0) return modelId.slice(0, splitAt) === 'openai-compat' ? 'openai_compat' : modelId.slice(0, splitAt);
  return adminProviderFromPrefixedModel(modelId);
}

function normalizeTierModelRefs(models: string[], preferredProvider = '') {
  const primaryProvider = preferredProvider || models.map(adminProviderFromTierModel).find(Boolean) || '';
  return models
    .map((modelId) => modelId.trim())
    .filter(Boolean)
    .map((modelId) => formatTierModelId(adminProviderFromTierModel(modelId) || primaryProvider, modelId))
    .filter((modelId) => modelId.includes('::'));
}

function normalizeTierState(state: TierState): TierState {
  const used = new Set<string>();
  const normalized: TierState = {
    tier1: { defaultModel: '', models: [] },
    tier2: { defaultModel: '', models: [] },
    tier3: { defaultModel: '', models: [] },
  };
  for (const level of TIER_LEVELS) {
    const preferredProvider = state[level.key].models.map(adminProviderFromTierModel).find(Boolean) || adminProviderFromTierModel(state[level.key].defaultModel);
    const defaultModel = normalizeTierModelRefs([state[level.key].defaultModel], preferredProvider)[0] || '';
    const orderedModels = normalizeTierModelRefs([defaultModel, ...state[level.key].models], preferredProvider);
    for (const modelId of orderedModels) {
      if (used.has(modelId)) continue;
      used.add(modelId);
      normalized[level.key].models.push(modelId);
    }
    normalized[level.key].defaultModel = defaultModel && normalized[level.key].models.includes(defaultModel)
      ? defaultModel
      : normalized[level.key].models[0] || '';
  }
  return normalized;
}

// --- Form Components ---

export function AdminAiSettingsForm({ value, defaults, saving, onSave, onToast }: { value: Record<string, unknown>; defaults: SettingsDefaults | null; saving: boolean; onSave: (patch: Record<string, unknown>) => Promise<void>; onToast?: AdminToast }) {
  const providers = ['openrouter', 'nvidia', 'ollama', 'openai_compat', 'router9'] as const;
  const ocrValue = getAdminOcrSettings(value);
  const [draft, setDraft] = useState(() => Object.fromEntries(providers.map((provider) => [provider, getAdminProviderSettings(value, provider, defaults)])) as Record<(typeof providers)[number], ReturnType<typeof getAdminProviderSettings>>);
  const [ocrProvider, setOcrProvider] = useState(ocrValue.provider);
  const [ocrModel, setOcrModel] = useState(ocrValue.model);
  const [ocrMaxImageMb, setOcrMaxImageMb] = useState(String(ocrValue.max_image_mb));
  const [scanning, setScanning] = useState<string | null>(null);
  const [checking, setChecking] = useState<string | null>(null);
  const [checkingAll, setCheckingAll] = useState(false);
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
    setDraft((current) => ({ ...current, [provider]: { ...current[provider], ...patch } }));
  }

  async function saveProvider(provider: (typeof providers)[number]) {
    const current = getAdminProviderSettings(value, provider, defaults);
    const providerDraft = draft[provider] as ReturnType<typeof getAdminProviderSettings> & { api_key?: string };
    const nextProvider = {
      ...current,
      ...providerDraft,
      base_url: providerDraft.base_url.trim(),
    };
    if (!providerDraft.api_key?.trim()) {
      delete (nextProvider as { api_key?: string }).api_key;
    }
    if (provider !== 'router9') {
      delete (nextProvider as { only_mode?: boolean }).only_mode;
    }
    const providerPatch: Record<string, unknown> = {
      base_url: nextProvider.base_url,
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
      const scannedModels =
        provider === 'router9'
          ? await scanRouter9Models(runtime)
          : await scanProviderModels(provider as 'openrouter' | 'openai_compat' | 'nvidia' | 'ollama', runtime);
      const models = uniqueScannedModels(scannedModels);
      const scannedIds = models.map((model) => model.id);
      const scannedIdSet = new Set(scannedIds);
      const allowed_model_ids = draft[provider].allowed_model_ids.filter((id) => scannedIdSet.has(id));
      const next = {
        ...draft[provider],
        scanned_models: models,
        allowed_model_ids,
        last_scanned_at: new Date().toISOString(),
      };
      updateProvider(provider, next);
      onToast?.('Quét model', `Đã quét ${models.length} model duy nhất từ ${providerLabels[provider]}. Chọn model cần dùng rồi bấm Lưu provider.`, 'info');
    } catch (error) {
      onToast?.('Quét model', getErrorMessage(error, `Không thể quét model cho ${providerLabels[provider]}.`), 'error');
    } finally {
      setScanning(null);
    }
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

  async function checkAllProviders() {
    setCheckingAll(true);
    try {
      const runtime = adminSettingsToRuntime(value, defaults);
      providers.forEach((provider) => {
        runtime[provider] = { ...runtime[provider], ...draft[provider] };
      });
      const results = await checkAllAdminProviders(runtime);
      setCheckResults(Object.fromEntries(results.map((result) => [result.provider, result])));
      const failed = results.filter((result) => result.status !== 'ok');
      onToast?.(
        'Kiểm tra provider',
        failed.length === 0
          ? 'Tất cả provider đã kết nối thành công.'
          : `${results.length - failed.length}/${results.length} provider kết nối thành công.`,
        failed.length === 0 ? 'info' : 'warning',
      );
    } catch (error) {
      onToast?.('Kiểm tra provider', getErrorMessage(error, 'Không thể kiểm tra tất cả provider.'), 'error');
    } finally {
      setCheckingAll(false);
    }
  }

  function toggleModelId(provider: (typeof providers)[number], modelId: string) {
    updateProvider(provider, {
      allowed_model_ids: draft[provider].allowed_model_ids.includes(modelId)
        ? draft[provider].allowed_model_ids.filter((id) => id !== modelId)
        : [...draft[provider].allowed_model_ids, modelId],
    });
  }

  function bulkSetModelIds(provider: (typeof providers)[number], modelIds: string[], allowed: boolean) {
    const ids = modelIds.filter(Boolean);
    updateProvider(provider, {
      allowed_model_ids: allowed
        ? [...new Set([...draft[provider].allowed_model_ids, ...ids])]
        : draft[provider].allowed_model_ids.filter((id) => !ids.includes(id)),
    });
  }

  function bulkSelectByKeyword(provider: (typeof providers)[number], modelItems: Array<{ id: string; name: string }>, keywords: string[]) {
    const ids = modelItems
      .filter((modelItem) => keywords.some((keyword) => `${modelItem.id} ${modelItem.name}`.toLowerCase().includes(keyword)))
      .map((modelItem) => modelItem.id);
    bulkSetModelIds(provider, ids, true);
  }

  function bulkSelectByCapability(provider: (typeof providers)[number], modelItems: Array<{ id: string; model?: ScannedModelInfo }>, key: 'is_free_endpoint' | 'supports_thinking' | 'supports_vision') {
    const ids = modelItems.filter((modelItem) => modelItem.model?.[key] === true).map((modelItem) => modelItem.id);
    bulkSetModelIds(provider, ids, true);
  }

  function modelCapabilityBadges(model?: ScannedModelInfo) {
    if (!model) return ['Unknown capability'];
    const badges = [
      model.is_free_endpoint ? 'Free' : '',
      model.supports_thinking ? 'Thinking' : '',
      model.supports_vision ? 'Vision' : '',
    ].filter(Boolean);
    return badges.length > 0 ? badges : ['Unknown capability'];
  }

  function addManualModel(provider: (typeof providers)[number]) {
    const modelId = (manualModelInputs[provider] ?? '').trim();
    if (!modelId) return;
    setDraft((current) => {
      const providerValue = current[provider];
      const scanned_models = providerValue.scanned_models.some((modelItem: any) => modelItem.id === modelId)
        ? providerValue.scanned_models
        : [...providerValue.scanned_models, { id: modelId, label: modelId, provider }];
      const allowed_model_ids = providerValue.allowed_model_ids.includes(modelId)
        ? providerValue.allowed_model_ids
        : [...providerValue.allowed_model_ids, modelId];
      return {
        ...current,
        [provider]: {
          ...providerValue,
          scanned_models,
          allowed_model_ids,
        },
      };
    });
    setManualModelInputs((current) => ({ ...current, [provider]: '' }));
  }

  function removeManualModel(provider: (typeof providers)[number], modelId: string) {
    updateProvider(provider, {
      scanned_models: draft[provider].scanned_models.filter((modelItem: any) => modelItem.id !== modelId),
      allowed_model_ids: draft[provider].allowed_model_ids.filter((id) => id !== modelId),
    });
  }

  function selectOcrProvider(nextProvider: string) {
    const nextSettings = draft[nextProvider as (typeof providers)[number]] ?? getAdminProviderSettings(value, nextProvider, defaults);
    const firstScannedModel = nextSettings.scanned_models
      .map((modelItem: any) => typeof modelItem === 'string' ? modelItem : modelItem.id)
      .find(Boolean);
    const firstAllowedModel = nextSettings.allowed_model_ids.find(Boolean);
    setOcrProvider(nextProvider);
    setOcrModel(defaults?.ocr.provider === nextProvider ? defaults.ocr.model : firstAllowedModel || firstScannedModel || '');
  }

  const normalizedModelFilter = modelFilter.trim().toLowerCase();
  const ocrProviderValue = draft[ocrProvider as (typeof providers)[number]] ?? getAdminProviderSettings(value, ocrProvider, defaults);
  const ocrModelOptions = adminModelOptions(ocrProviderValue, [ocrModel, defaults?.ocr.provider === ocrProvider ? defaults.ocr.model : '']);

  return (
    <div className="admin-ai-settings">
      <section className="admin-settings-section">
        <div className="admin-section-heading-row">
          <div>
            <h4>Provider & model</h4>
            <p className="field-hint">OpenRouter, NVIDIA, OpenAI-compatible, 9router và Ollama cloud có thể quét endpoint /models. Ollama local dùng /api/tags.</p>
          </div>
          <button type="button" className="secondary-button" onClick={() => void checkAllProviders()} disabled={saving || checkingAll || checking !== null}>
            {checkingAll ? 'Đang kiểm tra...' : 'Kiểm tra tất cả'}
          </button>
        </div>
        <label className="field-label">Tìm model<input type="search" value={modelFilter} onChange={(event) => setModelFilter(event.target.value)} placeholder="Nhập tên hoặc ID model" /></label>
        <div className="admin-provider-grid">
          {providers.map((provider) => {
            const providerValue = draft[provider];
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
                      <button type="button" className="secondary-button" onClick={() => void scanProvider(provider)} disabled={saving || scanning === provider}>{scanning === provider ? 'Đang quét...' : 'Quét model'}</button>
                      <button type="button" className="secondary-button" onClick={() => void saveProvider(provider)} disabled={saving}>{saving ? 'Đang lưu...' : 'Lưu provider'}</button>
                    </div>
                  )}
                </div>
                <div className="admin-provider-config">
                <div className={`admin-field-grid ${provider === 'router9' ? 'admin-field-grid-router9' : ''}`}>
                  <label className="field-label">Base URL<input type="url" value={providerValue.base_url} onChange={(event) => updateProvider(provider, { base_url: event.target.value })} placeholder="https://..." /></label>
                  <label className="field-label">API key<input type="password" value={(providerValue as any).api_key ?? ''} onChange={(event) => updateProvider(provider, { ...( { api_key: event.target.value } as any) })} placeholder={defaults?.[provider]?.api_key_configured ? 'Đã cấu hình, nhập để thay' : 'Nhập API key'} /></label>
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
                  <div className="admin-model-bulk-actions">
                    <button type="button" className="secondary-button" onClick={() => bulkSetModelIds(provider, filteredAllowlistOptions.map((modelItem) => modelItem.id), true)} disabled={filteredAllowlistOptions.length === 0}>Chọn tất cả đang lọc</button>
                    <button type="button" className="secondary-button" onClick={() => bulkSetModelIds(provider, filteredAllowlistOptions.map((modelItem) => modelItem.id), false)} disabled={filteredAllowlistOptions.length === 0}>Bỏ chọn đang lọc</button>
                    <button type="button" className="secondary-button" onClick={() => bulkSetModelIds(provider, allowlistOptions.map((modelItem) => modelItem.id), false)} disabled={allowlistOptions.length === 0}>Bỏ chọn tất cả</button>
                    <button type="button" className="secondary-button" onClick={() => bulkSelectByCapability(provider, filteredAllowlistOptions, 'supports_vision')} disabled={filteredAllowlistOptions.length === 0}>Chọn Vision</button>
                    <button type="button" className="secondary-button" onClick={() => bulkSelectByCapability(provider, filteredAllowlistOptions, 'is_free_endpoint')} disabled={filteredAllowlistOptions.length === 0}>Chọn Free</button>
                    <button type="button" className="secondary-button" onClick={() => bulkSelectByCapability(provider, filteredAllowlistOptions, 'supports_thinking')} disabled={filteredAllowlistOptions.length === 0}>Chọn Thinking</button>
                    <button type="button" className="secondary-button" onClick={() => bulkSelectByKeyword(provider, filteredAllowlistOptions, ['gpt', 'codex'])} disabled={filteredAllowlistOptions.length === 0}>Chọn GPT/Codex</button>
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
                          <span className="model-label">
                            <strong>{modelItem.name}</strong>{modelItem.id !== modelItem.name && <small>{modelItem.id}</small>}
                            <span className="model-capability-badges" aria-label={`Capabilities for ${modelItem.id}`}>
                              {modelCapabilityBadges(modelItem.model).map((badge) => <small key={badge} className="model-capability-badge">{badge}</small>)}
                            </span>
                          </span>
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
          <label className="field-label">Provider OCR<select value={ocrProvider} onChange={(event) => selectOcrProvider(event.target.value)}>{(['local', 'openrouter', 'router9', 'nvidia', 'ollama', 'openai_compat'] as const).map((provider) => <option key={provider} value={provider}>{providerLabels[provider] || provider}</option>)}</select></label>
          <label className="field-label">Model OCR<select value={ocrModel} onChange={(event) => setOcrModel(event.target.value)}><option value="">{ocrProvider === 'local' ? 'paddleocr+pix2tex mặc định' : 'Chọn model'}</option>{ocrProvider === 'local' ? <option value="paddleocr+pix2tex">paddleocr+pix2tex</option> : ocrModelOptions.map((modelItem) => <option key={modelItem.id} value={modelItem.id}>{modelItem.name}</option>)}</select></label>
          <label className="field-label">Dung lượng ảnh tối đa (MB)<input type="number" min="1" max="32" value={ocrMaxImageMb} onChange={(event) => setOcrMaxImageMb(event.target.value)} /></label>
        </div>
        <button type="button" className="secondary-button" onClick={saveOcr} disabled={saving}>{saving ? 'Đang lưu...' : 'Lưu OCR'}</button>
      </section>
    </div>
  );
}

export function AdminPlanSettingsForm({ plans, onSavePlan }: { plans: AdminPlanResponse[]; onSavePlan: (planId: string, patch: Partial<Pick<AdminPlanResponse, 'name' | 'daily_render_limit' | 'daily_ocr_limit' | 'sort_order' | 'is_active'>>) => Promise<AdminPlanResponse> }) {
  const orderedPlans = [...(plans.length > 0 ? plans : defaultAdminPlans())].sort((left, right) => left.sort_order - right.sort_order || left.id.localeCompare(right.id));
  const [drafts, setDrafts] = useState(() => buildPlanDrafts(orderedPlans));
  const [savingPlan, setSavingPlan] = useState<string | null>(null);

  useEffect(() => {
    setDrafts(buildPlanDrafts(orderedPlans));
  }, [plans]);

  function updateDraft(planId: string, patch: Partial<{ name: string; render: string; ocr: string; active: boolean }>) {
    setDrafts((current) => ({ ...current, [planId]: { ...current[planId], ...patch } }));
  }

  async function savePlan(plan: AdminPlanResponse) {
    const draft = drafts[plan.id];
    if (!draft) return;
    setSavingPlan(plan.id);
    try {
      await onSavePlan(plan.id, {
        name: draft.name.trim(),
        daily_render_limit: optionalNumber(draft.render),
        daily_ocr_limit: optionalNumber(draft.ocr),
        is_active: draft.active,
      });
    } finally {
      setSavingPlan(null);
    }
  }

  return (
    <section className="admin-settings-section admin-plan-settings-section">
      <div className="admin-plan-section-head">
        <div>
          <h4>Giới hạn theo gói</h4>
          <p className="field-hint">Để trống nghĩa là không giới hạn theo ngày. Dữ liệu lưu trong bảng plans.</p>
        </div>
        <span className="admin-plan-count">{orderedPlans.length} gói</span>
      </div>
      <div className="admin-plan-grid" role="table" aria-label="Giới hạn theo gói người dùng">
        <div className="admin-plan-grid-head" role="row">
          <span>Gói</span>
          <span>Tên hiển thị</span>
          <span>Render/ngày</span>
          <span>OCR/ngày</span>
          <span>Trạng thái</span>
          <span></span>
        </div>
        {orderedPlans.map((plan) => {
          const draft = drafts[plan.id] ?? { name: plan.name, render: '', ocr: '', active: plan.is_active };
          return (
            <article className="admin-plan-row" key={plan.id} role="row">
              <div className="admin-plan-name-cell">
                <strong>{planLabel(plan.id)}</strong>
                <span>{plan.id}</span>
              </div>
              <label className="field-label admin-plan-field"><span>Tên hiển thị</span><input value={draft.name} onChange={(event) => updateDraft(plan.id, { name: event.target.value })} /></label>
              <label className="field-label admin-plan-field"><span>Render/ngày</span><input type="number" min="0" placeholder="∞" value={draft.render} onChange={(event) => updateDraft(plan.id, { render: event.target.value })} /></label>
              <label className="field-label admin-plan-field"><span>OCR/ngày</span><input type="number" min="0" placeholder="∞" value={draft.ocr} onChange={(event) => updateDraft(plan.id, { ocr: event.target.value })} /></label>
              <label className="admin-plan-toggle"><input type="checkbox" checked={draft.active} onChange={(event) => updateDraft(plan.id, { active: event.target.checked })} /><span>{draft.active ? 'Active' : 'Inactive'}</span></label>
              <button type="button" className="secondary-button admin-plan-save" onClick={() => void savePlan(plan)} disabled={savingPlan === plan.id}>{savingPlan === plan.id ? 'Đang lưu...' : 'Lưu'}</button>
            </article>
          );
        })}
      </div>
      {plans.length === 0 && <p className="field-hint admin-plan-warning">Backend chưa trả bảng plans; đang hiển thị 3 gói mặc định để cấu hình sau khi migration chạy.</p>}
    </section>
  );
}

function defaultAdminPlans(): AdminPlanResponse[] {
  return [
    { id: 'free', name: 'Free', daily_render_limit: 20, daily_ocr_limit: 20, sort_order: 10, is_active: true, created_at: '', updated_at: '' },
    { id: 'pro', name: 'Pro', daily_render_limit: 200, daily_ocr_limit: 200, sort_order: 20, is_active: true, created_at: '', updated_at: '' },
    { id: 'pro_plus', name: 'Pro+', daily_render_limit: null, daily_ocr_limit: null, sort_order: 30, is_active: true, created_at: '', updated_at: '' },
  ];
}

function buildPlanDrafts(plans: AdminPlanResponse[]) {
  return Object.fromEntries(plans.map((plan) => [plan.id, {
    name: plan.name,
    render: String(plan.daily_render_limit ?? ''),
    ocr: String(plan.daily_ocr_limit ?? ''),
    active: plan.is_active,
  }])) as Record<string, { name: string; render: string; ocr: string; active: boolean }>;
}

export function AdminFeatureFlagsForm({ value, onSave, onToast }: { value: Record<string, unknown>; onSave: (value: Record<string, unknown>) => Promise<void>; onToast?: AdminToast }) {
  const [maintenanceMode, setMaintenanceMode] = useState(value.maintenance_mode === true);
  const [message, setMessage] = useState(getStringValue(value.maintenance_message, 'Hệ thống đang bảo trì. Vui lòng thử lại sau.'));
  const [googleOAuth, setGoogleOAuth] = useState(value.google_oauth_enabled !== false);
  const [ocr, setOcr] = useState(value.ocr_enabled !== false);
  const [render, setRender] = useState(value.render_enabled !== false);
  const [turnstile, setTurnstile] = useState(value.turnstile_enabled === true);
  const [nlpShadowRules, setNlpShadowRules] = useState(Array.isArray(value.nlp_shadow_rules) ? value.nlp_shadow_rules.join(', ') : '');
  const [nlpAuthoritativeRules, setNlpAuthoritativeRules] = useState(Array.isArray(value.nlp_authoritative_rules) ? value.nlp_authoritative_rules.join(', ') : '');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setMaintenanceMode(value.maintenance_mode === true);
    setMessage(getStringValue(value.maintenance_message, 'Hệ thống đang bảo trì. Vui lòng thử lại sau.'));
    setGoogleOAuth(value.google_oauth_enabled !== false);
    setOcr(value.ocr_enabled !== false);
    setRender(value.render_enabled !== false);
    setTurnstile(value.turnstile_enabled === true);
    setNlpShadowRules(Array.isArray(value.nlp_shadow_rules) ? value.nlp_shadow_rules.join(', ') : '');
    setNlpAuthoritativeRules(Array.isArray(value.nlp_authoritative_rules) ? value.nlp_authoritative_rules.join(', ') : '');
  }, [value]);

  async function saveFlags() {
    setSaving(true);
    try {
      await onSave({
        version: 2,
        maintenance_mode: maintenanceMode,
        maintenance_message: message,
        google_oauth_enabled: googleOAuth,
        ocr_enabled: ocr,
        render_enabled: render,
        turnstile_enabled: turnstile,
        nlp_shadow_rules: splitRolloutRules(nlpShadowRules),
        nlp_authoritative_rules: splitRolloutRules(nlpAuthoritativeRules),
      });
    } catch (error) {
      onToast?.('Cờ tính năng', getErrorMessage(error, 'Không thể lưu cờ tính năng.'), 'error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="admin-settings-section"><h4>Cờ tính năng</h4><div className="admin-field-grid">
      <label className="checkbox-label"><input type="checkbox" checked={maintenanceMode} onChange={(event) => setMaintenanceMode(event.target.checked)} disabled={saving} /> Chế độ bảo trì</label>
      <label className="checkbox-label"><input type="checkbox" checked={render} onChange={(event) => setRender(event.target.checked)} disabled={saving} /> Cho phép dựng hình</label>
      <label className="checkbox-label"><input type="checkbox" checked={ocr} onChange={(event) => setOcr(event.target.checked)} disabled={saving} /> Cho phép OCR</label>
      <label className="checkbox-label"><input type="checkbox" checked={googleOAuth} onChange={(event) => setGoogleOAuth(event.target.checked)} disabled={saving} /> Cho phép đăng nhập Google</label>
      <label className="checkbox-label"><input type="checkbox" checked={turnstile} onChange={(event) => setTurnstile(event.target.checked)} disabled={saving} /> Bật xác minh Turnstile</label>
    </div>
    <label className="field-label">NLP shadow rules<input value={nlpShadowRules} onChange={(event) => setNlpShadowRules(event.target.value)} placeholder="algebra, render:solid_geometry" disabled={saving} /><span className="field-hint">Target hoặc target:intent, phân cách bằng dấu phẩy. Chỉ ghi mismatch, không đổi kết quả.</span></label>
    <label className="field-label">NLP authoritative rules<input value={nlpAuthoritativeRules} onChange={(event) => setNlpAuthoritativeRules(event.target.value)} placeholder="algebra:equation" disabled={saving} /><span className="field-hint">Chỉ bật slice đã đạt quality gate. Rule authoritative ưu tiên shadow.</span></label>
    <label className="field-label">Thông báo bảo trì<textarea rows={3} value={message} onChange={(event) => setMessage(event.target.value)} disabled={saving} /></label><button type="button" className="secondary-button" onClick={() => void saveFlags()} disabled={saving} aria-busy={saving}>{saving ? 'Đang lưu...' : 'Lưu cờ tính năng'}</button></section>
  );
}

export function AdminAiProfilesForm({ value, aiSettings, defaults, onSave, onToast }: { value: Record<string, unknown>; aiSettings: Record<string, unknown>; defaults?: SettingsDefaults | null; onSave: (value: Record<string, unknown>) => Promise<void>; onToast?: AdminToast }) {
  const geometry = getAiTaskProfile(value.geometry_reasoning);
  const solver = getAiTaskProfile(value.solver_explanation);
  const ocr = getAiTaskProfile(value.ocr);
  const [geometryModel, setGeometryModel] = useState(formatProfileModelId(geometry.provider, geometry.model));
  const [solverModel, setSolverModel] = useState(formatProfileModelId(solver.provider, solver.model));
  const [solverFallbacks, setSolverFallbacks] = useState<string[]>(solver.fallbacks);
  const [ocrModel, setOcrModel] = useState(formatProfileModelId(ocr.provider, ocr.model));
  const [ocrFallbacks, setOcrFallbacks] = useState<string[]>(ocr.fallbacks);
  const [saving, setSaving] = useState(false);
  const settingsDefaults = mergeAdminProfileDefaults(defaults, adminSettingsToDefaults(aiSettings));

  useEffect(() => {
    const nextGeometry = getAiTaskProfile(value.geometry_reasoning);
    const nextSolver = getAiTaskProfile(value.solver_explanation);
    const nextOcr = getAiTaskProfile(value.ocr);
    setGeometryModel(formatProfileModelId(nextGeometry.provider, nextGeometry.model));
    setSolverModel(formatProfileModelId(nextSolver.provider, nextSolver.model));
    setSolverFallbacks(nextSolver.fallbacks);
    setOcrModel(formatProfileModelId(nextOcr.provider, nextOcr.model));
    setOcrFallbacks(nextOcr.fallbacks);
  }, [value]);

  function modelOptions(selectedModel: string, fallbackModels: string[] = []) {
    return allProviderModelOptions(selectedModel, fallbackModels);
  }

  function fallbackModelOptions(selectedModel: string, fallbackModels: string[] = []) {
    return allProviderModelOptions(selectedModel, fallbackModels);
  }

  function allProviderModelOptions(selectedModel: string, fallbackModels: string[] = []) {
    const seen = new Set<string>();
    const combined: Array<{ id: string; label: string }> = [];
    (['openrouter', 'nvidia', 'ollama', 'openai_compat', 'router9'] as const).forEach((provider) => {
      const providerDefaults = settingsDefaults[provider];
      const registryAllowed = settingsDefaults.registry_models
        ?.filter((model) => model.provider_id === provider && model.enabled && model.allowed)
        .map((model) => ({ id: formatProfileModelId(provider, model.id), label: `${providerLabels[provider]}: ${model.label || model.id}` })) ?? [];
      const allowedIds = providerDefaults.allowed_model_ids.map((id) => {
        const scanned = providerDefaults.scanned_models.find((model) => model.id === id);
        return { id: formatProfileModelId(provider, id), label: `${providerLabels[provider]}: ${scanned?.label ?? id}` };
      });
      [...registryAllowed, ...allowedIds].forEach((option) => {
        if (!seen.has(option.id)) { seen.add(option.id); combined.push(option); }
      });
    });
    [...fallbackModels, selectedModel].filter(Boolean).forEach((id) => {
      if (!seen.has(id)) { seen.add(id); combined.push({ id, label: id }); }
    });
    return combined;
  }

  function updateFallbacks(kind: 'solver' | 'ocr', modelId: string, checked: boolean) {
    const setter = kind === 'solver' ? setSolverFallbacks : setOcrFallbacks;
    setter((current) => checked ? [...new Set([...current, modelId])] : current.filter((item) => item !== modelId));
  }

  async function saveProfiles() {
    setSaving(true);
    try {
      const geometry = parseProfileModelId(geometryModel);
      const solver = parseProfileModelId(solverModel);
      const ocr = parseProfileModelId(ocrModel);
      await onSave({ version: 1, geometry_reasoning: { provider: geometry.provider, model: geometry.model, fallbacks: [] }, solver_explanation: { provider: solver.provider, model: solver.model, fallbacks: solverFallbacks }, ocr: { provider: ocr.provider, model: ocr.model, fallbacks: ocrFallbacks } });
      onToast?.('Hồ sơ tác vụ', 'Đã lưu hồ sơ tác vụ.', 'info');
    } catch (error) {
      onToast?.('Hồ sơ tác vụ', getErrorMessage(error, 'Không thể lưu hồ sơ tác vụ.'), 'error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="admin-settings-section"><h4>Hồ sơ AI theo tác vụ</h4><p className="field-hint">Các mục này chọn model cho tác vụ phụ. Dựng hình chính dùng phần "Routing model dựng hình theo tier" bên dưới.</p><div className="admin-field-grid">
      <label className="field-label">Model reasoning hình học<select value={geometryModel} onChange={(event) => setGeometryModel(event.target.value)} disabled={saving}><option value="">Chọn model từ allowlist</option>{modelOptions(geometryModel).map((modelItem) => <option key={modelItem.id} value={modelItem.id}>{modelItem.label}</option>)}</select></label>
      <label className="field-label">Model diễn giải lời giải<select value={solverModel} onChange={(event) => setSolverModel(event.target.value)} disabled={saving}><option value="">Chọn model từ allowlist</option>{modelOptions(solverModel, solverFallbacks).map((modelItem) => <option key={modelItem.id} value={modelItem.id}>{modelItem.label}</option>)}</select></label>
      <label className="field-label">Model OCR<select value={ocrModel} onChange={(event) => setOcrModel(event.target.value)} disabled={saving}><option value="">Chọn model từ allowlist</option>{modelOptions(ocrModel, ocrFallbacks).map((modelItem) => <option key={modelItem.id} value={modelItem.id}>{modelItem.label}</option>)}</select></label>
    </div>
    <div className="admin-model-fallback-grid">
      <ModelFallbackChecklist title="Model dự phòng diễn giải lời giải" options={fallbackModelOptions(solverModel, solverFallbacks)} selected={solverFallbacks} onToggle={(modelId, checked) => updateFallbacks('solver', modelId, checked)} disabled={saving} />
      <ModelFallbackChecklist title="Model dự phòng OCR" options={fallbackModelOptions(ocrModel, ocrFallbacks)} selected={ocrFallbacks} onToggle={(modelId, checked) => updateFallbacks('ocr', modelId, checked)} disabled={saving} />
    </div>
    <button type="button" className="secondary-button" onClick={() => void saveProfiles()} disabled={saving} aria-busy={saving}>{saving ? 'Đang lưu...' : 'Lưu hồ sơ tác vụ'}</button></section>
  );
}

function ModelFallbackChecklist({ title, options, selected, onToggle, disabled }: { title: string; options: Array<{ id: string; label: string }>; selected: string[]; onToggle: (modelId: string, checked: boolean) => void; disabled?: boolean }) {
  // Đảm bảo các model đã được chọn luôn hiển thị dù không còn trong allowlist
  const visibleOptions = [...options];
  selected.filter((id) => id && !options.some((o) => o.id === id)).forEach((id) => visibleOptions.push({ id, label: id }));
  return (
    <section className="admin-model-fallback-list">
      <div className="admin-provider-models-head">
        <strong>{title}</strong>
        <span>{visibleOptions.length}</span>
      </div>
      <div className="admin-model-checklist">
        {visibleOptions.length > 0 ? visibleOptions.map((option) => (
          <div key={option.id} className="admin-model-checkbox">
            <label>
              <input type="checkbox" checked={selected.includes(option.id)} onChange={(event) => onToggle(option.id, event.target.checked)} disabled={disabled} />
              <span className="model-label"><strong>{option.id}</strong></span>
            </label>
          </div>
        )) : <p className="field-hint">Chưa có model đã quét hoặc allowlist cho provider này.</p>}
      </div>
    </section>
  );
}

const AI_PROFILE_PROVIDERS = ['openrouter', 'nvidia', 'ollama', 'openai_compat', 'router9'] as const;

const TIER_LEVELS = [
  { key: 'tier1', label: 'Tiêu chuẩn' },
  { key: 'tier2', label: 'Nâng cao' },
  { key: 'tier3', label: 'Tối đa' },
] as const;

type TierLevelKey = (typeof TIER_LEVELS)[number]['key'];
type TierModelState = { defaultModel: string; models: string[] };
type TierState = Record<TierLevelKey, TierModelState>;

function emptyTierState(): TierState {
  return {
    tier1: { defaultModel: '', models: [] },
    tier2: { defaultModel: '', models: [] },
    tier3: { defaultModel: '', models: [] },
  };
}

function getTierState(value: unknown, tier: TierLevelKey): TierModelState {
  const data = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  const direct = data[tier];
  if (direct && typeof direct === 'object') {
    const directData = direct as Record<string, unknown>;
    if (Array.isArray(directData.models)) {
      const models = normalizeTierModelRefs(directData.models.map(String));
      const defaultModel = normalizeTierModelRefs([getStringValue(directData.default_model, '')], models.map(adminProviderFromTierModel).find(Boolean) || '')[0] || models[0] || '';
      return { defaultModel, models };
    }
    const directProfile = getAiTaskProfile(direct);
    const defaultModel = formatTierModelId(directProfile.provider, directProfile.model);
    return { defaultModel, models: defaultModel ? [defaultModel] : [] };
  }
  const legacyRender = data.render && typeof data.render === 'object' ? data.render as Record<string, unknown> : {};
  const legacyProfile = getAiTaskProfile(legacyRender[tier]);
  const defaultModel = formatTierModelId(legacyProfile.provider, legacyProfile.model);
  return { defaultModel, models: defaultModel ? [defaultModel] : [] };
}

export function AdminAiTierProfilesForm({ value, aiSettings, defaults, onSave, onToast }: { value: Record<string, unknown>; aiSettings: Record<string, unknown>; defaults?: SettingsDefaults | null; onSave: (value: Record<string, unknown>) => Promise<void>; onToast?: AdminToast }) {
  const [tierState, setTierState] = useState<TierState>(emptyTierState());
  const [saving, setSaving] = useState(false);
  const settingsDefaults = mergeAdminProfileDefaults(defaults, adminSettingsToDefaults(aiSettings));

  function buildStateFromValue(source: Record<string, unknown>) {
    const state = Object.fromEntries(TIER_LEVELS.map((level) => [level.key, getTierState(source, level.key)])) as TierState;
    return normalizeTierState(state);
  }

  useEffect(() => {
    setTierState(buildStateFromValue(value));
  }, [value]);

  function allProviderModelOptions(selectedModels: string[] = []) {
    const seen = new Set<string>();
    const combined: Array<{ id: string; label: string }> = [];
    AI_PROFILE_PROVIDERS.forEach((provider) => {
      const providerDefaults = settingsDefaults[provider];
      const registryAllowed = settingsDefaults.registry_models
        ?.filter((model) => model.provider_id === provider && model.enabled && model.allowed)
        .map((model) => ({ id: formatTierModelId(provider, model.id), label: `${providerLabels[provider]}: ${model.label || model.id}` })) ?? [];
      const allowedIds = providerDefaults.allowed_model_ids.map((id) => {
        const scanned = providerDefaults.scanned_models.find((model) => model.id === id);
        return { id: formatTierModelId(provider, id), label: `${providerLabels[provider]}: ${scanned?.label ?? id}` };
      });
      [...registryAllowed, ...allowedIds].forEach((option) => {
        if (!seen.has(option.id)) { seen.add(option.id); combined.push(option); }
      });
    });
    selectedModels.filter(Boolean).forEach((id) => {
      if (!seen.has(id)) { seen.add(id); combined.push({ id, label: id }); }
    });
    return combined;
  }

  function toggleTierModel(tier: TierLevelKey, modelId: string, checked: boolean) {
    setTierState((current) => {
      const next: TierState = {
        tier1: { ...current.tier1, models: current.tier1.models.filter((id) => id !== modelId) },
        tier2: { ...current.tier2, models: current.tier2.models.filter((id) => id !== modelId) },
        tier3: { ...current.tier3, models: current.tier3.models.filter((id) => id !== modelId) },
      };
      for (const level of TIER_LEVELS) {
        if (next[level.key].defaultModel === modelId) next[level.key].defaultModel = '';
      }
      if (checked) {
        next[tier].models = [...next[tier].models, modelId];
        if (!next[tier].defaultModel) next[tier].defaultModel = modelId;
      }
      return normalizeTierState(next);
    });
  }

  function selectTierDefault(tier: TierLevelKey, modelId: string) {
    setTierState((current) => {
      const next: TierState = {
        tier1: { ...current.tier1, models: current.tier1.models.filter((id) => id !== modelId) },
        tier2: { ...current.tier2, models: current.tier2.models.filter((id) => id !== modelId) },
        tier3: { ...current.tier3, models: current.tier3.models.filter((id) => id !== modelId) },
      };
      if (!modelId) {
        next[tier].defaultModel = '';
        return normalizeTierState(next);
      }
      for (const level of TIER_LEVELS) {
        if (next[level.key].defaultModel === modelId) next[level.key].defaultModel = '';
      }
      next[tier].models = [modelId, ...next[tier].models];
      next[tier].defaultModel = modelId;
      return normalizeTierState(next);
    });
  }

  function allSelectedModels() {
    return TIER_LEVELS.flatMap((level) => tierState[level.key].models);
  }

  async function saveTierProfiles() {
    setSaving(true);
    try {
      const normalized = normalizeTierState(tierState);
      const payload: Record<string, unknown> = { version: 3 };
      for (const level of TIER_LEVELS) payload[level.key] = { tier: level.key, default_model: normalized[level.key].defaultModel, models: normalized[level.key].models };
      await onSave(payload);
      setTierState(normalized);
      onToast?.('Tier model', 'Đã lưu cấu hình tier.', 'info');
    } catch (error) {
      onToast?.('Tier model', getErrorMessage(error, 'Không thể lưu cấu hình tier.'), 'error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="admin-settings-section">
      <h4>Routing model dựng hình theo tier</h4>
      <p className="field-hint">Đây là nguồn chọn model chính cho render. Mỗi tier ghi vào task render_tier1/2/3; model phải có dạng provider::model.</p>
      {TIER_LEVELS.map((level) => (
        <div key={level.key} className="admin-tier-task">
          <h5>{level.label}</h5>
          <div className="admin-field-grid">
            <label className="field-label">
              Model chính của tier
              <select value={tierState[level.key].defaultModel} onChange={(event) => selectTierDefault(level.key, event.target.value)} disabled={saving}>
                <option value="">Chưa chọn model chính</option>
                {allProviderModelOptions(allSelectedModels()).map((modelItem) => <option key={modelItem.id} value={modelItem.id}>{modelItem.label}</option>)}
              </select>
            </label>
          </div>
          <div className="admin-model-fallback-grid">
            <ModelFallbackChecklist
              title={`Pool model ${level.label.toLowerCase()} (${tierState[level.key].models.length})`}
              options={allProviderModelOptions(allSelectedModels())}
              selected={tierState[level.key].models}
              onToggle={(modelId, checked) => toggleTierModel(level.key, modelId, checked)}
              disabled={saving}
            />
          </div>
        </div>
      ))}
      <button type="button" className="secondary-button" onClick={() => void saveTierProfiles()} disabled={saving} aria-busy={saving}>{saving ? 'Đang lưu...' : 'Lưu cấu hình tier'}</button>
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
      await onSave({ version: 2, scene_extraction: sceneExtraction.trim(), reasoning: reasoning.trim() });
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
