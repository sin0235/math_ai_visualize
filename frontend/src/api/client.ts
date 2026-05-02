import type { AdvancedRenderSettings, MathScene, RenderResponse, Renderer } from '../types/scene';
import type { ProviderKey, RuntimeSettings, ScannedModelInfo, SettingsDefaults } from '../types/settings';

export interface OcrResponse {
  text: string;
  provider: string;
  model: string;
  warnings: string[];
}

export interface HealthResponse {
  status: string;
  app: string;
}

export interface UserResponse {
  id: string;
  email: string;
  created_at: string;
  role: 'user' | 'admin';
  status: 'active' | 'disabled';
  display_name?: string | null;
  last_login_at?: string | null;
  plan: string;
  email_verified_at?: string | null;
  password_changed_at?: string | null;
}

export interface AuthResponse {
  user: UserResponse;
}

export interface MessageResponse {
  message: string;
}

export interface SessionResponse {
  id: string;
  created_at: string;
  expires_at: string;
  last_seen_at?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
  current: boolean;
}

export interface RenderHistoryItem {
  id: string;
  problem_text: string;
  provider?: string | null;
  model?: string | null;
  created_at: string;
  source_type: string;
  renderer?: string | null;
}

export interface RenderHistoryDetail extends RenderHistoryItem {
  scene: MathScene;
  payload: RenderResponse['payload'];
  warnings: string[];
  render_request?: Record<string, unknown> | null;
  advanced_settings?: Record<string, unknown> | null;
  runtime_settings?: Record<string, unknown> | null;
}

export interface UserSettingsResponse {
  settings?: RuntimeSettings | null;
  updated_at?: string | null;
}

export interface AdminSummaryResponse {
  users: number;
  active_users: number;
  admins: number;
  render_jobs: number;
}

export interface AdminRenderHistoryItem extends RenderHistoryItem {
  user_id?: string | null;
}

export interface AuditLogResponse {
  id: string;
  actor_user_id?: string | null;
  action: string;
  target_type: string;
  target_id?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface SystemSettingResponse {
  key: string;
  value: Record<string, unknown>;
  updated_by?: string | null;
  updated_at: string;
}

export class ApiError extends Error {
  details: string[];

  constructor(message: string, details: string[] = []) {
    super(message);
    this.name = 'ApiError';
    this.details = details;
  }
}

const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL);

function apiUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}

function normalizeApiBaseUrl(value: string | undefined) {
  const baseUrl = value?.trim().replace(/\/$/, '') ?? '';
  if (!baseUrl) return '';
  if (baseUrl.startsWith('http://') || baseUrl.startsWith('https://')) return baseUrl;
  if (baseUrl.startsWith('/')) return baseUrl;
  return `https://${baseUrl}`;
}

export async function getHealth(): Promise<HealthResponse> {
  return requestJson('/api/health', undefined, 'Không thể kiểm tra trạng thái backend.');
}

export async function getSettingsDefaults(): Promise<SettingsDefaults> {
  return requestJson('/api/settings/defaults', undefined, 'Không thể đọc cấu hình backend.');
}

export async function getCurrentUser(): Promise<AuthResponse> {
  return requestJson('/api/auth/me', { credentials: 'include' }, 'Không thể đọc phiên đăng nhập.');
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  return requestJson('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password }),
  }, 'Không thể đăng nhập.');
}

export async function register(email: string, password: string, displayName?: string): Promise<AuthResponse> {
  return requestJson('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password, display_name: displayName ? cleanText(displayName) : undefined }),
  }, 'Không thể tạo tài khoản.');
}

export async function forgotPassword(email: string): Promise<MessageResponse> {
  return requestJson('/api/auth/forgot-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email }),
  }, 'Không thể gửi yêu cầu đặt lại mật khẩu.');
}

export async function resetPassword(token: string, password: string): Promise<MessageResponse> {
  return requestJson('/api/auth/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ token, password }),
  }, 'Không thể đặt lại mật khẩu.');
}

export async function verifyEmail(token: string): Promise<AuthResponse> {
  return requestJson('/api/auth/verify-email', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ token }),
  }, 'Không thể xác minh email.');
}

