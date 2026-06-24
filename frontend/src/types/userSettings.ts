export type UserAiTask = 'render' | 'reasoning' | 'ocr' | 'solver' | 'chat';

export interface UserAiProviderSettings {
  enabled: boolean;
  base_url: string;
  api_key_configured: boolean;
  api_key_last4?: string | null;
  api_key_updated_at?: string | null;
  updated_at?: string | null;
}

export interface UserAiModelSettings {
  model_id: string;
  label: string;
  supports_vision: boolean;
  enabled: boolean;
}

export interface UserAiModelSettingsResponse extends UserAiModelSettings {
  id: string;
}

export interface UserAiTaskProfileSettings {
  task: UserAiTask;
  model_id: string;
  enabled: boolean;
}

export interface UserSettingsResponse {
  ai_provider: UserAiProviderSettings;
  models: UserAiModelSettingsResponse[];
  task_profiles: UserAiTaskProfileSettings[];
}

export interface UserAiProviderUpdateRequest {
  enabled: boolean;
  base_url: string;
  api_key?: string | null;
  clear_api_key?: boolean;
}

export interface UserAiModelsUpdateRequest {
  models: UserAiModelSettings[];
}

export interface UserAiTaskProfilesUpdateRequest {
  task_profiles: UserAiTaskProfileSettings[];
}

export interface UserAiProviderCheckRequest {
  base_url: string;
  api_key?: string | null;
  model: string;
}

export interface UserAiProviderCheckResponse {
  ok: boolean;
  message: string;
}

export const USER_AI_TASK_LABELS: Record<UserAiTask, string> = {
  render: 'Dựng hình',
  reasoning: 'Suy luận',
  ocr: 'OCR ảnh',
  solver: 'Giải toán',
  chat: 'Chat',
};

export const USER_AI_TASKS: UserAiTask[] = ['render', 'reasoning', 'ocr', 'solver', 'chat'];
