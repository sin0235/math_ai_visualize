import type { OcrProvider, ProviderSettingsDefaults, RegistryModelDefaults, SettingsDefaults } from '../types/settings';

export type Option = { id: string; label: string };

export const rendererOptions: Option[] = [
  { id: 'geogebra_2d', label: 'GeoGebra 2D' },
  { id: 'geogebra_3d', label: 'GeoGebra 3D' },
  { id: 'threejs_3d', label: 'Three.js 3D' },
];

export const renderSourceOptions: Option[] = [
  { id: 'problem', label: 'Đề bài' },
  { id: 'scene_edit', label: 'Chỉnh scene' },
];

export const providerLabels: Record<string, string> = {
  auto: 'Tự động chọn provider',
  openrouter: 'OpenRouter',
  nvidia: 'NVIDIA',
  ollama: 'Ollama',
  openai_compat: 'OpenAI-compatible',
  router9: '9router',
  local: 'Local OCR',
  mock: 'Mock extractor',
};

type RenderProviderKey = 'openrouter' | 'nvidia' | 'ollama' | 'openai_compat' | 'router9';

export interface RenderModelOption {
  key: string;
  label: string;
  provider: string;
  description: string;
  group: string;
  modelId?: string;
  supportsThinking?: boolean;
}

const RENDER_PROVIDER_ORDER: RenderProviderKey[] = ['router9', 'openrouter', 'nvidia', 'ollama', 'openai_compat'];
const EXPLICIT_RENDER_MODEL_LIMIT = 32;
const EXPLICIT_RENDER_MODEL_LIMIT_PER_PROVIDER = 8;

export function buildRenderModelOptions(defaults: SettingsDefaults | null, tier = 'tier1'): RenderModelOption[] {
  const providerOrder = orderRenderProviders(defaults?.default_provider);
  const explicitModels = buildExplicitRenderModelOptions(defaults, providerOrder, tier);

  if (defaults?.router9.only_mode) {
    return [
      {
        key: 'default:auto',
        provider: 'auto',
        label: 'Mặc định hệ thống (9router)',
        description: '9router-only đang bật; backend dùng model trong tier profile.',
        group: 'Chiến lược',
      },
      ...explicitModels.filter((option) => option.provider === 'router9'),
    ];
  }

  return [
    {
      key: 'default:auto',
      provider: 'auto',
      label: 'Mặc định hệ thống',
      description: 'Backend dùng model và fallback trong tier profile.',
      group: 'Chiến lược',
    },
    ...explicitModels,
  ];
}

function buildExplicitRenderModelOptions(defaults: SettingsDefaults | null, providerOrder: RenderProviderKey[], tier: string): RenderModelOption[] {
  if (!defaults) return [];
  const preferredKeys = preferredRenderModelKeys(defaults, tier);
  const byProvider = new Map<RenderProviderKey, RegistryModelDefaults[]>();
  for (const provider of providerOrder) {
    const models = registryModelsForRenderProvider(defaults, provider);
    const preferred = models.filter((model) => preferredKeys.has(modelKey(provider, model.id)));
    const rest = models.filter((model) => !preferredKeys.has(modelKey(provider, model.id)));
    byProvider.set(provider, [...preferred, ...rest].slice(0, EXPLICIT_RENDER_MODEL_LIMIT_PER_PROVIDER));
  }
  return providerOrder
    .flatMap((provider) => (byProvider.get(provider) ?? []).map((model) => renderModelOption(provider, model, preferredKeys.has(modelKey(provider, model.id)))))
    .slice(0, EXPLICIT_RENDER_MODEL_LIMIT);
}

function registryModelsForRenderProvider(defaults: SettingsDefaults, provider: RenderProviderKey): RegistryModelDefaults[] {
  const models = defaults.registry_models?.filter((model) => model.provider_id === provider && model.enabled) ?? [];
  if (models.length === 0) return [];
  const hasAllowlist = models.some((model) => model.allowed);
  return (hasAllowlist ? models.filter((model) => model.allowed) : models)
    .sort((left, right) => Number(Boolean(right.supports_thinking)) - Number(Boolean(left.supports_thinking))
      || Number(Boolean(right.is_free_endpoint)) - Number(Boolean(left.is_free_endpoint))
      || (left.label || left.id).localeCompare(right.label || right.id));
}