export async function resendVerification(): Promise<MessageResponse> {
  return requestJson('/api/auth/resend-verification', { method: 'POST', credentials: 'include' }, 'Không thể gửi lại email xác minh.');
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<MessageResponse> {
  return requestJson('/api/auth/change-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  }, 'Không thể đổi mật khẩu.');
}

export async function updateProfile(displayName: string): Promise<AuthResponse> {
  return requestJson('/api/auth/profile', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ display_name: displayName }),
  }, 'Không thể cập nhật hồ sơ.');
}

export async function getSessions(): Promise<SessionResponse[]> {
  return requestJson('/api/auth/sessions', { credentials: 'include' }, 'Không thể tải phiên đăng nhập.');
}

export async function revokeSession(id: string): Promise<MessageResponse> {
  return requestJson(`/api/auth/sessions/${encodeURIComponent(id)}`, { method: 'DELETE', credentials: 'include' }, 'Không thể thu hồi phiên đăng nhập.');
}

export async function revokeOtherSessions(): Promise<MessageResponse> {
  return requestJson('/api/auth/sessions/revoke-others', { method: 'POST', credentials: 'include' }, 'Không thể thu hồi các phiên khác.');
}

export async function logout(): Promise<void> {
  await requestVoid('/api/auth/logout', { method: 'POST', credentials: 'include' }, 'Không thể đăng xuất.');
}

export async function getUserSettings(): Promise<UserSettingsResponse> {
  return requestJson('/api/user/settings', { credentials: 'include' }, 'Không thể tải cấu hình cá nhân.');
}

export async function saveUserSettings(settings: RuntimeSettings): Promise<UserSettingsResponse> {
  return requestJson('/api/user/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ settings: compactStoredSettings(settings) }),
  }, 'Không thể lưu cấu hình cá nhân.');
}

export async function getRenderHistory(): Promise<RenderHistoryItem[]> {
  return requestJson('/api/history', { credentials: 'include' }, 'Không thể tải lịch sử dựng hình.');
}

export async function getRenderHistoryDetail(id: string): Promise<RenderHistoryDetail> {
  return requestJson(`/api/history/${encodeURIComponent(id)}`, { credentials: 'include' }, 'Không thể tải chi tiết lịch sử.');
}

export async function deleteRenderHistory(id: string): Promise<void> {
  await requestVoid(`/api/history/${encodeURIComponent(id)}`, { method: 'DELETE', credentials: 'include' }, 'Không thể xoá lịch sử.');
}

export async function getAdminSummary(): Promise<AdminSummaryResponse> {
  return requestJson('/api/admin/summary', { credentials: 'include' }, 'Không thể tải dashboard quản trị.');
}

export async function getAdminUsers(query = ''): Promise<UserResponse[]> {
  const suffix = query.trim() ? `?q=${encodeURIComponent(query.trim())}` : '';
  return requestJson(`/api/admin/users${suffix}`, { credentials: 'include' }, 'Không thể tải danh sách người dùng.');
}

