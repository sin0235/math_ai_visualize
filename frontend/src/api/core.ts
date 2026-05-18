import type { RuntimeSettings } from '../types/settings';

export class ApiError extends Error {
  details: string[];

  constructor(message: string, details: string[] = []) {
    super(message);
    this.name = 'ApiError';
    this.details = details;
  }
}

export const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

export function apiUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}

export function normalizeApiBaseUrl(value: string | undefined) {
  const baseUrl = value?.trim().replace(/\/$/, '') ?? '';
  if (!baseUrl) return '';
  if (baseUrl.startsWith('http://') || baseUrl.startsWith('https://')) return baseUrl;
  if (baseUrl.startsWith('/')) return baseUrl;
  return `https://${baseUrl}`;
}

export function queryString(filters: object) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    const text = typeof value === 'string' ? value.trim() : '';
    if (text) params.set(key, text);
  }
  const serialized = params.toString();
  return serialized ? `?${serialized}` : '';
}

export async function requestJson<T>(path: string, init: RequestInit | undefined, fallbackMessage: string): Promise<T> {
  try {
    const response = await fetchWithRetry(apiUrl(path), init);
    if (!response.ok) throw await parseApiError(response, `${fallbackMessage} HTTP ${response.status}`);
    const body = await response.text();
    if (!body.trim()) throw new ApiError(fallbackMessage);
    if (looksLikeHtml(body)) throw gatewayHtmlApiError(response.status, fallbackMessage);
    try {
      return JSON.parse(body) as T;
    } catch {
      throw new ApiError(fallbackMessage);
    }
  } catch (caught) {
    if (caught instanceof ApiError) throw caught;
    throw networkApiError(caught, fallbackMessage);
  }
}

export async function requestVoid(path: string, init: RequestInit | undefined, fallbackMessage: string): Promise<void> {
  try {
    const response = await fetchWithRetry(apiUrl(path), init);
    if (!response.ok) throw await parseApiError(response, `${fallbackMessage} HTTP ${response.status}`);
  } catch (caught) {
    if (caught instanceof ApiError) throw caught;
    throw networkApiError(caught, fallbackMessage);
  }
}

export async function fetchWithRetry(input: RequestInfo | URL, init?: RequestInit) {
  try {
    return await fetch(input, init);
  } catch (caught) {
    if (init?.signal?.aborted || !isTransientNetworkError(caught)) throw caught;
    await new Promise((resolve) => window.setTimeout(resolve, 350));
    return fetch(input, init);
  }
}

export function timeoutSignal(ms: number) {
  const controller = new AbortController();
  window.setTimeout(() => controller.abort(), ms);
  return controller.signal;
}

function isTransientNetworkError(caught: unknown) {
  return caught instanceof TypeError;
}

export function networkApiError(caught: unknown, fallbackMessage: string) {
  if (caught instanceof DOMException && caught.name === 'AbortError') return new ApiError('Hệ thống đang quá tải do lượng người dùng tăng cao. Vui lòng thử lại sau ít phút.');
  if (caught instanceof TypeError) return new ApiError('Hệ thống đang quá tải do lượng người dùng tăng cao. Vui lòng thử lại sau ít phút.');
  if (caught instanceof Error) return new ApiError(caught.message || fallbackMessage);
  return new ApiError(fallbackMessage);
}

export async function parseApiError(response: Response, fallbackMessage: string): Promise<ApiError> {
  const body = await response.text();
  if (!body.trim()) return new ApiError(fallbackMessage);
  if (looksLikeHtml(body) || response.headers.get('content-type')?.toLowerCase().includes('text/html')) {
    return gatewayHtmlApiError(response.status, fallbackMessage);
  }

  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    const parsedDetail = parseDetail(parsed.detail);
    if (parsedDetail) return parsedDetail;
  } catch {
    // Keep raw text fallback.
  }

  return new ApiError(body.trim() || fallbackMessage);
}

function looksLikeHtml(body: string) {
  return /^\s*<!doctype\s+html/i.test(body) || /^\s*<html[\s>]/i.test(body);
}

function gatewayHtmlApiError(statusCode: number, fallbackMessage: string) {
  if (statusCode === 504 || statusCode === 408 || statusCode === 0) {
    return new ApiError('Hệ thống đang quá tải do provider phản hồi quá lâu. Vui lòng thử lại sau ít phút.', [
      'Thử model nhẹ hơn hoặc tắt reasoning layer nếu đang bật.',
      'Nếu lỗi lặp lại, quản trị viên cần tăng timeout proxy hoặc giảm chuỗi fallback model.',
    ]);
  }
  if (statusCode === 502 || statusCode === 503) {
    return new ApiError('Backend hoặc provider tạm thời không sẵn sàng. Vui lòng thử lại sau ít phút.');
  }
  return new ApiError(fallbackMessage);
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
    const data = detail as { code?: unknown; message?: unknown; hint?: unknown; attempts?: unknown; suggestions?: unknown; debug_message?: unknown };
    const code = typeof data.code === 'string' ? `[${data.code}] ` : '';
    const message = typeof data.message === 'string' ? `${code}${data.message}` : JSON.stringify(detail);
    const details = [data.hint, data.suggestions, data.attempts, data.debug_message].flatMap((value) => {
      if (Array.isArray(value)) return value.map(String);
      if (typeof value === 'string') return [value];
      return [];
    });
    return new ApiError(message, details);
  }
  return null;
}

export function compactRuntimeSettings(settings?: RuntimeSettings) {
  if (!settings) return undefined;

  const compact = {
    default_provider: undefined,
    openrouter: compactProviderConnectionSettings(settings.openrouter),
    nvidia: compactProviderConnectionSettings(settings.nvidia),
    ollama: compactProviderConnectionSettings(settings.ollama),
    openai_compat: compactProviderConnectionSettings(settings.openai_compat),
    router9: compactRouter9ConnectionSettings(settings),
    openrouter_http_referer: cleanText(settings.openrouter_http_referer),
    openrouter_x_title: cleanText(settings.openrouter_x_title),
    openrouter_reasoning_enabled: settings.openrouter_reasoning_enabled ? true : undefined,
  };

  if (
    compact.default_provider === undefined &&
    compact.openrouter === undefined &&
    compact.nvidia === undefined &&
    compact.ollama === undefined &&
    compact.openai_compat === undefined &&
    compact.router9 === undefined &&
    compact.openrouter_http_referer === undefined &&
    compact.openrouter_x_title === undefined &&
    compact.openrouter_reasoning_enabled === undefined
  ) {
    return undefined;
  }

  return compact;
}

function compactProviderConnectionSettings(settings: RuntimeSettings['openrouter']) {
  const compact = {
    api_key: cleanText(settings.api_key),
    base_url: cleanText(settings.base_url),
  };

  if (compact.api_key === undefined && compact.base_url === undefined) {
    return undefined;
  }

  return compact;
}

function compactRouter9ConnectionSettings(settings: RuntimeSettings) {
  const compact = {
    api_key: cleanText(settings.router9.api_key),
    base_url: cleanText(settings.router9.base_url),
    only_mode: settings.router9.only_mode ? true : undefined,
    allowed_model_ids: settings.router9.allowed_model_ids.length > 0 ? settings.router9.allowed_model_ids : undefined,
  };

  if (
    compact.api_key === undefined &&
    compact.base_url === undefined &&
    compact.only_mode === undefined &&
    compact.allowed_model_ids === undefined
  ) {
    return undefined;
  }

  return compact;
}

export function cleanText(value: string) {
  const text = value.trim();
  return text || undefined;
}
