export type ProviderKey = 'openrouter' | 'nvidia' | 'ollama';
export type OcrProvider = 'openrouter' | 'router9';

export interface ScannedModelInfo {
  id: string;
  label: string;
  provider: string;
  owned_by?: string | null;
  created?: number | null;
  context_length?: number | null;
}

export interface ProviderConnectionSettings {
  api_key: string;
  base_url: string;
  model: string;
  scanned_models: ScannedModelInfo[];
  last_scanned_at: string;
}

export interface Router9Settings extends ProviderConnectionSettings {
  only_mode: boolean;
  scanned_models: ScannedModelInfo[];
  allowed_model_ids: string[];
  last_scanned_at: string;
}

export interface OcrSettings {
  provider: OcrProvider;
  model: string;
  max_image_mb: number;
}

export interface RuntimeSettings {
  default_provider: string;
  openrouter: ProviderConnectionSettings;
  nvidia: ProviderConnectionSettings;
  ollama: ProviderConnectionSettings;
  router9: Router9Settings;
  ocr: OcrSettings;
  openrouter_http_referer: string;
  openrouter_x_title: string;
  openrouter_reasoning_enabled: boolean;
}

export interface ProviderSettingsDefaults {
  api_key_configured: boolean;
  base_url: string;
  model?: string | null;
  scanned_models: ScannedModelInfo[];
  allowed_model_ids: string[];
}

export interface OpenRouterSettingsDefaults extends ProviderSettingsDefaults {
  vision_model: string;
  http_referer?: string | null;
  x_title: string;
  reasoning_enabled: boolean;
}

export interface Router9SettingsDefaults extends ProviderSettingsDefaults {
  only_mode: boolean;
  allowed_model_ids: string[];
}

export interface AdminProviderModelSettings {
  base_url: string;
  model: string;
  scanned_models: ScannedModelInfo[];
  allowed_model_ids: string[];
  last_scanned_at: string;
  only_mode: boolean;
}

export interface AdminRouter9ModelSettings extends AdminProviderModelSettings {
  only_mode: boolean;
  allowed_model_ids: string[];
}

export interface AdminOcrModelSettings {
  provider: OcrProvider;
  model: string;
  max_image_mb: number;
}

export interface SettingsDefaults {
  app_name: string;
  default_provider: string;
  openrouter: OpenRouterSettingsDefaults;
  nvidia: ProviderSettingsDefaults;
  ollama: ProviderSettingsDefaults;
  router9: Router9SettingsDefaults;
}

export const SETTINGS_STORAGE_VERSION = 4;

export const defaultRuntimeSettings: RuntimeSettings = {
  default_provider: 'auto',
  openrouter: {
    api_key: '',
    base_url: '',
    model: '',
    scanned_models: [],
    last_scanned_at: '',
  },
  nvidia: {
    api_key: '',
    base_url: '',
    model: '',
    scanned_models: [],
    last_scanned_at: '',
  },
  ollama: {
    api_key: '',
    base_url: '',
    model: '',
    scanned_models: [],
    last_scanned_at: '',
  },
  router9: {
    api_key: '',
    base_url: '',
    model: '',
    only_mode: false,
    scanned_models: [],
    allowed_model_ids: [],
    last_scanned_at: '',
  },
  ocr: {
    provider: 'openrouter',
    model: '',
    max_image_mb: 8,
  },
  openrouter_http_referer: '',
  openrouter_x_title: '',
  openrouter_reasoning_enabled: false,
};
