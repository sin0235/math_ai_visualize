import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';

import { convertPdfWithMineru, fetchMineruText, getMineruJob, getMineruStatus, mineruUrl, type MineruArtifact, type MineruJobSnapshot, type MineruResult } from '../api/mineru';
import type { ModelOption } from './ProblemInput';
import type { RuntimeSettings } from '../types/settings';

type UploadState = 'idle' | 'queued' | 'running' | 'completed' | 'failed';

interface PdfToWordPageProps {
  enabled: boolean;
  apiBaseUrl: string;
  modelOptions: ModelOption[];
  runtimeSettings: RuntimeSettings;
  router9Only: boolean;
  onOpenSettings: () => void;
  onUseProblemText: (text: string) => void;
}

const MAX_LOCAL_UPLOAD_MB = 128;
const MAX_PROBLEM_TEXT_CHARS = 2000;
const ALLOWED_LLM_PROVIDERS = new Set(['auto', 'openrouter', 'router9', 'nvidia']);
const backendOptions = [
  { value: 'auto', label: 'Tự động' },
  { value: 'pipeline', label: 'Ổn định' },
  { value: 'hybrid-auto-engine', label: 'Cân bằng' },
  { value: 'vlm-auto-engine', label: 'Chính xác cao' },
  { value: 'hybrid-http-client', label: 'Cân bằng từ xa' },
  { value: 'vlm-http-client', label: 'Chính xác cao từ xa' },
];
const languageOptions = [
  { value: 'latin', label: 'Latin/Vietnamese' },
  { value: 'en', label: 'English' },
  { value: 'ch', label: 'Chinese + English' },
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
];

