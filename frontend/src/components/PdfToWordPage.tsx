import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';

import { convertPdfWithMineru, getMineruJob, getMineruStatus, mineruUrl, normalizeMineruBaseUrl, type MineruJobSnapshot, type MineruResult } from '../api/mineru';
import type { ModelOption } from './ProblemInput';
import type { RuntimeSettings } from '../types/settings';

type UploadState = 'idle' | 'queued' | 'running' | 'completed' | 'failed';

interface PdfToWordPageProps {
  apiBaseUrl: string;
  modelOptions: ModelOption[];
  runtimeSettings: RuntimeSettings;
  router9Only: boolean;
  onOpenSettings: () => void;
}

const MAX_LOCAL_UPLOAD_MB = 128;
const MINERU_API_BASE_URL_STORAGE_KEY = 'pdfWordMineruApiBaseUrl';
const ALLOWED_LLM_PROVIDERS = new Set(['auto', 'openrouter', 'router9', 'nvidia']);
const backendOptions = [
  { value: 'auto', label: 'Tự động' },
  { value: 'pipeline', label: 'Ổn định' },
  { value: 'hybrid-auto-engine', label: 'Cân bằng' },
  { value: 'vlm-auto-engine', label: 'Chính xác cao' },
  { value: 'hybrid-http-client', label: 'Cân bằng từ xa' },
  { value: 'vlm-http-client', label: 'Chính xác cao từ xa' },
];
const guideStrokeIcon = {
  viewBox: '0 0 24 24',
  width: 20,
  height: 20,
  fill: 'none' as const,
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true as const,
};

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
  apiBaseUrl,
  modelOptions,
  runtimeSettings,
  router9Only,
  onOpenSettings,
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
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState('');
  const [remoteMaxUploadMb, setRemoteMaxUploadMb] = useState<number | null>(null);
  const [readinessMessage, setReadinessMessage] = useState('');
  const [readinessReady, setReadinessReady] = useState<boolean | null>(null);
  const [guideOpen, setGuideOpen] = useState(false);
  const [backend, setBackend] = useState('auto');
  const [parseMethod, setParseMethod] = useState('auto');
  const [language, setLanguage] = useState('ch');
  const [latexDelimitersType, setLatexDelimitersType] = useState('b');
  const [formulaEnable, setFormulaEnable] = useState(true);
  const [tableEnable, setTableEnable] = useState(true);
  const [llmMode, setLlmMode] = useState('off');
  const [examFormat, setExamFormat] = useState(false);
  const [startPage, setStartPage] = useState('1');
  const [endPage, setEndPage] = useState('');
  const [mineruApiBaseUrl, setMineruApiBaseUrl] = useState(() => loadMineruApiBaseUrl(apiBaseUrl));
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollAbortRef = useRef(false);

  const selectedModel = modelOptions.find((option) => option.key === selectedModelKey) ?? modelOptions[0];
  const llmProvider = normalizePdfLlmProvider(router9Only ? 'router9' : selectedModel?.provider);
  const llmModel = selectedModel?.modelId ?? providerDefaultModel(runtimeSettings, llmProvider);
  const credentials = providerCredentials(runtimeSettings, llmProvider);
  const activeApiBaseUrl = normalizeMineruBaseUrl(mineruApiBaseUrl) || apiBaseUrl;
  const maxUploadMb = remoteMaxUploadMb ?? Number(import.meta.env.VITE_PDF_WORD_MAX_UPLOAD_MB || MAX_LOCAL_UPLOAD_MB);
  const busy = status === 'queued' || status === 'running';

  const readinessLabel = useMemo(() => {
    if (!activeApiBaseUrl) return 'Cần link xử lý';
    if (readinessReady === null) return 'Đang kiểm tra';
    return readinessReady ? 'Sẵn sàng xử lý' : 'Chưa sẵn sàng';
  }, [activeApiBaseUrl, readinessReady]);

  useEffect(() => {
    if (!modelOptions.some((option) => option.key === selectedModelKey)) {
      setSelectedModelKey(modelOptions[0]?.key ?? 'provider:auto');
    }
  }, [modelOptions, selectedModelKey]);

  useEffect(() => {
    const saved = window.localStorage.getItem(MINERU_API_BASE_URL_STORAGE_KEY);
    if (!saved) setMineruApiBaseUrl(apiBaseUrl);
  }, [apiBaseUrl]);

  useEffect(() => {
    if (!file) {
      setPdfPreviewUrl('');
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    setPdfPreviewUrl(objectUrl);
    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [file]);

  useEffect(() => {
    pollAbortRef.current = false;
    setReadinessReady(null);
    setReadinessMessage('');
    if (!activeApiBaseUrl) return;
    getMineruStatus(activeApiBaseUrl)
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
  }, [activeApiBaseUrl]);

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
    if (!activeApiBaseUrl) {
      setError('Dán link xử lý MinerU trước khi chuyển đổi.');
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
      const initial = await convertPdfWithMineru(activeApiBaseUrl, {
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
        serverUrl: '',
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
      const snapshot = await getMineruJob(activeApiBaseUrl, jobId);
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
          <button type="button" className="pdf-word-guide-button" aria-label="Hướng dẫn chạy MinerU Colab" onClick={() => setGuideOpen(true)}>
            <svg {...guideStrokeIcon}>
              <path d="M9.25 14.75c-.95-.76-1.5-1.9-1.5-3.2A4.25 4.25 0 0 1 12 7.25a4.25 4.25 0 0 1 4.25 4.3c0 1.3-.55 2.44-1.5 3.2-.55.44-.9 1.03-.98 1.75h-3.54c-.08-.72-.43-1.31-.98-1.75Z" />
              <path d="M10 19h4" />
              <path d="M10.75 21h2.5" />
              <path d="M12 3v1.5" />
              <path d="m5.75 5.75 1.05 1.05" />
              <path d="m18.25 5.75-1.05 1.05" />
            </svg>
          </button>
        </aside>
        {guideOpen && <MineruColabGuide onClose={() => setGuideOpen(false)} />}

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
                disabled={busy}
                onChange={(event) => pickFile(event.target.files?.[0] ?? null)}
              />
              <span className="pdf-word-drop-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="M12 18v-6" /><path d="m9 15 3 3 3-3" /></svg>
              </span>
              <strong>{file ? file.name : 'Kéo thả PDF hoặc bấm để chọn'}</strong>
              <span>{file ? `${formatBytes(file.size)} · sẵn sàng chuyển đổi` : `Tối đa ${maxUploadMb} MB`}</span>
            </label>

            {file && pdfPreviewUrl && (
              <PdfOriginalPreview fileName={file.name} url={pdfPreviewUrl} />
            )}

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

            <details className="pdf-word-advanced-options" open={!activeApiBaseUrl}>
              <summary>Tuỳ chọn nâng cao</summary>
              <label className="field-label">
                Link xử lý MinerU
                <input
                  value={mineruApiBaseUrl}
                  disabled={busy}
                  placeholder="https://...trycloudflare.com"
                  onChange={(event) => updateMineruApiBaseUrl(event.target.value, setMineruApiBaseUrl)}
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
            <button className="submit-button" type="submit" disabled={busy || !file || !activeApiBaseUrl}>
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
              <ResultDownloads baseUrl={activeApiBaseUrl} result={result} />
            )}
          </section>
        )}
      </div>
    </section>
  );
}

