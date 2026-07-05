import type { RuntimeSettings } from '../types/settings';
import type { FeedbackResponse, FeedbackStatus, UserResponse } from './auth';
import type { RenderHistoryDetail, RenderHistoryItem } from './render';
import { cleanText, compactRuntimeSettings, queryString, requestJson, requestVoid } from './core';

export interface AdminSummaryResponse {
  users: number;
  active_users: number;
  admins: number;
  render_jobs: number;
  render_jobs_today: number;
  users_today: number;
  ai_warning_jobs: number;
  ai_warning_rate: number;
  daily_stats: Array<{ day: string; count: number }>;
}

export interface AdminUserFilters {
  q?: string;
  role?: string;
  status?: string;
  plan?: string;
}

export interface AdminRenderJobFilters {
  provider?: string;
  model?: string;
  renderer?: string;
  source_type?: string;
  user_id?: string;
  q?: string;
}

export interface AdminAuditLogFilters {
  action?: string;
  actor_user_id?: string;
  target_type?: string;
}

export interface AdminFeedbackResponse extends FeedbackResponse {
  user_id: string;
  user_email?: string | null;
  resolved_by?: string | null;
}

export interface AdminFeedbackFilters {
  status?: string;
  user_id?: string;
  q?: string;
}

export interface AdminSessionResponse {
  id: string;
  created_at: string;
  expires_at: string;
  last_seen_at?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
}

export interface AdminRenderHistoryItem extends RenderHistoryItem {
  user_id?: string | null;
  user_email?: string | null;
  user_display_name?: string | null;
}

