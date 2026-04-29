import type { AdvancedRenderSettings, MathScene, RenderResponse, Renderer } from '../types/scene';
import type { ProviderKey, RuntimeSettings, ScannedModelInfo, SettingsDefaults } from '../types/settings';

export interface OcrResponse {
  text: string;
  provider: string;
  model: string;
  warnings: string[];
}

export async function getSettingsDefaults(): Promise<SettingsDefaults> {
  const response = await fetch('/api/settings/defaults');

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body.trim() || `Không thể đọc cấu hình backend. HTTP ${response.status}`);
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
  const response = await fetch('/api/render', {
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
    const body = await response.text();
    let message = body.trim();
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      if (typeof parsed.detail === 'string') {
        message = parsed.detail;
      } else if (Array.isArray(parsed.detail)) {
        message = parsed.detail.map((item) => item?.msg ?? JSON.stringify(item)).join('\n');
      }
    } catch {
      // Keep the raw response text.
    }
    throw new Error(message || `Không thể dựng hình từ đề bài. HTTP ${response.status}`);
  }

  return response.json();
}

export async function ocrImage(imageDataUrl: string, runtimeSettings: RuntimeSettings): Promise<OcrResponse> {
  const response = await fetch('/api/ocr', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_data_url: imageDataUrl,
      ocr_provider: runtimeSettings.ocr.provider,
      ocr_model: runtimeSettings.ocr.model.trim() || undefined,
      runtime_settings: compactRuntimeSettings(runtimeSettings),
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    let message = body.trim();
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      if (typeof parsed.detail === 'string') message = parsed.detail;
    } catch {
      // Keep the raw response text.
    }
    throw new Error(message || `Không thể OCR ảnh đề bài. HTTP ${response.status}`);
  }

  return response.json();
}

export async function scanProviderModels(provider: ProviderKey, runtimeSettings: RuntimeSettings): Promise<ScannedModelInfo[]> {
  const response = await fetch('/api/ai/models/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, runtime_settings: compactRuntimeSettings(runtimeSettings) }),
  });

  if (!response.ok) {
    const body = await response.text();
    let message = body.trim();
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      if (typeof parsed.detail === 'string') message = parsed.detail;
    } catch {
      // Keep the raw response text.
    }
    throw new Error(message || `Không thể quét model provider. HTTP ${response.status}`);
  }

  const payload = await response.json() as { models: ScannedModelInfo[] };
  return payload.models;
}

export async function scanRouter9Models(runtimeSettings: RuntimeSettings): Promise<ScannedModelInfo[]> {
  const response = await fetch('/api/ai/router9/models/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ runtime_settings: compactRuntimeSettings(runtimeSettings) }),
  });

  if (!response.ok) {
    const body = await response.text();
    let message = body.trim();
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      if (typeof parsed.detail === 'string') message = parsed.detail;
    } catch {
      // Keep the raw response text.
    }
    throw new Error(message || `Không thể quét model 9router. HTTP ${response.status}`);
  }

  const payload = await response.json() as { models: ScannedModelInfo[] };
  return payload.models;
}

export async function renderEditedScene(scene: MathScene, advancedSettings: AdvancedRenderSettings): Promise<RenderResponse> {
  const response = await fetch('/api/render/scene', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scene,
      advanced_settings: advancedSettings,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    let message = body.trim();
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      if (typeof parsed.detail === 'string') {
        message = parsed.detail;
      } else if (Array.isArray(parsed.detail)) {
        message = parsed.detail.map((item) => item?.msg ?? JSON.stringify(item)).join('\n');
      }
    } catch {
      // Keep the raw response text.
    }
    throw new Error(message || `Không thể dựng lại scene. HTTP ${response.status}`);
  }

  return response.json();
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