function preferredRenderModelKeys(defaults: SettingsDefaults, tier: string) {
  const keys = new Set<string>();
  const tasks = [`render_${tier}`, 'render', 'reasoning'];
  defaults.registry_task_profiles?.filter((profile) => tasks.includes(profile.task)).forEach((profile) => {
    const provider = normalizeRenderProvider(profile.provider_id || defaults.default_provider);
    if (!provider) return;
    addProfileModelKey(keys, provider, profile.model_id);
    profile.fallbacks.forEach((fallback) => addProfileModelKey(keys, provider, fallback));
  });
  return keys;
}

function addProfileModelKey(keys: Set<string>, provider: RenderProviderKey, modelRef: string) {
  const value = modelRef.trim();
  if (!value) return;
  const explicitProvider = normalizeRenderProvider(value.split('/')[0]);
  if (explicitProvider && value.startsWith(`${explicitProvider}/`)) {
    keys.add(modelKey(explicitProvider, value.slice(explicitProvider.length + 1)));
    return;
  }
  keys.add(modelKey(provider, value));
}

function renderModelOption(provider: RenderProviderKey, model: RegistryModelDefaults, preferred: boolean): RenderModelOption {
  const labelParts = [model.label || model.id, ...compactCapabilityParts(model)];
  return {
    key: `model:${provider}:${model.id}`,
    provider,
    modelId: model.id,
    supportsThinking: model.supports_thinking,
    label: `${renderProviderLabel(provider)}: ${labelParts.join(' · ')}`,
    description: `${preferred ? 'Task profile ưu tiên. ' : ''}${renderProviderLabel(provider)} model ${model.id}${model.context_length ? `, context ${formatContextLength(model.context_length)}` : ''}. ${capabilitySentence(model)}`.trim(),
    group: renderProviderLabel(provider),
  };
}

function compactCapabilityParts(model: RegistryModelDefaults) {
  const parts: string[] = [];
  if (model.is_free_endpoint) parts.push('Free');
  if (model.supports_thinking) parts.push('Thinking');
  else parts.push('Không Thinking');
  if (model.supports_vision) parts.push('Vision');
  if (model.context_length) parts.push(formatContextLength(model.context_length));
  return parts;
}

function capabilitySentence(model: RegistryModelDefaults) {
  const parts = compactCapabilityParts(model);
  return parts.length ? parts.join(', ') : 'Chưa có capability metadata.';
}

function formatContextLength(value: number) {
  return value >= 1000 ? `${Math.round(value / 1000)}K ctx` : `${value} ctx`;
}

function orderRenderProviders(defaultProvider: string | undefined): RenderProviderKey[] {
  const normalized = normalizeRenderProvider(defaultProvider);
  if (!normalized) return [...RENDER_PROVIDER_ORDER];
  return [normalized, ...RENDER_PROVIDER_ORDER.filter((provider) => provider !== normalized)];
}

function normalizeRenderProvider(provider: string | null | undefined): RenderProviderKey | null {
  if (provider === 'ollama_gpt_oss') return 'ollama';
  if (provider === 'openrouter_gpt_oss' || provider === 'opencode_nemotron') return 'openrouter';
  return RENDER_PROVIDER_ORDER.includes(provider as RenderProviderKey) ? provider as RenderProviderKey : null;
}

function modelKey(provider: RenderProviderKey, modelId: string) {
  return `${provider}:${normalizeModelForProvider(provider, modelId)}`;
}

function renderProviderLabel(provider: RenderProviderKey) {
  return provider === 'router9' ? '9router' : providerLabels[provider] || provider;
}