function MineruColabGuide({ onClose }: { onClose: () => void }) {
  return (
    <div className="pdf-word-guide-backdrop" role="dialog" aria-modal="true" aria-labelledby="mineru-colab-guide-title" onMouseDown={onClose}>
      <div className="pdf-word-guide-modal" onMouseDown={(event) => event.stopPropagation()}>
        <div className="pdf-word-guide-header">
          <div>
            <p className="eyebrow">MinerU Colab / Kaggle</p>
            <h3 id="mineru-colab-guide-title">Hướng dẫn lấy link xử lý PDF</h3>
          </div>
          <button type="button" className="pdf-word-guide-close" aria-label="Đóng hướng dẫn" onClick={onClose}>
            <svg {...guideStrokeIcon} strokeWidth={2.2}>
              <path d="M18 6 6 18" />
              <path d="M6 6l12 12" />
            </svg>
          </button>
        </div>

        <ol className="pdf-word-guide-steps">
          <li className="pdf-word-guide-inline-step">
            <strong>Mở notebook Colab.</strong>
            <a href="https://colab.research.google.com/drive/1KC1hHv9eYoRjwKkrwXO-uHrAzEAw8ATY?usp=sharing" target="_blank" rel="noreferrer">
              Mở MinerU Colab
            </a>
          </li>
          <li>
            <strong>Bật GPU đúng cách.</strong>
            Vào <span>Runtime → Change runtime type</span>, chọn <span>T4 GPU</span> hoặc GPU đang có, rồi bấm <span>Save</span>.
          </li>
          <li>
            <strong>Chạy lần lượt các cell từ trên xuống.</strong>
            Nếu Colab hỏi quyền Drive hoặc cài package, chấp nhận và đợi đến khi server khởi động xong. Không đóng tab trong lúc xử lý.
          </li>
          <li>
            <strong>Lấy link API Cloudflare.</strong>
            Sau cell tunnel chạy xong, copy link dạng <span>https://...trycloudflare.com</span>. Mở thử link đó trên trình duyệt: nếu thấy web PDF sang Word hoặc gọi được <span>/api/status</span> là link đúng.
          </li>
          <li>
            <strong>Dán link vào ô “Link xử lý MinerU”.</strong>
            Dán nguyên link Cloudflare vào ô trong trang này. Hệ thống sẽ dùng link đó thay cho URL trong <span>.env</span> và tự lưu lại cho lần refresh sau.
          </li>
          <li>
            <strong>Khi đổi runtime hoặc chạy lại notebook.</strong>
            Link Cloudflare có thể đổi. Nếu xử lý báo lỗi hoặc mất kết nối, copy link mới từ Colab rồi dán lại vào ô “Link xử lý MinerU”.
          </li>
          <li>
            <strong>Tắt GPU khi dùng xong.</strong>
            Trong Colab chọn <span>Runtime → Disconnect and delete runtime</span>. Nếu dùng Kaggle, bấm <span>Stop session</span> hoặc tắt notebook session để tránh giữ GPU lãng phí.
          </li>
        </ol>

        <div className="pdf-word-guide-note">
          Không paste link này vào “server_url” của MinerU CLI. Trang này dùng nó làm base API cho các endpoint <span>/api/status</span>, <span>/api/convert</span> và <span>/api/jobs</span>.
        </div>
      </div>
    </div>
  );
}

