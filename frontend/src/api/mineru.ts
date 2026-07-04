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

export interface MineruProviderConfig {
  api_key_configured?: boolean;
  api_key_env?: string;
  base_url?: string;
  model?: string;
  only_mode?: boolean;
}

export interface MineruProviderDefaults {
  default_provider?: string;
  nvidia?: MineruProviderConfig;
  openrouter?: MineruProviderConfig;
  router9?: MineruProviderConfig;
}

export interface MineruLlmProvidersResponse {
  ok: boolean;
  providers?: MineruProviderDefaults;
}

export interface MineruSelectOption {
  value: string;
  label: string;
}

export interface MineruPageConfig {
  options: {
    backends: MineruSelectOption[];
    parseMethods: MineruSelectOption[];
    languages: MineruSelectOption[];
    latexDelimiters: MineruSelectOption[];
    llmModes: MineruSelectOption[];
    llmProviders: MineruSelectOption[];
    llmModels: MineruSelectOption[];
  };
  values: {
    backend: string;
    parseMethod: string;
    language: string;
    latexDelimitersType: string;
    formulaEnable: boolean;
    tableEnable: boolean;
    examFormat: boolean;
    llmMode: string;
    llmProvider: string;
    llmModel: string;
    llmReasoning: boolean;
    router9Only: boolean;
    serverUrl: string;
  };
}