export function buildProviderOptions(defaults: SettingsDefaults | null, includeMock = false): Option[] {
  const options: Option[] = [{ id: 'auto', label: providerLabels.auto }];
  if (!defaults) return includeMock ? [...options, { id: 'mock', label: providerLabels.mock }] : options;
  if (defaults.registry_providers?.length) {
    defaults.registry_providers
      .filter((provider) => provider.enabled && (provider.api_key_configured || (defaults.registry_models?.some((model) => model.provider_id === provider.id && model.enabled) ?? false) || provider.id === 'ollama'))
      .forEach((provider) => options.push({ id: provider.id, label: provider.label || providerLabels[provider.id] || provider.id }));
  } else {
    (['openrouter', 'nvidia', 'ollama', 'openai_compat', 'router9'] as const).forEach((provider) => {
      const item = defaults[provider];
      if (item.api_key_configured || item.scanned_models.length > 0 || item.allowed_model_ids.length > 0) {
        options.push({ id: provider, label: providerLabels[provider] });
      }
    });
  }
  if (includeMock) options.push({ id: 'mock', label: providerLabels.mock });
  return options;
}

export function buildOcrProviderOptions(defaults: SettingsDefaults | null): Option[] {
  const options: Option[] = [{ id: '', label: 'Theo mặc định hệ thống' }];
  const providers = ['local', 'openrouter', 'router9', 'nvidia', 'ollama', 'openai_compat'] as const;
  providers.forEach((provider) => {
    if (!defaults) {
      options.push({ id: provider, label: providerLabels[provider] || provider });
      return;
    }
    if (provider === 'local') {
      options.push({ id: provider, label: providerLabels[provider] || provider });
      return;
    }
    const item = defaults[provider];
    if (item.api_key_configured || item.scanned_models.length > 0 || item.allowed_model_ids.length > 0) {
      options.push({ id: provider, label: providerLabels[provider] || provider });
    }
  });
  return options;
}

export function buildRegistryModelOptions(defaults: SettingsDefaults | null, providerId: string, currentModel = '', extraModelIds: string[] = []): Option[] {
  const registryModels = defaults?.registry_models?.filter((model) => model.provider_id === providerId && model.enabled) ?? [];
  if (registryModels.length === 0) return [];
  const hasAllowlist = registryModels.some((model) => model.allowed);
  const visibleModels = hasAllowlist ? registryModels.filter((model) => model.allowed) : registryModels;
  const options = visibleModels.map((model) => ({ id: model.id, label: model.label || model.id }));
  return mergeOptions(options, [currentModel, ...extraModelIds]);
}

export function buildModelOptionsFromDefaults(providerDefaults: ProviderSettingsDefaults | undefined, currentModel = '', extraModelIds: string[] = [], defaults?: SettingsDefaults | null, providerId?: string): Option[] {
  if (defaults && providerId) {
    const registryOptions = buildRegistryModelOptions(defaults, providerId, currentModel, extraModelIds);
    if (registryOptions.length > 0) {
      return mergeOptions(registryOptions, [
        ...(providerDefaults?.allowed_model_ids ?? []),
        currentModel,
        ...extraModelIds,
      ]);
    }
  }
  if (!providerDefaults) return uniqueOptions([currentModel, ...extraModelIds]);
  const ids = providerDefaults.allowed_model_ids.length > 0
    ? providerDefaults.allowed_model_ids
    : providerDefaults.scanned_models.length > 0
      ? providerDefaults.scanned_models.map((model) => model.id)
      : [];
  const options = ids.map((id) => {
    const scanned = providerDefaults.scanned_models.find((model) => model.id === id);
    return { id, label: scanned?.label ?? id };
  });
  if (providerDefaults.allowed_model_ids.length === 0) {
    [currentModel, ...extraModelIds].filter(Boolean).forEach((id) => {
      if (!options.some((option) => option.id === id)) options.unshift({ id, label: id });
    });
  }
  return options;
}

function mergeOptions(base: Option[], extraIds: Array<string | null | undefined>) {
  const byId = new Map(base.map((option) => [option.id, option]));
  extraIds.filter(Boolean).forEach((value) => {
    const id = String(value);
    if (!byId.has(id)) byId.set(id, { id, label: id });
  });
  return [...byId.values()];
}

function uniqueOptions(ids: string[]) {
  const seen = new Set<string>();
  return ids.filter(Boolean).filter((id) => {
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  }).map((id) => ({ id, label: id }));
}

