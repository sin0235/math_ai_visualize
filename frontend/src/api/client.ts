import type { AdvancedRenderSettings, MathScene, RenderResponse, Renderer } from '../types/scene';
import type { ProviderKey, RuntimeSettings, ScannedModelInfo, SettingsDefaults } from '../types/settings';

export interface OcrResponse {
  text: string;
  provider: string;
  model: string;
  warnings: string[];
}

export class ApiError extends Error {
  details: string[];

  constructor(message: string, details: string[] = []) {
    super(message);
    this.name = 'ApiError';
    this.details = details;
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? '';

function apiUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}

export async function getSettingsDefaults(): Promise<SettingsDefaults> {
  const response = await fetch(apiUrl('/api/settings/defaults'));

  if (!response.ok) {
    throw await parseApiError(response, `Không thể đọc cấu hình backend. HTTP ${response.status}`);
  }

  return response.json();
}

export async function renderProblem(
  problemText: string,
  preferredAiProvider?: string,
  preferredAiModel?: string,
  advancedSettings?: AdvancedRenderSettings,
  preferredRenderer?: Renderer,
  runtimeSettings?: RuntimeSettings,
): Promise<RenderResponse> {
  const response = await fetch(apiUrl('/api/render'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      problem_text: problemText,
      preferred_ai_provider: preferredAiProvider,
      preferred_ai_model: preferredAiModel,
      preferred_renderer: preferredRenderer,
      advanced_settings: advancedSettings,
      runtime_settings: compactRuntimeSettings(runtimeSettings),
    }),
  });

  if (!response.ok) {
    throw await parseApiError(response, `Không thể dựng hình từ đề bài. HTTP ${response.status}`);
  }

  return response.json();
}

export async function ocrImage(imageDataUrl: string, runtimeSettings: RuntimeSettings): Promise<OcrResponse> {
  const response = await fetch(apiUrl('/api/ocr'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_data_url: imageDataUrl,
      ocr_provider: runtimeSettings.router9.only_mode ? 'router9' : runtimeSettings.ocr.provider,
      ocr_model: runtimeSettings.ocr.model.trim() || undefined,
      runtime_settings: compactRuntimeSettings(runtimeSettings),
    }),
  });

  if (!response.ok) {
    throw await parseApiError(response, `Không thể OCR ảnh đề bài. HTTP ${response.status}`);
  }

  return response.json();
}

export async function scanProviderModels(provider: ProviderKey, runtimeSettings: RuntimeSettings): Promise<ScannedModelInfo[]> {
  const response = await fetch(apiUrl('/api/ai/models/scan'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, runtime_settings: compactRuntimeSettings(runtimeSettings) }),
  });

  if (!response.ok) {
    throw await parseApiError(response, `Không thể quét model provider. HTTP ${response.status}`);
  }

  const payload = await response.json() as { models: ScannedModelInfo[] };
  return payload.models;
}

export async function scanRouter9Models(runtimeSettings: RuntimeSettings): Promise<ScannedModelInfo[]> {
  const response = await fetch(apiUrl('/api/ai/router9/models/scan'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ runtime_settings: compactRuntimeSettings(runtimeSettings) }),
  });

  if (!response.ok) {
    throw await parseApiError(response, `Không thể quét model 9router. HTTP ${response.status}`);
  }

  const payload = await response.json() as { models: ScannedModelInfo[] };
  return payload.models;
}

export async function renderEditedScene(scene: MathScene, advancedSettings: AdvancedRenderSettings): Promise<RenderResponse> {
  const response = await fetch(apiUrl('/api/render/scene'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scene,
      advanced_settings: advancedSettings,
    }),
  });

  if (!response.ok) {
    throw await parseApiError(response, `Không thể dựng lại scene. HTTP ${response.status}`);
  }

  return response.json();
}

async function parseApiError(response: Response, fallbackMessage: string): Promise<ApiError> {
  const body = await response.text();
  if (!body.trim()) return new ApiError(fallbackMessage);

  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    const parsedDetail = parseDetail(parsed.detail);
    if (parsedDetail) return parsedDetail;
  } catch {
    // Keep raw text fallback.
  }

  return new ApiError(body.trim() || fallbackMessage);
}

function parseDetail(detail: unknown): ApiError | null {
  if (typeof detail === 'string') return new ApiError(detail);
  if (Array.isArray(detail)) {
    return new ApiError(detail.map((item) => {
      if (item && typeof item === 'object' && 'msg' in item) return String(item.msg);
      return JSON.stringify(item);
    }).join('\n'));
  }
  if (detail && typeof detail === 'object') {
    const data = detail as { message?: unknown; attempts?: unknown; suggestions?: unknown };
    const message = typeof data.message === 'string' ? data.message : JSON.stringify(detail);
    const details = [data.attempts, data.suggestions].flatMap((value) => {
      if (Array.isArray(value)) return value.map(String);
      if (typeof value === 'string') return [value];
      return [];
    });
    return new ApiError(message, details);
  }
  return null;
}

function compactRuntimeSettings(settings?: RuntimeSettings) {
  if (!settings) return undefined;

  const compact = {
    default_provider: cleanText(settings.default_provider) && settings.default_provider !== 'auto' ? settings.default_provider : undefined,
    openrouter: compactProviderSettings(settings.openrouter),
    nvidia: compactProviderSettings(settings.nvidia),
    ollama: compactProviderSettings(settings.ollama),
    router9: compactRouter9Settings(settings),
    openrouter_http_referer: cleanText(settings.openrouter_http_referer),
    openrouter_x_title: cleanText(settings.openrouter_x_title),
    openrouter_reasoning_enabled: settings.openrouter_reasoning_enabled ? true : undefined,
  };

  if (
    compact.default_provider === undefined &&
    compact.openrouter === undefined &&
    compact.nvidia === undefined &&
    compact.ollama === undefined &&
    compact.router9 === undefined &&
    compact.openrouter_http_referer === undefined &&
    compact.openrouter_x_title === undefined &&
    compact.openrouter_reasoning_enabled === undefined
  ) {
    return undefined;
  }

  return compact;
}

function compactProviderSettings(settings: RuntimeSettings['openrouter']) {
  const compact = {
    api_key: cleanText(settings.api_key),
    base_url: cleanText(settings.base_url),
    model: cleanText(settings.model),
  };

  if (compact.api_key === undefined && compact.base_url === undefined && compact.model === undefined) {
    return undefined;
  }

  return compact;
}

function compactRouter9Settings(settings: RuntimeSettings) {
  const compact = {
    api_key: cleanText(settings.router9.api_key),
    base_url: cleanText(settings.router9.base_url),
    model: cleanText(settings.router9.model),
    only_mode: settings.router9.only_mode ? true : undefined,
    allowed_model_ids: settings.router9.allowed_model_ids.length > 0 ? settings.router9.allowed_model_ids : undefined,
  };

  if (
    compact.api_key === undefined &&
    compact.base_url === undefined &&
    compact.model === undefined &&
    compact.only_mode === undefined &&
    compact.allowed_model_ids === undefined
  ) {
    return undefined;
  }

  return compact;
}

function cleanText(value: string) {
  const text = value.trim();
  return text || undefined;
}