export interface AdminRenderHistoryDetail extends RenderHistoryDetail {
  user_id?: string | null;
  user_email?: string | null;
  user_display_name?: string | null;
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

export interface AdminPlanResponse {
  id: string;
  name: string;
  daily_render_limit?: number | null;
  daily_ocr_limit?: number | null;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AdminUploadedFilesStorageDiagnostics {
  total_rows: number;
  rows_by_provider: Record<string, number>;
  rows_with_base64: number;
  external_rows_with_base64: number;
  external_only_rows: number;
  database_provider_rows: number;
  base64_chars: number;
  estimated_inline_bytes: number;
  default_cleanup_candidates: number;
  default_cleanup_reclaimable_bytes: number;
  error?: string;
}

export interface AdminDatabaseDiagnostics {
  backend: string;
  sqlite_path?: string | null;
  configured_sqlite_path: string;
  resolved_sqlite_path?: string | null;
  sqlite_path_diagnostics?: {
    configured_path: string;
    resolved_path: string;
    parent_exists: boolean;
    file_exists: boolean;
  };
  migration_drift?: {
    ok: boolean;
    available_count: number;
    applied_count: number;
    missing_migrations: string[];
    extra_migrations: string[];
    latest_available_migration?: string | null;
    latest_applied_migration?: string | null;
    unexpected_duplicate_prefixes: Record<string, string[]>;
  };
  migrations: Array<{ filename: string; applied_at: string }>;
  counts: Record<string, number | string>;
  uploaded_files_storage?: AdminUploadedFilesStorageDiagnostics;
  system_settings: Record<string, { updated_at: string; updated_by?: string | null }>;
  ai_settings: {
    exists: boolean;
    default_provider?: string | null;
    router9_model?: string | null;
    router9_only_mode?: boolean | null;
    router9_allowed_model_count: number;
    router9_scanned_model_count: number;
    legacy_canonical_drift?: {
      ok: boolean;
      differences: Array<{ field: string; legacy?: unknown; canonical?: unknown }>;
    };
  };
  model_registry?: {
    provider_count: number;
    model_count: number;
    allowed_model_count: number;
    stale_allowed_model_count: number;
    legacy_ai_settings_present: boolean;
    canonical_registry_active: boolean;
  };
}

export interface AdminDatabaseCleanupRequest {
  dry_run: boolean;
  limit_per_table?: number;
  tables?: string[] | null;
  min_age_hours?: number;
  verify_remote?: boolean;
  providers?: Array<'appwrite' | 'r2'> | null;
  confirm?: string | null;
  delete_remote?: boolean;
  delete_db_record?: boolean;
}

export interface AdminDevDataResetRequest {
  dry_run: boolean;
  confirm?: string | null;
  delete_upload_remotes?: boolean;
}

export interface AdminDevDataResetResponse {
  dry_run: boolean;
  confirm_required: string;
  tables: Record<string, number>;
  remote_deleted: number;
  remote_skipped: number;
  warnings: string[];
}

export interface AdminStorageCheckRequest {
  provider: 'auto' | 'appwrite' | 'r2';
  write?: boolean;
  read_back?: boolean;
  delete_after?: boolean;
}

export interface AdminStorageCheckResult {
  provider: string;
  status: string;
  configured: boolean;
  steps: Array<{ name: string; status: string; message: string }>;
  warnings: string[];
  storage_key?: string | null;
  external_file_id?: string | null;
  latency_ms: number;
}

export interface AdminStorageCheckResponse {
  provider: string;
  status: string;
  results: AdminStorageCheckResult[];
}

export interface AdminDatabaseCleanupTableResult {
  candidates: number;
  deleted?: number;
  cleared?: number;
  remote_deleted?: number;
  db_deleted?: number;
  skipped?: number;
  bytes_reclaimable?: number;
  bytes_cleared?: number;
  dry_run: boolean;
  limit: number;
  min_age_hours?: number;
  verify_remote?: boolean;
  providers?: string[];
  by_provider?: Record<string, { candidates: number; bytes_reclaimable: number }>;
  warnings?: string[];
  error?: string;
}

export interface AdminDatabaseCleanupResponse {
  dry_run: boolean;
  limit_per_table: number;
  tables: Record<string, AdminDatabaseCleanupTableResult>;
  warnings: string[];
  report_only_tables: string[];
}

export interface AdminProviderCheckResponse {
  provider: string;
  status: string;
  message: string;
  model?: string | null;
  latency_ms?: number | null;
}

export async function getAdminSummary(): Promise<AdminSummaryResponse> {
  return requestJson('/api/admin/summary', { credentials: 'include' }, 'Không thể tải dashboard quản trị.');
}

export async function getAdminUsers(filters: AdminUserFilters | string = {}): Promise<UserResponse[]> {
  const normalized = typeof filters === 'string' ? { q: filters } : filters;
  return requestJson(`/api/admin/users${queryString(normalized)}`, { credentials: 'include' }, 'Không thể tải danh sách người dùng.');
}

export async function getAdminPlans(): Promise<AdminPlanResponse[]> {
  return requestJson('/api/admin/plans', { credentials: 'include' }, 'Không thể tải danh sách gói người dùng.');
}

export async function updateAdminPlan(id: string, patch: Partial<Pick<AdminPlanResponse, 'name' | 'daily_render_limit' | 'daily_ocr_limit' | 'sort_order' | 'is_active'>>): Promise<AdminPlanResponse> {
  return requestJson(`/api/admin/plans/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(patch),
  }, 'Không thể cập nhật gói người dùng.');
}

export async function updateAdminUser(id: string, patch: Partial<Pick<UserResponse, 'role' | 'status' | 'display_name' | 'plan'>>): Promise<UserResponse> {
  return requestJson(`/api/admin/users/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(patch),
  }, 'Không thể cập nhật người dùng.');
}

export async function getAdminRenderJobs(filters: AdminRenderJobFilters = {}): Promise<AdminRenderHistoryItem[]> {
  return requestJson(`/api/admin/render-jobs${queryString(filters)}`, { credentials: 'include' }, 'Không thể tải lịch sử render hệ thống.');
}

export async function getAdminRenderJobDetail(id: string): Promise<AdminRenderHistoryDetail> {
  return requestJson(`/api/admin/render-jobs/${encodeURIComponent(id)}`, { credentials: 'include' }, 'Không thể tải chi tiết render job.');
}

export async function deleteAdminRenderJob(id: string): Promise<void> {
  await requestVoid(`/api/admin/render-jobs/${encodeURIComponent(id)}`, { method: 'DELETE', credentials: 'include' }, 'Không thể xoá render job.');
}

export async function getAdminSystemSettings(): Promise<SystemSettingResponse[]> {
  return requestJson('/api/admin/system-settings', { credentials: 'include' }, 'Không thể tải cấu hình hệ thống.');
}

export async function updateAdminSystemSetting(key: string, value: Record<string, unknown>): Promise<SystemSettingResponse> {
  return requestJson('/api/admin/system-settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ key, value }),
  }, 'Không thể lưu cấu hình hệ thống.');
}