export function buildPlanOptions(settingsValue: Record<string, unknown> | undefined): Option[] {
  const plansValue = settingsValue?.plans && typeof settingsValue.plans === 'object' ? settingsValue.plans as Record<string, unknown> : {};
  const ids = Object.keys(plansValue);
  const normalized = ids.length > 0 ? ids : ['free', 'pro', 'pro_plus'];
  return normalized.map((id) => ({ id, label: planLabel(id) }));
}

export function planLabel(id: string) {
  return id === 'pro_plus' ? 'pro+' : id;
}

export function distinctOptions(values: Array<string | null | undefined>, base: Option[] = []): Option[] {
  const byId = new Map(base.map((option) => [option.id, option]));
  values.filter(Boolean).forEach((value) => {
    const id = String(value);
    if (!byId.has(id)) byId.set(id, { id, label: id });
  });
  return [...byId.values()];
}

const ROUTER9_MODEL_PREFIXES = [
  'router9/',
  'gh/',
  'cc/',
  'cx/',
  'oc/',
  'kr/',
  'cf/',
  'claude-ds/',
  'openAI-ds/',
  'kc/',
  'github/',
  'codex-',
] as const;

const OPENROUTER_MODEL_PREFIXES = ['openrouter/', 'openai/', 'google/', 'anthropic/', 'meta-llama/', 'mistralai/', 'qwen/'] as const;
const NVIDIA_MODEL_PREFIXES = ['nvidia/'] as const;
const OLLAMA_MODEL_PREFIXES = ['ollama/'] as const;
const OPENAI_COMPAT_MODEL_PREFIXES = ['openai_compat/', 'openai-compat/'] as const;
const EXPLICIT_PROVIDER_PREFIXES: Record<OcrProvider, readonly string[]> = {
  local: ['local/'],
  openrouter: ['openrouter/'],
  router9: ['router9/'],
  nvidia: NVIDIA_MODEL_PREFIXES,
  ollama: OLLAMA_MODEL_PREFIXES,
  openai_compat: OPENAI_COMPAT_MODEL_PREFIXES,
};

export function inferOcrProviderFromModelId(model: string): OcrProvider | null {
  const value = model.trim();
  if (!value) return null;
  if (ROUTER9_MODEL_PREFIXES.some((prefix) => value.startsWith(prefix))) return 'router9';
  if (value.startsWith(NVIDIA_MODEL_PREFIXES[0])) return 'nvidia';
  if (value.startsWith(OLLAMA_MODEL_PREFIXES[0])) return 'ollama';
  if (OPENAI_COMPAT_MODEL_PREFIXES.some((prefix) => value.startsWith(prefix))) return 'openai_compat';
  if (OPENROUTER_MODEL_PREFIXES.some((prefix) => value.startsWith(prefix))) return 'openrouter';
  return null;
}

export function explicitProviderFromModelId(model: string): OcrProvider | null {
  const value = model.trim();
  if (!value) return null;
  for (const [provider, prefixes] of Object.entries(EXPLICIT_PROVIDER_PREFIXES) as Array<[OcrProvider, readonly string[]]>) {
    if (prefixes.some((prefix) => value.startsWith(prefix))) return provider;
  }
  return null;
}

export function normalizeModelForProvider(provider: string, model: string): string {
  const value = model.trim();
  if (provider === 'local') return value.replace(/^local\//, '');
  if (provider === 'openrouter') return value.replace(/^openrouter\//, '');
  if (provider === 'router9') return value.replace(/^router9\//, '');
  if (provider === 'nvidia') return value.replace(/^nvidia\//, '');
  if (provider === 'ollama') return value.replace(/^ollama\//, '');
  if (provider === 'openai_compat') return value.replace(/^openai_compat\//, '').replace(/^openai-compat\//, '');
  return value;
}

export function normalizeProviderModelSelection(provider: string, model: string) {
  const selectedProvider = provider.trim();
  const selectedModel = model.trim();
  const explicitProvider = explicitProviderFromModelId(selectedModel);
  if (explicitProvider && selectedProvider && explicitProvider !== selectedProvider) {
    return { provider: explicitProvider, model: normalizeModelForProvider(explicitProvider, selectedModel), changed: true };
  }
  return { provider: selectedProvider, model: normalizeModelForProvider(selectedProvider, selectedModel), changed: false };
}
