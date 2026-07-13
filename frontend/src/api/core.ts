import type { RuntimeSettings } from '../types/settings';

export interface ApiErrorMetadata {
  code?: string;
  correlationId?: string;
  stage?: string;
  retryable?: boolean;
  retryAfterSeconds?: number;
}

export class ApiError extends Error {
  details: string[];
  code?: string;
  correlationId?: string;
  stage?: string;
  retryable?: boolean;
  retryAfterSeconds?: number;

  constructor(message: string, details: string[] = [], metadata: ApiErrorMetadata = {}) {
    super(message);
    this.name = 'ApiError';
    this.details = details;
    this.code = metadata.code;
    this.correlationId = metadata.correlationId;
    this.stage = metadata.stage;
    this.retryable = metadata.retryable;
    this.retryAfterSeconds = metadata.retryAfterSeconds;
  }
}

export const API_BASE_URL = normalizeApiBaseUrl(import.meta.env?.VITE_API_BASE_URL);

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
  if (caught instanceof DOMException && caught.name === 'AbortError') return new ApiError(`${fallbackMessage} Yêu cầu quá thời gian chờ.`);
  if (caught instanceof TypeError) return new ApiError(`${fallbackMessage} Không thể kết nối tới backend.`);
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
    const parsedDetail = parseDetail(parsed.detail, retryAfterSeconds(response.headers.get('Retry-After')));
    if (parsedDetail) return parsedDetail;
  } catch {
    // Keep raw text fallback.
  }

  return new ApiError(body.trim() || fallbackMessage);
}

function retryAfterSeconds(value: string | null): number | undefined {
  if (!value) return undefined;
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds > 0) return Math.ceil(seconds);
  const retryAt = Date.parse(value);
  if (Number.isNaN(retryAt)) return undefined;
  return Math.max(1, Math.ceil((retryAt - Date.now()) / 1000));
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

function parseDetail(detail: unknown, retryAfter?: number): ApiError | null {
  if (typeof detail === 'string') return new ApiError(detail);
  if (Array.isArray(detail)) {
    return new ApiError(detail.map((item) => {
      if (item && typeof item === 'object' && 'msg' in item) return String(item.msg);
      return JSON.stringify(item);
    }).join('\n'));
  }
  if (detail && typeof detail === 'object') {
    const data = detail as {
      code?: unknown;
      message?: unknown;
      hint?: unknown;
      attempts?: unknown;
      suggestions?: unknown;
      debug_message?: unknown;
      correlation_id?: unknown;
      stage?: unknown;
      retryable?: unknown;
    };
    const codeValue = typeof data.code === 'string' ? data.code : undefined;
    const message = typeof data.message === 'string' ? data.message : JSON.stringify(detail);
    const detailValues = [data.hint, data.suggestions, data.attempts];
    if (!codeValue?.startsWith('ANALYZER_')) detailValues.push(data.debug_message);
    const details = detailValues.flatMap((value) => {
      if (Array.isArray(value)) return value.map(String);
      if (typeof value === 'string') return [value];
      return [];
    });
    return new ApiError(message, details, {
      code: codeValue,
      correlationId: typeof data.correlation_id === 'string' ? data.correlation_id : undefined,
      stage: typeof data.stage === 'string' ? data.stage : undefined,
      retryable: typeof data.retryable === 'boolean' ? data.retryable : undefined,
      retryAfterSeconds: retryAfter,
    });
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
    model: cleanText(settings.model),
  };

  if (compact.model === undefined) {
    return undefined;
  }

  return compact;
}

function compactRouter9ConnectionSettings(settings: RuntimeSettings) {
  const compact = {
    model: cleanText(settings.router9.model),
    only_mode: settings.router9.only_mode ? true : undefined,
    allowed_model_ids: settings.router9.allowed_model_ids.length > 0 ? settings.router9.allowed_model_ids : undefined,
  };

  if (
    compact.model === undefined &&
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
