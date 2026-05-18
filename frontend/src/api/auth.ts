import type { UserBasicSettings } from '../types/settings';
import { apiUrl, cleanText, requestJson, requestVoid } from './core';

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

export interface UserSettingsResponse {
  settings?: UserBasicSettings | null;
  updated_at?: string | null;
}

export type FeedbackStatus = 'pending' | 'received' | 'accepted';

export interface FeedbackResponse {
  id: string;
  subject: string;
  message: string;
  status: FeedbackStatus;
  admin_note?: string | null;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
}

export interface FeedbackStatusResponse {
  can_submit: boolean;
  pending_feedback?: FeedbackResponse | null;
  latest_feedback?: FeedbackResponse | null;
}

export function getGoogleOAuthStartUrl(): string {
  return apiUrl('/api/auth/google/start');
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

export async function register(email: string, password: string, displayName: string | undefined, acceptPrivacyPolicy: boolean, acceptTerms: boolean): Promise<AuthResponse> {
  return requestJson('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      email,
      password,
      display_name: displayName ? cleanText(displayName) : undefined,
      accept_privacy_policy: acceptPrivacyPolicy,
      accept_terms: acceptTerms,
    }),
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

export async function verifyEmail(token: string, otp: string): Promise<AuthResponse> {
  return requestJson('/api/auth/verify-email', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ token, otp }),
  }, 'Không thể xác minh email.');
}

export async function resendVerification(email: string): Promise<MessageResponse> {
  return requestJson('/api/auth/resend-verification', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email }),
  }, 'Không thể gửi lại email xác minh.');
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

export async function loginWithGoogle(): Promise<AuthResponse> {
  window.location.href = getGoogleOAuthStartUrl();
  throw new Error('Đang chuyển tới Google OAuth.');
}

export async function getUserSettings(): Promise<UserSettingsResponse> {
  return requestJson('/api/user/settings', { credentials: 'include' }, 'Không thể tải cấu hình cá nhân.');
}

export async function saveUserSettings(settings: UserBasicSettings): Promise<UserSettingsResponse> {
  return requestJson('/api/user/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ settings }),
  }, 'Không thể lưu cấu hình cá nhân.');
}

export async function getFeedbackStatus(): Promise<FeedbackStatusResponse> {
  return requestJson('/api/feedback/status', { credentials: 'include' }, 'Không thể tải trạng thái góp ý.');
}

export async function getMyFeedback(): Promise<FeedbackResponse[]> {
  return requestJson('/api/feedback', { credentials: 'include' }, 'Không thể tải lịch sử góp ý.');
}

export async function submitFeedback(subject: string, message: string): Promise<FeedbackResponse> {
  return requestJson('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ subject: cleanText(subject), message: cleanText(message) }),
  }, 'Không thể gửi góp ý.');
}