export function PdfToWordPage({
  enabled,
  apiBaseUrl,
  modelOptions,
  runtimeSettings,
  router9Only,
  onOpenSettings,
  onUseProblemText,
}: PdfToWordPageProps) {
  const [selectedModelKey, setSelectedModelKey] = useState(modelOptions[0]?.key ?? 'provider:auto');
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [status, setStatus] = useState<UploadState>('idle');
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [terminalLines, setTerminalLines] = useState<string[]>([]);
  const [result, setResult] = useState<MineruResult | null>(null);
  const [remoteMaxUploadMb, setRemoteMaxUploadMb] = useState<number | null>(null);
  const [readinessMessage, setReadinessMessage] = useState('');
  const [readinessReady, setReadinessReady] = useState<boolean | null>(null);
  const [backend, setBackend] = useState('auto');
  const [parseMethod, setParseMethod] = useState('auto');
  const [language, setLanguage] = useState('latin');
  const [latexDelimitersType, setLatexDelimitersType] = useState('b');
  const [formulaEnable, setFormulaEnable] = useState(true);
  const [tableEnable, setTableEnable] = useState(true);
  const [llmMode, setLlmMode] = useState('review');
  const [examFormat, setExamFormat] = useState(true);
  const [startPage, setStartPage] = useState('1');
  const [endPage, setEndPage] = useState('');
  const [serverUrl, setServerUrl] = useState('');
  const [importingText, setImportingText] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollAbortRef = useRef(false);

  const selectedModel = modelOptions.find((option) => option.key === selectedModelKey) ?? modelOptions[0];
  const llmProvider = normalizePdfLlmProvider(router9Only ? 'router9' : selectedModel?.provider);
  const llmModel = selectedModel?.modelId ?? providerDefaultModel(runtimeSettings, llmProvider);
  const credentials = providerCredentials(runtimeSettings, llmProvider);
  const maxUploadMb = remoteMaxUploadMb ?? Number(import.meta.env.VITE_PDF_WORD_MAX_UPLOAD_MB || MAX_LOCAL_UPLOAD_MB);
  const busy = status === 'queued' || status === 'running';
  const markdownArtifact = result?.artifacts?.find((artifact) => artifact.kind === 'markdown' || artifact.filename?.toLowerCase().endsWith('.md'));

  const readinessLabel = useMemo(() => {
    if (!enabled || !apiBaseUrl) return 'Chưa sẵn sàng';
    if (readinessReady === null) return 'Đang kiểm tra';
    return readinessReady ? 'Sẵn sàng xử lý' : 'Chưa sẵn sàng';
  }, [apiBaseUrl, enabled, readinessReady]);

  useEffect(() => {
    if (!modelOptions.some((option) => option.key === selectedModelKey)) {
      setSelectedModelKey(modelOptions[0]?.key ?? 'provider:auto');
    }
  }, [modelOptions, selectedModelKey]);

  useEffect(() => {
    pollAbortRef.current = false;
    if (!enabled || !apiBaseUrl) return;
    getMineruStatus(apiBaseUrl)
      .then((snapshot) => {
        setRemoteMaxUploadMb(snapshot.max_upload_mb ?? null);
        setReadinessReady(snapshot.readiness?.ready ?? null);
        setReadinessMessage(snapshot.readiness?.message || snapshot.readiness?.detail || '');
      })
      .catch((caught) => {
        setReadinessReady(false);
        setReadinessMessage(caught instanceof Error ? caught.message : 'Không kiểm tra được dịch vụ.');
      });
    return () => {
      pollAbortRef.current = true;
    };
  }, [apiBaseUrl, enabled]);

  function pickFile(nextFile: File | null) {
    setError('');
    setResult(null);
    if (!nextFile) {
      setFile(null);
      return;
    }
    if (!nextFile.name.toLowerCase().endsWith('.pdf') && nextFile.type !== 'application/pdf') {
      setError('Chỉ nhận file PDF.');
      setFile(null);
      return;
    }
    if (nextFile.size > maxUploadMb * 1024 * 1024) {
      setError(`File vượt quá giới hạn ${maxUploadMb} MB.`);
      setFile(null);
      return;
    }
    setFile(nextFile);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!enabled) {
      setError('Chức năng này hiện chưa mở.');
      return;
    }
    if (!apiBaseUrl) {
      setError('Dịch vụ chuyển đổi chưa sẵn sàng.');
      return;
    }
    if (!file) {
      setError('Chưa chọn file PDF.');
      return;
    }

    setStatus('queued');
    setProgress(3);
    setError('');
    setResult(null);
    setTerminalLines([]);
    setMessage('Đang chuẩn bị file...');

    try {
      const initial = await convertPdfWithMineru(apiBaseUrl, {
        file,
        backend,
        parseMethod,
        language,
        latexDelimitersType,
        formulaEnable,
        tableEnable,
        examFormat,
        startPage,
        endPage,
        serverUrl,
        llmMode,
        llmProvider,
        llmModel,
        llmApiKey: credentials.apiKey,
        llmBaseUrl: credentials.baseUrl,
        llmReasoning: llmProvider === 'openrouter' && runtimeSettings.openrouter_reasoning_enabled,
        router9Only: router9Only || runtimeSettings.router9.only_mode,
      });
      applyJobSnapshot(initial);
      await pollJob(initial.job_id);
    } catch (caught) {
      setStatus('failed');
      setError(caught instanceof Error ? caught.message : 'Không thể chuyển PDF.');
    }
  }

  async function pollJob(jobId: string) {
    while (!pollAbortRef.current) {
      await sleep(1500);
      const snapshot = await getMineruJob(apiBaseUrl, jobId);
      applyJobSnapshot(snapshot);
      if (snapshot.done || snapshot.status === 'completed' || snapshot.status === 'failed') return;
    }
  }

  function applyJobSnapshot(snapshot: MineruJobSnapshot) {
    const nextProgress = typeof snapshot.progress === 'number' ? snapshot.progress : progress;
    setProgress(nextProgress);
    setMessage(snapshot.message || snapshot.stage || snapshot.status);
    setTerminalLines(snapshot.terminal_lines?.slice(-8) ?? []);
    if (snapshot.status === 'completed' || snapshot.done && snapshot.result) {
      setStatus('completed');
      setProgress(100);
      setResult(snapshot.result ?? null);
      return;
    }
    if (snapshot.ok === false || snapshot.status === 'failed') {
      setStatus('failed');
      setError(snapshot.error || snapshot.message || 'MinerU xử lý thất bại.');
      return;
    }
    setStatus(snapshot.status === 'queued' ? 'queued' : 'running');
  }

  async function handleUseMarkdown() {
    if (!markdownArtifact?.download_url && !markdownArtifact?.relative_path) return;
    setImportingText(true);
    setError('');
    try {
      const markdown = await fetchMineruText(apiBaseUrl, markdownArtifact.download_url || markdownArtifact.relative_path || '');
      const normalized = markdown.replace(/\s+/g, ' ').trim().slice(0, MAX_PROBLEM_TEXT_CHARS);
      if (!normalized) throw new Error('Markdown trích xuất đang rỗng.');
      onUseProblemText(normalized);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Không thể lấy Markdown từ MinerU.');
    } finally {
      setImportingText(false);
    }
  }

  return (
    <section className="pdf-word-page">
      <div className="pdf-word-shell">
        <div className="pdf-word-intro">
          <p className="eyebrow">PDF sang Word</p>
          <h2>Chuyển đề toán PDF sang Word</h2>
          <p>
            Tải lên đề PDF để tạo file Word có thể chỉnh sửa, giữ công thức, bảng và cấu trúc câu hỏi trắc nghiệm.
          </p>
        </div>

        <aside className="pdf-word-status-panel" aria-label="Trạng thái MinerU">
          <span className={`pdf-word-status-dot ${readinessReady ? 'ready' : ''}`} aria-hidden="true" />
          <div>
            <strong>{readinessLabel}</strong>
            <span>{formatReadinessMessage(readinessReady, readinessMessage)}</span>
          </div>
        </aside>

        <form className="pdf-word-workspace" onSubmit={handleSubmit}>
          <div className="pdf-word-upload-column">
            <label
              className={`pdf-word-dropzone ${dragActive ? 'drag-active' : ''} ${file ? 'has-file' : ''}`.trim()}
              onDragOver={(event) => {
                event.preventDefault();
                if (!busy) setDragActive(true);
              }}
              onDragLeave={() => setDragActive(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragActive(false);
                if (!busy) pickFile(event.dataTransfer.files?.[0] ?? null);
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                disabled={busy || !enabled}
                onChange={(event) => pickFile(event.target.files?.[0] ?? null)}
              />
              <span className="pdf-word-drop-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="M12 18v-6" /><path d="m9 15 3 3 3-3" /></svg>
              </span>
              <strong>{file ? file.name : 'Kéo thả PDF hoặc bấm để chọn'}</strong>
              <span>{file ? `${formatBytes(file.size)} · sẵn sàng chuyển đổi` : `Tối đa ${maxUploadMb} MB`}</span>
            </label>

            <div className="pdf-word-field-grid">
              <label className="field-label">
                Chế độ xử lý
                <select value={backend} disabled={busy} onChange={(event) => setBackend(event.target.value)}>
                  {backendOptions.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </label>
              <label className="field-label">
                Kiểu đọc PDF
                <select value={parseMethod} disabled={busy} onChange={(event) => setParseMethod(event.target.value)}>
                  <option value="auto">Tự động</option>
                  <option value="ocr">OCR</option>
                  <option value="txt">Ưu tiên chữ có sẵn</option>
                </select>
              </label>
              <label className="field-label">
                Ngôn ngữ
                <select value={language} disabled={busy} onChange={(event) => setLanguage(event.target.value)}>
                  {languageOptions.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </label>
              <label className="field-label">
                Định dạng công thức
                <select value={latexDelimitersType} disabled={busy} onChange={(event) => setLatexDelimitersType(event.target.value)}>
                  <option value="b">Phổ biến trong tài liệu học thuật</option>
                  <option value="a">Phổ biến trong đề thi</option>
                  <option value="all">Tự nhận dạng</option>
                </select>
              </label>
              <label className="field-label">
                Trang bắt đầu
                <input value={startPage} disabled={busy} inputMode="numeric" onChange={(event) => setStartPage(event.target.value)} />
              </label>
              <label className="field-label">
                Trang kết thúc
                <input value={endPage} disabled={busy} inputMode="numeric" placeholder="Để trống" onChange={(event) => setEndPage(event.target.value)} />
              </label>
            </div>

            <div className="pdf-word-option-toggles" aria-label="Tùy chọn đề toán">
              <label className="checkbox-label">
                <input type="checkbox" checked={formulaEnable} disabled={busy} onChange={(event) => setFormulaEnable(event.target.checked)} />
                Nhận diện công thức toán
              </label>
              <label className="checkbox-label">
                <input type="checkbox" checked={tableEnable} disabled={busy} onChange={(event) => setTableEnable(event.target.checked)} />
                Giữ bảng trong đề
              </label>
              <label className="checkbox-label">
                <input type="checkbox" checked={examFormat} disabled={busy} onChange={(event) => setExamFormat(event.target.checked)} />
                Tối ưu cấu trúc đề trắc nghiệm
              </label>
            </div>

            <details className="pdf-word-advanced-options">
              <summary>Tuỳ chọn nâng cao</summary>
              <label className="field-label">
                Nguồn xử lý riêng
                <input
                  value={serverUrl}
                  disabled={busy}
                  placeholder="Để trống để dùng cấu hình mặc định"
                  onChange={(event) => setServerUrl(event.target.value)}
                />
              </label>
            </details>
          </div>

          <div className="pdf-word-options-column">
            <div className="panel-title">Kiểm tra kết quả</div>
            <label className="field-label">
              Mức kiểm tra
              <select value={llmMode} disabled={busy} onChange={(event) => setLlmMode(event.target.value)}>
                <option value="review">Kiểm tra công thức và bảng</option>
                <option value="correct">Tự sửa lỗi rõ ràng</option>
                <option value="off">Không kiểm tra thêm</option>
              </select>
            </label>
            {modelOptions.length === 0 && (
              <button type="button" className="link-button" onClick={onOpenSettings}>Mở cài đặt kiểm tra</button>
            )}
            <button className="submit-button" type="submit" disabled={busy || !file || !enabled || !apiBaseUrl}>
              {busy && <Spinner />}
              {busy ? 'Đang chuyển đổi...' : 'Chuyển PDF sang Word'}
            </button>
            {error && <div className="pdf-word-error" role="alert">{error}</div>}
          </div>
        </form>

        {(busy || result) && (
          <section className="pdf-word-result-strip" aria-live="polite">
            <div className="pdf-word-progress-head">
              <strong>{status === 'completed' ? 'Hoàn tất' : 'Đang xử lý'}</strong>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="pdf-word-progress-track"><span style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} /></div>
            <p>{message}</p>
            {terminalLines.length > 0 && (
              <details className="pdf-word-log-panel">
                <summary>Xem nhật ký xử lý</summary>
                <pre className="pdf-word-terminal">{terminalLines.join('\n')}</pre>
              </details>
            )}
            {result && (
              <ResultDownloads
                baseUrl={apiBaseUrl}
                result={result}
                markdownArtifact={markdownArtifact}
                importingText={importingText}
                onUseMarkdown={handleUseMarkdown}
              />
            )}
          </section>
        )}
      </div>
    </section>
  );
}

function ResultDownloads({
  baseUrl,
  result,
  markdownArtifact,
  importingText,
  onUseMarkdown,
}: {
  baseUrl: string;
  result: MineruResult;
  markdownArtifact?: MineruArtifact;
  importingText: boolean;
  onUseMarkdown: () => void;
}) {
  const artifacts = result.artifacts ?? [];
  const docx = artifacts.find((artifact) => artifact.kind === 'docx') ?? artifacts.find((artifact) => artifact.filename?.toLowerCase().endsWith('.docx'));

  return (
    <div className="pdf-word-downloads">
      {docx && (
        <a className="pdf-word-download-primary" href={mineruUrl(baseUrl, docx.download_url || result.docx_url || '')} target="_blank" rel="noreferrer">
          Tải file Word
        </a>
      )}
      {result.artifacts_zip_url && (
        <a className="pdf-word-download-link" href={mineruUrl(baseUrl, result.artifacts_zip_url)} target="_blank" rel="noreferrer">
          Tải dữ liệu kèm theo
        </a>
      )}
      {markdownArtifact && (
        <button type="button" className="pdf-word-download-link" disabled={importingText} onClick={onUseMarkdown}>
          {importingText ? 'Đang lấy nội dung...' : 'Dùng nội dung để dựng hình'}
        </button>
      )}
      <div className="pdf-word-artifact-list">
        {artifacts.slice(0, 6).map((artifact) => (
          <a key={`${artifact.kind}-${artifact.filename}-${artifact.relative_path}`} href={mineruUrl(baseUrl, artifact.download_url || artifact.relative_path || '')} target="_blank" rel="noreferrer">
            <span>{artifact.kind || 'file'}</span>
            <strong>{artifact.filename || artifact.relative_path}</strong>
            {typeof artifact.size_bytes === 'number' && <em>{formatBytes(artifact.size_bytes)}</em>}
          </a>
        ))}
      </div>
    </div>
  );
}

function normalizePdfLlmProvider(provider: string | undefined) {
  const value = (provider || 'auto').trim().toLowerCase();
  if (value === '9route') return 'router9';
  return ALLOWED_LLM_PROVIDERS.has(value) ? value : 'auto';
}

function providerCredentials(settings: RuntimeSettings, provider: string) {
  if (provider === 'openrouter') return { apiKey: settings.openrouter.api_key, baseUrl: settings.openrouter.base_url };
  if (provider === 'nvidia') return { apiKey: settings.nvidia.api_key, baseUrl: settings.nvidia.base_url };
  if (provider === 'router9') return { apiKey: settings.router9.api_key, baseUrl: settings.router9.base_url };
  const fallbackProvider = normalizePdfLlmProvider(settings.default_provider);
  if (fallbackProvider !== 'auto') return providerCredentials(settings, fallbackProvider);
  return { apiKey: '', baseUrl: '' };
}

function providerDefaultModel(settings: RuntimeSettings, provider: string) {
  if (provider === 'openrouter') return settings.openrouter.model;
  if (provider === 'nvidia') return settings.nvidia.model;
  if (provider === 'router9') return settings.router9.model;
  return '';
}

function formatReadinessMessage(ready: boolean | null, message: string) {
  if (ready) return 'Bạn có thể tải file PDF lên để chuyển đổi.';
  if (!message) return 'Vui lòng thử lại sau ít phút.';
  const lower = message.toLowerCase();
  if (lower.includes('cors') || lower.includes('api') || lower.includes('env') || lower.includes('mineru') || lower.includes('cli')) {
    return 'Dịch vụ xử lý tài liệu chưa sẵn sàng.';
  }
  return message;
}

function formatBytes(value: number) {
  if (!Number.isFinite(value) || value <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const index = Math.min(units.length - 1, Math.floor(Math.log(value) / Math.log(1024)));
  return `${(value / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function Spinner() {
  return (
    <svg className="spinner" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
