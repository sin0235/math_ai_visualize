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
  ollama: 'Ollama / OpenAI-compatible',
  router9: '9router',
  mock: 'Mock extractor',
};

export function buildProviderOptions(defaults: SettingsDefaults | null, includeMock = false): Option[] {
  const options: Option[] = [{ id: 'auto', label: providerLabels.auto }];
  if (!defaults) return includeMock ? [...options, { id: 'mock', label: providerLabels.mock }] : options;
  (['openrouter', 'nvidia', 'ollama', 'router9'] as const).forEach((provider) => {
    const item = defaults[provider];
    if (item.api_key_configured || item.model || item.scanned_models.length > 0 || item.allowed_model_ids.length > 0) {
      options.push({ id: provider, label: providerLabels[provider] });
    }
  });
  if (includeMock) options.push({ id: 'mock', label: providerLabels.mock });
  return options;
}

export function buildOcrProviderOptions(defaults: SettingsDefaults | null): Option[] {
  const options: Option[] = [];
  if (!defaults || defaults.openrouter.api_key_configured || defaults.openrouter.vision_model || defaults.openrouter.scanned_models.length > 0) {
    options.push({ id: 'openrouter', label: 'OpenRouter vision' });
  }
  if (!defaults || defaults.router9.api_key_configured || defaults.router9.model || defaults.router9.scanned_models.length > 0) {
    options.push({ id: 'router9', label: '9router vision' });
  }
  return options;
}

export function buildModelOptionsFromDefaults(providerDefaults: ProviderSettingsDefaults | undefined, currentModel = '', extraModelIds: string[] = []): Option[] {
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
  [currentModel, ...extraModelIds].filter(Boolean).forEach((id) => {
    if (!options.some((option) => option.id === id)) options.unshift({ id, label: id });
  });
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
  const normalized = ids.length > 0 ? ids : ['free', 'pro'];
  return normalized.map((id) => ({ id, label: id }));
}

export function distinctOptions(values: Array<string | null | undefined>, base: Option[] = []): Option[] {
  const byId = new Map(base.map((option) => [option.id, option]));
  values.filter(Boolean).forEach((value) => {
    const id = String(value);
    if (!byId.has(id)) byId.set(id, { id, label: id });
  });
  return [...byId.values()];
}
