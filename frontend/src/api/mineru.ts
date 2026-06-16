export interface MineruStatusResponse {
  ok: boolean;
  readiness?: {
    ready?: boolean;
    message?: string;
    detail?: string;
    backend?: string;
  };
  max_upload_mb?: number;
}

export interface MineruLlmProvidersResponse {
  ok: boolean;
  default_provider?: string;
  providers?: {
    nvidia?: {
      api_key_configured?: boolean;
      model?: string;
    };
    openrouter?: {
      api_key_configured?: boolean;
      model?: string;
    };
    router9?: {
      api_key_configured?: boolean;
      model?: string;
      only_mode?: boolean;
    };
  };
}

export interface MineruArtifact {
  kind?: string;
  filename?: string;
  relative_path?: string;
  download_url?: string;
  preview_url?: string;
  preview_kind?: string;
  size_bytes?: number;
}

export interface MineruResult {
  original_filename?: string;
  download_name?: string;
  backend_used?: string;
  docx_url?: string;
  artifacts_zip_url?: string;
  artifacts?: MineruArtifact[];
  warnings?: string[];
}

export interface MineruJobSnapshot {
  ok: boolean;
  done?: boolean;
  queued?: boolean;
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | string;
  stage?: string;
  progress?: number;
  message?: string;
  error?: string;
  terminal_lines?: string[];
  elapsed_seconds?: number | null;
  eta_seconds?: number | null;
  result?: MineruResult;
}

export interface MineruConvertOptions {
  file: File;
  backend: string;
  parseMethod: string;
  language: string;
  latexDelimitersType: string;
  formulaEnable: boolean;
  tableEnable: boolean;
  examFormat: boolean;
  startPage: string;
  endPage: string;
  serverUrl: string;
  llmMode: string;
  llmProvider: string;
  llmModel: string;
  llmApiKey: string;
  llmBaseUrl: string;
  llmReasoning: boolean;
  router9Only: boolean;
}

export function normalizeMineruBaseUrl(value: string | undefined) {
  const baseUrl = value?.trim().replace(/\/$/, '') ?? '';
  if (!baseUrl) return '';
  if (baseUrl.startsWith('http://') || baseUrl.startsWith('https://')) return baseUrl;
  return `https://${baseUrl}`;
}

export function mineruUrl(baseUrl: string, path: string) {
  if (!path) return '#';
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  return `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`;
}

export async function getMineruStatus(baseUrl: string): Promise<MineruStatusResponse> {
  return requestMineru<MineruStatusResponse>(baseUrl, '/api/status');
}

export async function getMineruLlmProviders(baseUrl: string): Promise<MineruLlmProvidersResponse> {
  return requestMineru<MineruLlmProvidersResponse>(baseUrl, '/api/llm/providers');
}

export async function convertPdfWithMineru(baseUrl: string, options: MineruConvertOptions): Promise<MineruJobSnapshot> {
  const formData = new FormData();
  formData.set('pdf', options.file);
  formData.set('backend', options.backend);
  formData.set('parse_method', options.parseMethod);
  formData.set('language', options.language);
  formData.set('latex_delimiters_type', options.latexDelimitersType);
  formData.set('formula_enable', options.formulaEnable ? 'true' : 'false');
  formData.set('table_enable', options.tableEnable ? 'true' : 'false');
  formData.set('exam_format', options.examFormat ? 'true' : 'false');
  formData.set('start_page', options.startPage || '1');
  formData.set('end_page', options.endPage);
  formData.set('server_url', options.serverUrl.trim());
  formData.set('llm_mode', options.llmMode);
  formData.set('llm_provider', options.llmProvider);
  formData.set('llm_model', options.llmModel.trim());
  formData.set('llm_api_key', options.llmApiKey.trim());
  formData.set('llm_base_url', options.llmBaseUrl.trim());
  formData.set('llm_reasoning', options.llmReasoning ? 'true' : 'false');
  formData.set('router9_only', options.router9Only ? 'true' : 'false');

  return requestMineru<MineruJobSnapshot>(baseUrl, '/api/convert', {
    method: 'POST',
    body: formData,
  });
}

export async function getMineruJob(baseUrl: string, jobId: string): Promise<MineruJobSnapshot> {
  return requestMineru<MineruJobSnapshot>(baseUrl, `/api/jobs/${encodeURIComponent(jobId)}`);
}

export async function fetchMineruText(baseUrl: string, path: string): Promise<string> {
  const response = await fetch(mineruUrl(baseUrl, path));
  if (!response.ok) throw new Error(`Không thể tải nội dung MinerU. HTTP ${response.status}`);
  return response.text();
}

async function requestMineru<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(mineruUrl(baseUrl, path), init);
  const body = await response.text();
  let parsed: unknown = null;
  try {
    parsed = body ? JSON.parse(body) : null;
  } catch {
    parsed = null;
  }

  if (!response.ok) {
    const message = parseMineruError(parsed) || body.trim() || `Dịch vụ chuyển đổi phản hồi lỗi ${response.status}.`;
    throw new Error(message);
  }

  if (!body.trim()) {
    throw new Error('Dịch vụ chuyển đổi chưa trả về dữ liệu. Vui lòng thử lại.');
  }

  if (parsed && typeof parsed === 'object' && 'ok' in parsed && (parsed as { ok?: boolean }).ok === false) {
    throw new Error(parseMineruError(parsed) || 'Dịch vụ chuyển đổi trả về lỗi.');
  }

  return parsed as T;
}

function parseMineruError(parsed: unknown) {
  if (!parsed || typeof parsed !== 'object') return '';
  const data = parsed as { error?: unknown; message?: unknown };
  if (typeof data.error === 'string' && data.error.trim()) return data.error.trim();
  if (typeof data.message === 'string' && data.message.trim()) return data.message.trim();
  return '';
}