export async function getAdminDatabaseDiagnostics(): Promise<AdminDatabaseDiagnostics> {
  return requestJson('/api/admin/database/diagnostics', { credentials: 'include' }, 'Không thể tải chẩn đoán database.');
}

export async function cleanupAdminDatabase(request: AdminDatabaseCleanupRequest): Promise<AdminDatabaseCleanupResponse> {
  return requestJson('/api/admin/database/cleanup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(request),
  }, 'Không thể chạy cleanup database.');
}

export async function resetAdminDevData(request: AdminDevDataResetRequest): Promise<AdminDevDataResetResponse> {
  return requestJson('/api/admin/database/reset-dev-data', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(request),
  }, 'Không thể reset dữ liệu dev.');
}

export async function checkAdminStorage(request: AdminStorageCheckRequest): Promise<AdminStorageCheckResponse> {
  return requestJson('/api/admin/storage/check', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(request),
  }, 'Không thể kiểm tra storage upload.');
}

export async function checkAdminProvider(provider: string, runtimeSettings: RuntimeSettings): Promise<AdminProviderCheckResponse> {
  return requestJson(`/api/admin/providers/${encodeURIComponent(provider)}/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ runtime_settings: compactRuntimeSettings(runtimeSettings) }),
  }, 'Không thể kiểm tra kết nối provider.');
}

export async function checkAllAdminProviders(runtimeSettings: RuntimeSettings): Promise<AdminProviderCheckResponse[]> {
  const response = await requestJson<{ results: AdminProviderCheckResponse[] }>('/api/admin/providers/check-all', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ runtime_settings: compactRuntimeSettings(runtimeSettings) }),
  }, 'Không thể kiểm tra tất cả provider.');
  return response.results;
}

export async function getAdminFeedback(filters: AdminFeedbackFilters = {}): Promise<AdminFeedbackResponse[]> {
  return requestJson(`/api/admin/feedback${queryString(filters)}`, { credentials: 'include' }, 'Không thể tải danh sách góp ý.');
}

export async function updateAdminFeedback(id: string, status: FeedbackStatus, adminNote?: string): Promise<AdminFeedbackResponse> {
  return requestJson(`/api/admin/feedback/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ status, admin_note: adminNote ? cleanText(adminNote) : undefined }),
  }, 'Không thể cập nhật góp ý.');
}

export async function getAdminAuditLogs(filters: AdminAuditLogFilters = {}): Promise<AuditLogResponse[]> {
  return requestJson(`/api/admin/audit-logs${queryString(filters)}`, { credentials: 'include' }, 'Không thể tải audit logs.');
}

export async function getAdminUserSessions(userId: string): Promise<AdminSessionResponse[]> {
  return requestJson(`/api/admin/users/${encodeURIComponent(userId)}/sessions`, { credentials: 'include' }, 'Không thể tải phiên đăng nhập của user.');
}

export async function revokeAdminUserSession(userId: string, sessionId: string): Promise<void> {
  await requestVoid(`/api/admin/users/${encodeURIComponent(userId)}/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE', credentials: 'include' }, 'Không thể thu hồi phiên đăng nhập của user.');
}

export async function revokeAllAdminUserSessions(userId: string): Promise<void> {
  await requestVoid(`/api/admin/users/${encodeURIComponent(userId)}/sessions/revoke-all`, { method: 'POST', credentials: 'include' }, 'Không thể thu hồi toàn bộ phiên đăng nhập của user.');
}
