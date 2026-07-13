import type { AdvancedRenderSettings, MathScene, QualityRiskAdvisory, RenderAiSource, RenderFallbackSource, RenderResponse, Renderer } from '../types/scene';
import type { CommittedSceneRefV3, MathSceneV3, SceneCommand, SceneWorkspaceResponseV3 } from '../types/sceneV3';
import type { RuntimeSettings, ScannedModelInfo, SettingsDefaults } from '../types/settings';
import { buildExportFilename, type ExportFormatKey } from '../utils/exportFilename';
import { decodeRenderHistoryDetail } from '../utils/renderHistoryV3';
import { ApiError, apiUrl, compactRuntimeSettings, fetchWithRetry, networkApiError, parseApiError, requestJson, requestVoid, timeoutSignal } from './core';

export interface OcrResponse {
  text: string;
  provider: string;
  model: string;
  warnings: string[];
}

export interface OcrUploadResponse {
  file_id: string;
  filename: string;
  content_type: string;
  size: number;
  storage_provider: string;
  public_url?: string | null;
}

export interface HealthResponse {
  status: string;
  app: string;
}

export interface RenderHistoryItem {
  id: string;
  problem_text: string;
  provider?: string | null;
  model?: string | null;
  created_at: string;
  source_type: string;
  renderer?: string | null;
  degraded?: boolean;
  fallback_source?: RenderFallbackSource;
  ai_source?: RenderAiSource;
  schema_version?: string;
  title?: string | null;
  problem_preview?: string | null;
  topic?: string;
  grade?: string | null;
  tier?: string | null;
  is_favorite?: boolean;
  archived_at?: string | null;
  last_opened_at?: string | null;
  updated_at?: string | null;
  tags?: string[];
}

export interface RenderHistoryPatchRequest {
  title?: string | null;
  project_id?: string | null;
  is_favorite?: boolean | null;
  archived?: boolean | null;
  tags?: string[] | null;
}

export interface SceneRevisionResponse {
  id: string;
  history_item_id: string;
  render_job_id?: string | null;
  revision_no: number;
  change_source: string;
  change_summary?: string | null;
  created_at: string;
  schema_version: string;
  scene_id?: string | null;
  snapshot_revision?: number | null;
}

interface RenderHistoryDetailBase extends RenderHistoryItem {
  render_request?: Record<string, unknown> | null;
  runtime_settings?: Record<string, unknown> | null;
}

export interface RenderHistoryDetailV2 extends RenderHistoryDetailBase {
  kind: 'math_scene_v2';
  scene: MathScene;
  payload: RenderResponse['payload'];
  warnings: string[];
  response?: RenderResponse | null;
  advanced_settings?: Record<string, unknown> | null;
}

export interface RenderHistoryDetailV3 extends RenderHistoryDetailBase {
  kind: 'math_scene_v3';
  workspace: SceneWorkspaceResponseV3;
  snapshot_revision: number;
  command_log: SceneCommand[];
}

export type RenderHistoryDetail = RenderHistoryDetailV2 | RenderHistoryDetailV3;

export type ExportFormat = ExportFormatKey;

export interface ProblemVariantsResponse {
  variants: string[];
  provider: string;
  model: string;
}

export interface ConstructionAction {
  action_id: string;
  type: 'highlight' | 'add_point' | 'connect_points' | 'project_point' | 'intersect_objects' | 'add_auxiliary_line' | 'add_auxiliary_plane';
  source_object_ids: string[];
  result_object_id?: string | null;
  parameters: Record<string, unknown>;
}

export interface SolveStep {
  index: number;
  title: string;
  explanation: string;
  expression: string | null;
  result: string | null;
  highlight: string[];
  kind?: string | null;
  formula_latex?: string | null;
  substitution_latex?: string | null;
  result_latex?: string | null;
  sub_steps?: SolveStep[];
  theorem?: string | null;
  theorem_id?: string | null;
  claim?: string | null;
  depends_on?: string[];
  highlight_object_ids?: string[];
  relation_ids?: string[];
  construction_actions?: ConstructionAction[];
}

