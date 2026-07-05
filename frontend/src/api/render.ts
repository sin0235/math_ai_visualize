import type { AdvancedRenderSettings, MathScene, QualityRiskAdvisory, RenderAiSource, RenderFallbackSource, RenderResponse, Renderer } from '../types/scene';
import type { RuntimeSettings, ScannedModelInfo, SettingsDefaults } from '../types/settings';
import { buildExportFilename, type ExportFormatKey } from '../utils/exportFilename';
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
}

export interface RenderHistoryDetail extends RenderHistoryItem {
  scene: MathScene;
  payload: RenderResponse['payload'];
  warnings: string[];
  response?: RenderResponse | null;
  render_request?: Record<string, unknown> | null;
  advanced_settings?: Record<string, unknown> | null;
  runtime_settings?: Record<string, unknown> | null;
}

export type ExportFormat = ExportFormatKey;

export interface ProblemVariantsResponse {
  variants: string[];
  provider: string;
  model: string;
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
}

export type SolveConfidence = 'verified' | 'partial' | 'insufficient';

export interface SolveFact {
  source: 'given' | 'verified' | 'parameter_default' | 'construction_only' | string;
  text: string;
}

export interface SolveResponse {
  question: string;
  answer: string;
  steps: SolveStep[];
  warnings: string[];
  confidence?: SolveConfidence;
  method?: 'oxyz' | 'classical' | string;
  used_facts?: SolveFact[];
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

export async function getRenderHistoryDetail(id: string): Promise<RenderHistoryDetail> {
  return requestJson(`/api/history/${encodeURIComponent(id)}`, { credentials: 'include' }, 'Không thể tải chi tiết lịch sử.');
}

export async function deleteRenderHistory(id: string): Promise<void> {
  await requestVoid(`/api/history/${encodeURIComponent(id)}`, { method: 'DELETE', credentials: 'include' }, 'Không thể xoá lịch sử.');
}

export async function renderProblem(
  problemText: string,
  tier: 'tier1' | 'tier2' | 'tier3' = 'tier1',
  advancedSettings?: AdvancedRenderSettings,
  preferredRenderer?: Renderer,
  runtimeSettings?: RuntimeSettings,
  preferredAiModel?: string,
): Promise<RenderResponse> {
  return requestJson('/api/render', {
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
  }, 'Không thể dựng hình.');
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

export async function uploadOcrImage(file: File): Promise<OcrUploadResponse> {
  const formData = new FormData();
  formData.set('file', file);
  return requestJson('/api/ocr/uploads', {
    method: 'POST',
    credentials: 'include',
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

export async function scanProviderModels(
  provider: 'openrouter' | 'openai_compat' | 'nvidia' | 'ollama',
  runtimeSettings: RuntimeSettings,
): Promise<ScannedModelInfo[]> {
  const response = await requestJson<{ provider: string; models: ScannedModelInfo[] }>('/api/ai/models/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    signal: timeoutSignal(30_000),
    body: JSON.stringify({ provider, runtime_settings: compactRuntimeSettings(runtimeSettings) }),
  }, 'Không thể quét model provider.');
  return response.models;
}

export async function scanRouter9Models(runtimeSettings: RuntimeSettings): Promise<ScannedModelInfo[]> {
  const response = await requestJson<{ provider: string; models: ScannedModelInfo[] }>('/api/ai/router9/models/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    signal: timeoutSignal(30_000),
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

export async function generateProblemVariants(
  scene: MathScene,
  count: number,
  originalProblem?: string,
  runtimeSettings?: RuntimeSettings,
  preferredAiModel?: string,
  response?: RenderResponse | null,
): Promise<ProblemVariantsResponse> {
  return requestJson<ProblemVariantsResponse>(
    '/api/problem/variants',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        scene,
        response,
        count,
        original_problem: originalProblem,
        preferred_ai_model: preferredAiModel,
        runtime_settings: compactRuntimeSettings(runtimeSettings),
      }),
    },
    'Không thể sinh đề biến thể.',
  );
}

export async function exportScene(
  format: ExportFormat,
  scene: MathScene,
  advancedSettings: AdvancedRenderSettings,
  renderResponse?: RenderResponse | null,
): Promise<{ blob: Blob; filename: string }> {
  const meta = EXPORT_META[format];
  try {
    const response = await fetchWithRetry(apiUrl(meta.path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ scene, response: renderResponse, advanced_settings: advancedSettings }),
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
  scene: unknown,
  question: string,
  geometryMethod: 'oxyz' | 'classical' = 'oxyz',
  runtimeSettings?: RuntimeSettings,
  response?: RenderResponse | null,
): Promise<SolveResponse> {
  return requestJson('/api/solve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ scene, response, question, geometry_method: geometryMethod, runtime_settings: compactRuntimeSettings(runtimeSettings) }),
  }, 'Không thể giải toán từ scene này.');
}