export async function updateAdminUser(id: string, patch: Partial<Pick<UserResponse, 'role' | 'status' | 'display_name' | 'plan'>>): Promise<UserResponse> {
  return requestJson(`/api/admin/users/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(patch),
  }, 'Không thể cập nhật người dùng.');
}

export async function getAdminRenderJobs(): Promise<AdminRenderHistoryItem[]> {
  return requestJson('/api/admin/render-jobs', { credentials: 'include' }, 'Không thể tải lịch sử render hệ thống.');
}

export async function deleteAdminRenderJob(id: string): Promise<void> {
  await requestVoid(`/api/admin/render-jobs/${encodeURIComponent(id)}`, { method: 'DELETE', credentials: 'include' }, 'Không thể xoá render job.');
}

export async function getAdminSystemSettings(): Promise<SystemSettingResponse[]> {
  return requestJson('/api/admin/system-settings', { credentials: 'include' }, 'Không thể tải cấu hình hệ thống.');
}

export async function saveAdminSystemSetting(key: string, value: Record<string, unknown>): Promise<SystemSettingResponse> {
  return requestJson('/api/admin/system-settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ key, value }),
  }, 'Không thể lưu cấu hình hệ thống.');
}

export async function getAdminAuditLogs(): Promise<AuditLogResponse[]> {
  return requestJson('/api/admin/audit-logs', { credentials: 'include' }, 'Không thể tải audit logs.');
}

export async function renderProblem(
  problemText: string,
  preferredAiProvider?: string,
  preferredAiModel?: string,
  advancedSettings?: AdvancedRenderSettings,
  preferredRenderer?: Renderer,
  runtimeSettings?: RuntimeSettings,
): Promise<RenderResponse> {
  return requestJson('/api/render', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      problem_text: problemText,
      preferred_ai_provider: preferredAiProvider,
      preferred_ai_model: preferredAiModel,
      preferred_renderer: preferredRenderer,
      advanced_settings: advancedSettings,
      runtime_settings: compactRuntimeSettings(runtimeSettings),
    }),
  }, 'Không thể dựng hình từ đề bài.');
}

export async function ocrImage(imageDataUrl: string, runtimeSettings: RuntimeSettings): Promise<OcrResponse> {
  return requestJson('/api/ocr', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_data_url: imageDataUrl,
      ocr_provider: runtimeSettings.router9.only_mode ? 'router9' : runtimeSettings.ocr.provider,
      ocr_model: runtimeSettings.ocr.model.trim() || undefined,
      runtime_settings: compactRuntimeSettings(runtimeSettings),
    }),
  }, 'Không thể OCR ảnh đề bài.');
}

export async function scanProviderModels(provider: ProviderKey, runtimeSettings: RuntimeSettings): Promise<ScannedModelInfo[]> {
  const payload = await requestJson<{ models: ScannedModelInfo[] }>('/api/ai/models/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, runtime_settings: compactRuntimeSettings(runtimeSettings) }),
  }, 'Không thể quét model provider.');
  return payload.models;
}

export async function scanRouter9Models(runtimeSettings: RuntimeSettings): Promise<ScannedModelInfo[]> {
  const payload = await requestJson<{ models: ScannedModelInfo[] }>('/api/ai/router9/models/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ runtime_settings: compactRuntimeSettings(runtimeSettings) }),
  }, 'Không thể quét model 9router.');
  return payload.models;
}

export async function renderEditedScene(scene: MathScene, advancedSettings: AdvancedRenderSettings): Promise<RenderResponse> {
  return requestJson('/api/render/scene', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      scene,
      advanced_settings: advancedSettings,
    }),
  }, 'Không thể dựng lại scene.');
}

async function requestJson<T>(path: string, init: RequestInit | undefined, fallbackMessage: string): Promise<T> {
  try {
    const response = await fetch(apiUrl(path), init);
    if (!response.ok) throw await parseApiError(response, `${fallbackMessage} HTTP ${response.status}`);
    return response.json() as Promise<T>;
  } catch (caught) {
    if (caught instanceof ApiError) throw caught;
    throw networkApiError(caught, fallbackMessage);
  }
}

async function requestVoid(path: string, init: RequestInit | undefined, fallbackMessage: string): Promise<void> {
  try {
    const response = await fetch(apiUrl(path), init);
    if (!response.ok) throw await parseApiError(response, `${fallbackMessage} HTTP ${response.status}`);
  } catch (caught) {
    if (caught instanceof ApiError) throw caught;
    throw networkApiError(caught, fallbackMessage);
  }
}

function networkApiError(caught: unknown, fallbackMessage: string) {
  if (caught instanceof TypeError) {
    return new ApiError('Không kết nối được backend.', [
      `Frontend đang gọi API tại ${API_BASE_URL || 'cùng domain hiện tại'}.`,
      'Nếu deploy khác domain, hãy build frontend với VITE_API_BASE_URL trỏ tới backend.',
      'Nếu dùng đăng nhập khác domain, backend phải bật CORS credentials và frontend gọi API qua HTTPS.',
      'Nếu backend đã nhận OPTIONS nhưng trả 400, hãy thêm domain frontend vào CORS_ORIGINS và restart backend.',
      'Kiểm tra backend còn chạy và HTTPS/domain API truy cập được từ trình duyệt.',
    ]);
  }
  if (caught instanceof Error) return new ApiError(caught.message || fallbackMessage);
  return new ApiError(fallbackMessage);
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

function compactStoredSettings(settings: RuntimeSettings): RuntimeSettings {
  return {
    ...settings,
    openrouter: { ...settings.openrouter, api_key: '' },
    nvidia: { ...settings.nvidia, api_key: '' },
    ollama: { ...settings.ollama, api_key: '' },
    router9: { ...settings.router9, api_key: '' },
  };
}

function cleanText(value: string) {
  const text = value.trim();
  return text || undefined;
}