export interface MineruArtifact {
  kind?: string;
  label?: string;
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
  elapsed_seconds?: number;
  page_count?: number;
  source_kind?: string;
  source_file?: string;
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

export interface MineruDocxPreviewResponse {
  ok: boolean;
  filename: string;
  html: string;
}

const fallbackPageConfig: MineruPageConfig = {
  options: {
    backends: options(['auto', 'pipeline', 'hybrid-engine', 'hybrid-auto-engine', 'vlm-engine', 'vlm-auto-engine', 'hybrid-http-client', 'vlm-http-client']),
    parseMethods: options(['auto', 'ocr', 'txt']),
    languages: [
      { value: 'ch', label: 'Chinese + English' },
      { value: 'en', label: 'English' },
      { value: 'latin', label: 'Latin/Vietnamese' },
      { value: 'ch_lite', label: 'Chinese Lite' },
      { value: 'ch_server', label: 'Chinese Server' },
      { value: 'korean', label: 'Korean' },
      { value: 'japan', label: 'Japanese' },
      { value: 'chinese_cht', label: 'Traditional Chinese' },
      { value: 'arabic', label: 'Arabic' },
      { value: 'cyrillic', label: 'Cyrillic' },
      { value: 'east_slavic', label: 'East Slavic' },
      { value: 'devanagari', label: 'Devanagari' },
      { value: 'ta', label: 'Tamil' },
      { value: 'te', label: 'Telugu' },
      { value: 'ka', label: 'Kannada' },
      { value: 'th', label: 'Thai' },
      { value: 'el', label: 'Greek' },
    ],
    latexDelimiters: [
      { value: 'b', label: '\\(...\\) / \\[...\\]' },
      { value: 'a', label: '$...$ / $$...$$' },
      { value: 'all', label: 'All in DOCX parser' },
    ],
    llmModes: [
      { value: 'off', label: 'Tắt' },
      { value: 'review', label: 'Chỉ kiểm tra' },
      { value: 'correct', label: 'Tự sửa lỗi rõ ràng' },
    ],
    llmProviders: [
      { value: 'auto', label: 'Auto theo model' },
      { value: 'nvidia', label: 'NVIDIA' },
      { value: 'openrouter', label: 'OpenRouter' },
      { value: 'router9', label: '9route / 9router' },
    ],
    llmModels: [
      { value: 'google/gemma-3-27b-it', label: 'NVIDIA: Gemma 3 27B IT' },
      { value: 'openrouter/google/gemma-4-26b-a4b-it:free', label: 'OpenRouter: Gemma 4 26B A4B IT Free' },
    ],
  },
  values: {
    backend: 'auto',
    parseMethod: 'auto',
    language: 'ch',
    latexDelimitersType: 'b',
    formulaEnable: true,
    tableEnable: true,
    examFormat: false,
    llmMode: 'off',
    llmProvider: 'nvidia',
    llmModel: 'google/gemma-3-27b-it',
    llmReasoning: false,
    router9Only: false,
    serverUrl: '',
  },
};

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

export async function getMineruPageConfig(baseUrl: string): Promise<MineruPageConfig> {
  const response = await fetch(mineruUrl(baseUrl, '/'));
  if (!response.ok) return getDefaultMineruPageConfig();
  const html = await response.text();
  if (!html.trim()) return getDefaultMineruPageConfig();
  return parseMineruPageConfig(html);
}

export function getDefaultMineruPageConfig(): MineruPageConfig {
  return {
    options: {
      backends: [...fallbackPageConfig.options.backends],
      parseMethods: [...fallbackPageConfig.options.parseMethods],
      languages: [...fallbackPageConfig.options.languages],
      latexDelimiters: [...fallbackPageConfig.options.latexDelimiters],
      llmModes: [...fallbackPageConfig.options.llmModes],
      llmProviders: [...fallbackPageConfig.options.llmProviders],
      llmModels: [...fallbackPageConfig.options.llmModels],
    },
    values: { ...fallbackPageConfig.values },
  };
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

export async function getMineruDocxPreview(baseUrl: string, path: string): Promise<MineruDocxPreviewResponse> {
  return requestMineru<MineruDocxPreviewResponse>(baseUrl, path);
}

export async function fetchMineruText(baseUrl: string, path: string): Promise<string> {
  const response = await fetch(mineruUrl(baseUrl, path));
  if (!response.ok) throw new Error(`Không thể tải nội dung MinerU. HTTP ${response.status}`);
  return response.text();
}

function parseMineruPageConfig(html: string): MineruPageConfig {
  const document = new DOMParser().parseFromString(html, 'text/html');
  const selectOptions = (name: string, fallback: MineruSelectOption[]) => {
    const select = document.querySelector<HTMLSelectElement>(`select[name="${name}"]`);
    if (!select) return fallback;
    const parsed = Array.from(select.options).map((option) => ({ value: option.value, label: option.textContent?.trim() || option.value }));
    return parsed.length ? parsed : fallback;
  };
  const selectValue = (name: string, fallback: string) => {
    const select = document.querySelector<HTMLSelectElement>(`select[name="${name}"]`);
    return select?.value || fallback;
  };
  const inputValue = (name: string, fallback = '') => {
    const input = document.querySelector<HTMLInputElement>(`input[name="${name}"]`);
    return input?.value || fallback;
  };
  const checked = (name: string, fallback: boolean) => {
    const input = document.querySelector<HTMLInputElement>(`input[name="${name}"]`);
    return input ? input.checked : fallback;
  };

  return {
    options: {
      backends: selectOptions('backend', fallbackPageConfig.options.backends),
      parseMethods: selectOptions('parse_method', fallbackPageConfig.options.parseMethods),
      languages: selectOptions('language', fallbackPageConfig.options.languages),
      latexDelimiters: selectOptions('latex_delimiters_type', fallbackPageConfig.options.latexDelimiters),
      llmModes: selectOptions('llm_mode', fallbackPageConfig.options.llmModes),
      llmProviders: selectOptions('llm_provider', fallbackPageConfig.options.llmProviders),
      llmModels: selectOptions('llm_model', fallbackPageConfig.options.llmModels),
    },
    values: {
      backend: selectValue('backend', fallbackPageConfig.values.backend),
      parseMethod: selectValue('parse_method', fallbackPageConfig.values.parseMethod),
      language: selectValue('language', fallbackPageConfig.values.language),
      latexDelimitersType: selectValue('latex_delimiters_type', fallbackPageConfig.values.latexDelimitersType),
      formulaEnable: checked('formula_enable', fallbackPageConfig.values.formulaEnable),
      tableEnable: checked('table_enable', fallbackPageConfig.values.tableEnable),
      examFormat: checked('exam_format', fallbackPageConfig.values.examFormat),
      llmMode: selectValue('llm_mode', fallbackPageConfig.values.llmMode),
      llmProvider: 'nvidia',
      llmModel: fallbackPageConfig.values.llmModel,
      llmReasoning: checked('llm_reasoning', fallbackPageConfig.values.llmReasoning),
      router9Only: checked('router9_only', fallbackPageConfig.values.router9Only),
      serverUrl: inputValue('server_url', fallbackPageConfig.values.serverUrl),
    },
  };
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

function options(values: string[]): MineruSelectOption[] {
  return values.map((value) => ({ value, label: value }));
}
