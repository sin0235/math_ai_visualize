import type { ProviderSettingsDefaults, SettingsDefaults } from '../types/settings';

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
  mock: 'Mock extractor',
};

export function buildProviderOptions(defaults: SettingsDefaults | null, includeMock = false): Option[] {
  const options: Option[] = [{ id: 'auto', label: providerLabels.auto }];
  if (!defaults) return includeMock ? [...options, { id: 'mock', label: providerLabels.mock }] : options;
  if (defaults.registry_providers?.length) {
    defaults.registry_providers
      .filter((provider) => provider.enabled && (provider.api_key_configured || provider.default_model_id || provider.id === 'ollama'))
      .forEach((provider) => options.push({ id: provider.id, label: provider.label || providerLabels[provider.id] || provider.id }));
  } else {
    (['openrouter', 'nvidia', 'ollama', 'openai_compat', 'router9'] as const).forEach((provider) => {
      const item = defaults[provider];
      if (item.api_key_configured || item.model || item.scanned_models.length > 0 || item.allowed_model_ids.length > 0) {
        options.push({ id: provider, label: providerLabels[provider] });
      }
    });
  }
  if (includeMock) options.push({ id: 'mock', label: providerLabels.mock });
  return options;
}

export function buildOcrProviderOptions(defaults: SettingsDefaults | null): Option[] {
  const options: Option[] = [];
  const providers = ['openrouter', 'router9', 'nvidia', 'ollama', 'openai_compat'] as const;
  providers.forEach((provider) => {
    if (!defaults) {
      options.push({ id: provider, label: providerLabels[provider] || provider });
      return;
    }
    const item = defaults[provider];
    if (item.api_key_configured || item.model || item.scanned_models.length > 0 || item.allowed_model_ids.length > 0) {
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
  if (!hasAllowlist) {
    [currentModel, ...extraModelIds].filter(Boolean).forEach((id) => {
      if (!options.some((option) => option.id === id)) options.unshift({ id, label: id });
    });
  }
  return options;
}

export function buildModelOptionsFromDefaults(providerDefaults: ProviderSettingsDefaults | undefined, currentModel = '', extraModelIds: string[] = [], defaults?: SettingsDefaults | null, providerId?: string): Option[] {
  if (defaults && providerId) {
    const registryOptions = buildRegistryModelOptions(defaults, providerId, currentModel, extraModelIds);
    if (registryOptions.length > 0) return registryOptions;
  }
  if (!providerDefaults) return uniqueOptions([currentModel, ...extraModelIds]);
  const ids = providerDefaults.allowed_model_ids.length > 0
    ? providerDefaults.allowed_model_ids
    : providerDefaults.scanned_models.length > 0
      ? providerDefaults.scanned_models.map((model) => model.id)
      : [providerDefaults.model ?? ''].filter(Boolean);
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