export type SolveConfidence = 'verified' | 'partial' | 'insufficient';

export interface SolveFact {
  source: 'given' | 'verified' | 'parameter_default' | 'construction_only' | string;
  text: string;
}

export interface SolveTheorem {
  name: string;
  statement?: string;
}

export interface SolveResponse {
  question: string;
  answer: string;
  steps: SolveStep[];
  warnings: string[];
  confidence?: SolveConfidence;
  method?: 'oxyz' | 'classical' | string;
  used_facts?: SolveFact[];
  used_theorems?: SolveTheorem[];
  data_issues?: string[];
  advisory?: QualityRiskAdvisory | null;
}

const EXPORT_META: Record<ExportFormat, { path: string; errorMessage: string }> = {
  png: { path: '/api/export/png', errorMessage: 'Không thể xuất PNG.' },
  jpg: { path: '/api/export/jpg', errorMessage: 'Không thể xuất JPG.' },
  svg: { path: '/api/export/svg', errorMessage: 'Không thể xuất SVG.' },
  'katex-html': { path: '/api/export/katex-html', errorMessage: 'Không thể xuất HTML KaTeX.' },
  tikz: { path: '/api/export/tikz', errorMessage: 'Không thể xuất TikZ.' },
  pdf: { path: '/api/export/pdf', errorMessage: 'Không thể xuất PDF.' },
  ggb: { path: '/api/export/ggb', errorMessage: 'Không thể xuất GeoGebra.' },
};

export async function getHealth(): Promise<HealthResponse> {
  return requestJson('/api/health', undefined, 'Không thể kiểm tra trạng thái backend.');
}

export async function getSettingsDefaults(): Promise<SettingsDefaults> {
  return requestJson('/api/settings/defaults', undefined, 'Không thể đọc cấu hình backend.');
}

export async function getRenderHistory(): Promise<RenderHistoryItem[]> {
  return requestJson('/api/history', { credentials: 'include' }, 'Không thể tải lịch sử dựng hình.');
}

