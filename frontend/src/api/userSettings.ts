import type {
  UserAiModelsUpdateRequest,
  UserAiProviderCheckRequest,
  UserAiProviderCheckResponse,
  UserAiProviderUpdateRequest,
  UserAiTaskProfilesUpdateRequest,
  UserSettingsResponse,
} from '../types/userSettings';
import { requestJson } from './core';

export function getUserSettings(): Promise<UserSettingsResponse> {
  return requestJson('/api/user/settings', { credentials: 'include' }, 'Không thể tải cấu hình tài khoản.');
}

export function updateUserAiProvider(payload: UserAiProviderUpdateRequest): Promise<UserSettingsResponse> {
  return requestJson('/api/user/settings/ai-provider', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  }, 'Không thể lưu cấu hình BYOK.');
}

export function updateUserAiModels(payload: UserAiModelsUpdateRequest): Promise<UserSettingsResponse> {
  return requestJson('/api/user/settings/ai-models', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  }, 'Không thể lưu danh sách model BYOK.');
}

export function updateUserAiTaskProfiles(payload: UserAiTaskProfilesUpdateRequest): Promise<UserSettingsResponse> {
  return requestJson('/api/user/settings/ai-task-profiles', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  }, 'Không thể lưu task profile BYOK.');
}

export function checkUserAiProvider(payload: UserAiProviderCheckRequest): Promise<UserAiProviderCheckResponse> {
  return requestJson('/api/user/settings/ai-provider/check', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  }, 'Không thể kiểm tra kết nối BYOK.');
}