function ResultDownloads({ baseUrl, result }: { baseUrl: string; result: MineruResult }) {
  const artifacts = result.artifacts ?? [];
  const docx = artifacts.find((artifact) => artifact.kind === 'docx') ?? artifacts.find((artifact) => artifact.filename?.toLowerCase().endsWith('.docx'));

  return (
    <div className="pdf-word-downloads">
      {docx && (
        <a className="pdf-word-download-primary" href={mineruUrl(baseUrl, docx.download_url || result.docx_url || '')} target="_blank" rel="noreferrer">
          Tải file Word
        </a>
      )}
    </div>
  );
}

function PdfOriginalPreview({ fileName, url }: { fileName: string; url: string }) {
  return (
    <div className="pdf-word-preview-panel">
      <div className="pdf-word-preview-head">
        <strong>Bản PDF đã tải lên</strong>
        <a href={url} target="_blank" rel="noreferrer">Mở tab mới</a>
      </div>
      <iframe src={url} title={`Xem trước ${fileName}`} />
    </div>
  );
}

function loadMineruApiBaseUrl(fallback: string) {
  return window.localStorage.getItem(MINERU_API_BASE_URL_STORAGE_KEY) || fallback;
}

function updateMineruApiBaseUrl(value: string, setValue: (value: string) => void) {
  setValue(value);
  const normalized = normalizeMineruBaseUrl(value);
  if (normalized) {
    window.localStorage.setItem(MINERU_API_BASE_URL_STORAGE_KEY, normalized);
  } else {
    window.localStorage.removeItem(MINERU_API_BASE_URL_STORAGE_KEY);
  }
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