export async function patchRenderHistory(id: string, patch: RenderHistoryPatchRequest): Promise<RenderHistoryItem> {
  return requestJson(`/api/history/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(patch),
  }, 'Không thể cập nhật lịch sử.');
}

export async function getRenderHistoryRevisions(id: string): Promise<SceneRevisionResponse[]> {
  return requestJson(`/api/history/${encodeURIComponent(id)}/revisions`, { credentials: 'include' }, 'Không thể tải phiên bản scene.');
}

export async function getRenderHistoryDetail(id: string): Promise<RenderHistoryDetail> {
  const value = await requestJson<unknown>(`/api/history/${encodeURIComponent(id)}`, { credentials: 'include' }, 'Không thể tải chi tiết lịch sử.');
  return decodeRenderHistoryDetail(value);
}

export async function restoreRenderHistoryV3(id: string, snapshotRevision?: number): Promise<SceneWorkspaceResponseV3> {
  return requestJson(`/api/history/${encodeURIComponent(id)}/restore`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ snapshot_revision: snapshotRevision }),
  }, 'Không thể khôi phục scene workspace v3.');
}

export async function deleteRenderHistory(id: string): Promise<void> {
  await requestVoid(`/api/history/${encodeURIComponent(id)}`, { method: 'DELETE', credentials: 'include' }, 'Không thể xoá lịch sử.');
}

export type RenderJobCreateResponse = {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
};

export type RenderJobStatusResponse = {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  response?: RenderResponse | null;
  error?: { code?: string; message?: string; debug_message?: string } | null;
};

export async function renderProblem(
  problemText: string,
  tier: 'tier1' | 'tier2' | 'tier3' = 'tier1',
  advancedSettings?: AdvancedRenderSettings,
  preferredRenderer?: Renderer,
  runtimeSettings?: RuntimeSettings,
  preferredAiModel?: string,
  options?: { async?: boolean },
): Promise<RenderResponse> {
  const body = {
    problem_text: problemText,
    tier,
    preferred_renderer: preferredRenderer,
    advanced_settings: advancedSettings,
    ...preferredAiModelPayload(preferredAiModel),
    runtime_settings: compactRuntimeSettings(runtimeSettings),
  };
  if (options?.async) {
    const created = await requestJson<RenderJobCreateResponse>('/api/render/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(body),
    }, 'Không thể xếp hàng dựng hình.');
    return pollRenderJob(created.job_id);
  }
  return requestJson('/api/render', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  }, 'Không thể dựng hình.');
}

export async function renderProblemV3(
  problemText: string,
  tier: 'tier1' | 'tier2' | 'tier3' = 'tier1',
  advancedSettings?: AdvancedRenderSettings,
  preferredRenderer?: Renderer,
  runtimeSettings?: RuntimeSettings,
  preferredAiModel?: string,
): Promise<SceneWorkspaceResponseV3> {
  return requestJson('/api/render/v3', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      problem_text: problemText,
      tier,
      preferred_renderer: preferredRenderer,
      advanced_settings: advancedSettings,
      ...preferredAiModelPayload(preferredAiModel),
      runtime_settings: compactRuntimeSettings(runtimeSettings),
    }),
  }, 'Không thể dựng scene workspace v3.');
}

async function pollRenderJob(jobId: string, maxMs = 320_000): Promise<RenderResponse> {
  const started = Date.now();
  let delay = 600;
  while (Date.now() - started < maxMs) {
    const status = await requestJson<RenderJobStatusResponse>(
      `/api/render/jobs/${encodeURIComponent(jobId)}`,
      { credentials: 'include' },
      'Không thể kiểm tra tiến độ dựng hình.',
    );
    if (status.status === 'completed' && status.response) {
      return status.response;
    }
    if (status.status === 'failed') {
      const message = status.error?.debug_message || status.error?.message || 'Dựng hình thất bại.';
      throw new ApiError(message, [status.error?.code || 'RENDER_FAILED'].filter(Boolean) as string[]);
    }
    await new Promise((resolve) => window.setTimeout(resolve, delay));
    delay = Math.min(delay + 400, 2500);
  }
  throw new ApiError('Dựng hình quá thời gian chờ. Vui lòng thử lại.');
}

function preferredAiModelPayload(selection?: string) {
  const value = selection?.trim();
  if (!value || value === 'default:auto') return {};
  if (value.startsWith('default:')) {
    const provider = value.slice('default:'.length);
    return provider ? { preferred_ai_provider: provider } : {};
  }
  if (value.startsWith('model:')) {
    const payload = value.slice('model:'.length);
    const separator = payload.indexOf(':');
    if (separator > 0) {
      return {
        preferred_ai_provider: payload.slice(0, separator),
        preferred_ai_model: payload.slice(separator + 1),
      };
    }
  }
  return { preferred_ai_model: value };
}

export async function uploadOcrImage(file: File, signal?: AbortSignal): Promise<OcrUploadResponse> {
  const formData = new FormData();
  formData.set('file', file);
  return requestJson('/api/ocr/uploads', {
    method: 'POST',
    credentials: 'include',
    signal,
    body: formData,
  }, 'Không thể upload ảnh OCR.');
}

export async function ocrImage(imageDataUrl: string): Promise<OcrResponse> {
  return ocrImageByPayload({ image_data_url: imageDataUrl });
}

export async function ocrImageByUploadId(uploadId: string): Promise<OcrResponse> {
  return ocrImageByPayload({ upload_id: uploadId });
}

function ocrImageByPayload(payload: { image_data_url: string } | { upload_id: string }): Promise<OcrResponse> {
  return requestJson('/api/ocr', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  }, 'Không thể OCR ảnh đề bài.');
}

const MODEL_SCAN_TIMEOUT_MS = 120_000;

export async function scanProviderModels(
  provider: 'openrouter' | 'openai_compat' | 'nvidia' | 'ollama',
  runtimeSettings: RuntimeSettings,
): Promise<ScannedModelInfo[]> {
  const response = await requestJson<{ provider: string; models: ScannedModelInfo[] }>('/api/ai/models/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    signal: timeoutSignal(MODEL_SCAN_TIMEOUT_MS),
    body: JSON.stringify({ provider, runtime_settings: compactRuntimeSettings(runtimeSettings) }),
  }, 'Không thể quét model provider.');
  return response.models;
}

export async function scanRouter9Models(runtimeSettings: RuntimeSettings): Promise<ScannedModelInfo[]> {
  const response = await requestJson<{ provider: string; models: ScannedModelInfo[] }>('/api/ai/router9/models/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    signal: timeoutSignal(MODEL_SCAN_TIMEOUT_MS),
    body: JSON.stringify({ runtime_settings: compactRuntimeSettings(runtimeSettings) }),
  }, 'Không thể quét model 9router.');
  return response.models;
}

export async function renderEditedScene(scene: MathScene, advancedSettings: AdvancedRenderSettings, response?: RenderResponse | null): Promise<RenderResponse> {
  return requestJson('/api/render/scene', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      scene,
      response,
      advanced_settings: advancedSettings,
    }),
  }, 'Không thể dựng lại scene.');
}

export async function createSceneWorkspaceV3(scene: MathSceneV3): Promise<SceneWorkspaceResponseV3> {
  return requestJson('/api/render/v3/workspaces', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ scene }),
  }, 'Không thể tạo scene workspace.');
}

export async function getSceneWorkspaceV3(sceneId: string): Promise<SceneWorkspaceResponseV3> {
  return requestJson(
    `/api/render/v3/workspaces/${encodeURIComponent(sceneId)}`,
    { credentials: 'include' },
    'Không thể tải scene workspace.',
  );
}

export async function confirmSceneWorkspaceV3(reference: CommittedSceneRefV3): Promise<SceneWorkspaceResponseV3> {
  return requestJson(`/api/render/v3/workspaces/${encodeURIComponent(reference.scene_id)}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ revision: reference.revision }),
  }, 'Không thể xác nhận scene workspace.');
}

export async function applySceneCommandV3(command: SceneCommand): Promise<SceneWorkspaceResponseV3> {
  return requestJson('/api/render/v3/commands', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ command }),
  }, 'Không thể áp dụng chỉnh sửa scene.');
}

export async function generateProblemVariants(
  sceneRef: CommittedSceneRefV3,
  count: number,
  originalProblem?: string,
  runtimeSettings?: RuntimeSettings,
  preferredAiModel?: string,
): Promise<ProblemVariantsResponse> {
  return requestJson<ProblemVariantsResponse>(
    '/api/problem/variants',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        scene_ref: sceneRef,
        count,
        original_problem: originalProblem,
        preferred_ai_model: preferredAiModel,
        runtime_settings: compactRuntimeSettings(runtimeSettings),
      }),
    },
    'Không thể sinh đề biến thể.',
  );
}

export interface ExportViewCapture {
  mime_type: 'image/png' | 'image/jpeg';
  data_url: string;
  width: number;
  height: number;
}

export async function exportScene(
  format: ExportFormat,
  sceneRef: CommittedSceneRefV3,
  scene: MathSceneV3,
  viewCapture?: ExportViewCapture | null,
): Promise<{ blob: Blob; filename: string }> {
  const meta = EXPORT_META[format];
  try {
    const response = await fetchWithRetry(apiUrl(meta.path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ scene_ref: sceneRef, view_capture: viewCapture ?? undefined }),
    });
    if (!response.ok) throw await parseApiError(response, `${meta.errorMessage} HTTP ${response.status}`);
    const blob = await response.blob();
    return { blob, filename: buildExportFilename(scene, format) };
  } catch (caught) {
    if (caught instanceof ApiError) throw caught;
    throw networkApiError(caught, meta.errorMessage);
  }
}

export async function solveProblem(
  sceneRef: CommittedSceneRefV3,
  question: string,
  geometryMethod: 'oxyz' | 'classical' = 'oxyz',
  runtimeSettings?: RuntimeSettings,
): Promise<SolveResponse> {
  return requestJson('/api/solve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ scene_ref: sceneRef, question, geometry_method: geometryMethod, runtime_settings: compactRuntimeSettings(runtimeSettings) }),
  }, 'Không thể giải toán từ scene này.');
}
