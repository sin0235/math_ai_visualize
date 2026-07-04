import { FormEvent, memo, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import {
  convertPdfWithMineru,
  getDefaultMineruPageConfig,
  getMineruDocxPreview,
  getMineruJob,
  getMineruLlmProviders,
  getMineruPageConfig,
  getMineruStatus,
  mineruUrl,
  normalizeMineruBaseUrl,
  type MineruArtifact,
  type MineruJobSnapshot,
  type MineruPageConfig,
  type MineruProviderDefaults,
  type MineruResult,
  type MineruSelectOption,
} from '../api/mineru';

type UploadState = 'idle' | 'queued' | 'running' | 'completed' | 'failed';
type PreviewState = { title: string; kind: string; url: string; html?: string; loading?: boolean; error?: string } | null;

interface PdfToWordPageProps {
  apiBaseUrl: string;
}

const MAX_LOCAL_UPLOAD_MB = 128;
const MINERU_API_BASE_URL_STORAGE_KEY = 'pdfWordMineruApiBaseUrl';
const ALLOWED_LLM_PROVIDERS = new Set(['auto', 'openrouter', 'router9', 'nvidia']);
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

export function PdfToWordPage({ apiBaseUrl }: PdfToWordPageProps) {
  const [pageConfig, setPageConfig] = useState<MineruPageConfig>(() => getDefaultMineruPageConfig());
  const [providerDefaults, setProviderDefaults] = useState<MineruProviderDefaults>({});
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
  const [backend, setBackend] = useState(pageConfig.values.backend);
  const [parseMethod, setParseMethod] = useState(pageConfig.values.parseMethod);
  const [language, setLanguage] = useState(pageConfig.values.language);
  const [latexDelimitersType, setLatexDelimitersType] = useState(pageConfig.values.latexDelimitersType);
  const [formulaEnable, setFormulaEnable] = useState(pageConfig.values.formulaEnable);
  const [tableEnable, setTableEnable] = useState(pageConfig.values.tableEnable);
  const [forceOcr, setForceOcr] = useState(false);
  const [llmMode, setLlmMode] = useState(pageConfig.values.llmMode);
  const [, setLlmProvider] = useState(pageConfig.values.llmProvider);
  const [llmModel, setLlmModel] = useState(pageConfig.values.llmModel);
  const [, setLlmReasoning] = useState(pageConfig.values.llmReasoning);
  const [, setRouter9Only] = useState(pageConfig.values.router9Only);
  const [serverUrl, setServerUrl] = useState(pageConfig.values.serverUrl);
  const [examFormat, setExamFormat] = useState(pageConfig.values.examFormat);
  const [startPage, setStartPage] = useState('1');
  const [endPage, setEndPage] = useState('');
  const [mineruApiBaseUrl, setMineruApiBaseUrl] = useState(() => loadMineruApiBaseUrl(apiBaseUrl));
  const progressFillRef = useRef<HTMLSpanElement>(null);
  const pollAbortRef = useRef(false);

  const activeApiBaseUrl = normalizeMineruBaseUrl(mineruApiBaseUrl) || apiBaseUrl;
  const maxUploadMb = remoteMaxUploadMb ?? Number(import.meta.env.VITE_PDF_WORD_MAX_UPLOAD_MB || MAX_LOCAL_UPLOAD_MB);
  const busy = status === 'queued' || status === 'running';
  const selectedProviderReady = providerReady(providerDefaults, 'nvidia');
  const showLlmReviewMode = selectedProviderReady;
  const showServerUrl = backend === 'hybrid-http-client' || backend === 'vlm-http-client';
  const effectiveLlmMode = selectedProviderReady ? llmMode : 'off';

  const readinessLabel = useMemo(() => {
    if (!activeApiBaseUrl) return 'Cần link xử lý';
    if (readinessReady === null) return 'Đang kiểm tra';
    return readinessReady ? 'MinerU sẵn sàng' : 'MinerU chưa sẵn sàng';
  }, [activeApiBaseUrl, readinessReady]);

  useEffect(() => {
    const clamped = Math.max(0, Math.min(100, progress));
    progressFillRef.current?.style.setProperty('--pdf-word-progress', `${clamped}%`);
  }, [progress, status, result]);

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
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  useEffect(() => {
    pollAbortRef.current = false;
    setReadinessReady(null);
    setReadinessMessage('');
    if (!activeApiBaseUrl) return;

    getMineruPageConfig(activeApiBaseUrl)
      .then((config) => {
        setPageConfig(config);
        applyPageConfigValues(config);
      })
      .catch(() => {
        const config = getDefaultMineruPageConfig();
        setPageConfig(config);
        applyPageConfigValues(config);
      });

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

    getMineruLlmProviders(activeApiBaseUrl)
      .then((snapshot) => {
        const providers = snapshot.providers ?? {};
        setProviderDefaults(providers);
        const nvidiaReady = providers.nvidia?.api_key_configured === true;
        setRouter9Only((current) => current || providers.router9?.only_mode === true);
        setLlmProvider('nvidia');
        setLlmModel((currentModel) => modelForProvider('nvidia', providers) || currentModel || 'google/gemma-3-27b-it');
        if (!nvidiaReady) setLlmMode('off');
      })
      .catch(() => {
        setProviderDefaults({});
        setLlmMode('off');
      });

    return () => {
      pollAbortRef.current = true;
    };
  }, [activeApiBaseUrl]);

  function applyPageConfigValues(config: MineruPageConfig) {
    setBackend(config.values.backend);
    setParseMethod(config.values.parseMethod);
    setLanguage(config.values.language);
    setLatexDelimitersType(config.values.latexDelimitersType);
    setFormulaEnable(config.values.formulaEnable);
    setTableEnable(config.values.tableEnable);
    setExamFormat(config.values.examFormat);
    setLlmMode(config.values.llmMode);
    setLlmProvider('nvidia');
    setLlmModel(config.values.llmModel || 'google/gemma-3-27b-it');
    setLlmReasoning(config.values.llmReasoning);
    setRouter9Only(config.values.router9Only);
    setServerUrl(config.values.serverUrl);
  }

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
        parseMethod: forceOcr ? 'ocr' : parseMethod,
        language,
        latexDelimitersType,
        formulaEnable,
        tableEnable,
        examFormat,
        startPage,
        endPage,
        serverUrl: showServerUrl ? serverUrl : '',
        llmMode: effectiveLlmMode,
        llmProvider: 'nvidia',
        llmModel: llmModel || 'google/gemma-3-27b-it',
        llmApiKey: '',
        llmBaseUrl: '',
        llmReasoning: false,
        router9Only: false,
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
    setTerminalLines(snapshot.terminal_lines?.slice(-400) ?? []);
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
          <h2>MinerU PDF to Word</h2>
          <p>Gọi trực tiếp API MinerU đang chọn. Config form lấy từ trang gốc MinerU khi endpoint phản hồi.</p>
        </div>

        <aside className="pdf-word-status-panel" aria-label="Trạng thái MinerU">
          <span className={`pdf-word-status-dot ${readinessReady ? 'ready' : ''}`} aria-hidden="true" />
          <div>
            <strong>{readinessLabel}</strong>
            <span>{readinessMessage || 'Chưa có message từ MinerU.'}</span>
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
              <input type="file" accept=".pdf,application/pdf" disabled={busy} onChange={(event) => pickFile(event.target.files?.[0] ?? null)} />
              <span className="pdf-word-drop-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="M12 18v-6" /><path d="m9 15 3 3 3-3" /></svg>
              </span>
              <strong>{file ? file.name : 'Chọn file PDF'}</strong>
              <span>{file ? `${formatBytes(file.size)} · ready` : `Max ${maxUploadMb} MB`}</span>
            </label>

            {file && pdfPreviewUrl && <PdfOriginalPreview fileName={file.name} url={pdfPreviewUrl} />}

            <div className="pdf-word-field-grid">
              <OptionSelect label="Backend" value={backend} disabled={busy} options={pageConfig.options.backends} onChange={setBackend} />
              <OptionSelect label="Phương thức" value={parseMethod} disabled={busy || forceOcr} options={pageConfig.options.parseMethods} onChange={setParseMethod} />
              <OptionSelect label="OCR language" value={language} disabled={busy} options={pageConfig.options.languages} onChange={setLanguage} />
              <OptionSelect label="LaTeX delimiter" value={latexDelimitersType} disabled={busy} options={pageConfig.options.latexDelimiters} onChange={setLatexDelimitersType} />
              <label className="field-label">
                Từ trang
                <input value={startPage} disabled={busy} inputMode="numeric" onChange={(event) => setStartPage(event.target.value)} />
              </label>
              <label className="field-label">
                Đến trang
                <input value={endPage} disabled={busy} inputMode="numeric" placeholder="Tất cả" onChange={(event) => setEndPage(event.target.value)} />
              </label>
            </div>

            <div className="pdf-word-option-toggles" aria-label="Tùy chọn MinerU">
              <CheckboxLabel checked={formulaEnable} disabled={busy} onChange={setFormulaEnable}>Nhận diện công thức</CheckboxLabel>
              <CheckboxLabel checked={tableEnable} disabled={busy} onChange={setTableEnable}>Nhận diện bảng</CheckboxLabel>
              <CheckboxLabel checked={forceOcr} disabled={busy} onChange={setForceOcr}>Ép OCR</CheckboxLabel>
              <CheckboxLabel checked={examFormat} disabled={busy} onChange={setExamFormat}>Format đề thi trắc nghiệm</CheckboxLabel>
            </div>

            <div className="warning-box">
              PDF upload tới MinerU endpoint đang chọn. Không gửi tài liệu nhạy cảm vào endpoint không kiểm soát.
            </div>

            <details className="pdf-word-advanced-options" open={!activeApiBaseUrl}>
              <summary>Endpoint</summary>
              <label className="field-label">
                Link xử lý MinerU
                <input value={mineruApiBaseUrl} disabled={busy} placeholder="https://...trycloudflare.com" onChange={(event) => updateMineruApiBaseUrl(event.target.value, setMineruApiBaseUrl)} />
              </label>
              {showServerUrl && (
                <label className="field-label">
                  OpenAI-compatible URL
                  <input value={serverUrl} disabled={busy} placeholder="Chỉ dùng với http-client backend" onChange={(event) => setServerUrl(event.target.value)} />
                </label>
              )}
            </details>
          </div>

          <div className="pdf-word-options-column">
            <div className="panel-title">LLM review</div>
            {showLlmReviewMode && <OptionSelect label="LLM review" value={llmMode} disabled={busy} options={pageConfig.options.llmModes} onChange={setLlmMode} />}
            <div className={`pdf-word-provider-status ${selectedProviderReady ? 'ready' : 'blocked'}`}>
              {providerStatusText(providerDefaults, llmModel)}
            </div>
            <button className="submit-button" type="submit" disabled={busy || !file || !activeApiBaseUrl}>
              {busy && <Spinner />}
              {busy ? 'Đang chuyển đổi...' : 'Chuyển sang Word'}
            </button>
            {error && <div className="pdf-word-error" role="alert">{error}</div>}
          </div>
        </form>

        {(busy || result) && (
          <section className="pdf-word-result-strip" aria-live="polite">
            <div className="pdf-word-progress-head">
              <strong>{status === 'completed' ? 'Completed' : 'Running'}</strong>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="pdf-word-progress-track"><span ref={progressFillRef} className="pdf-word-progress-fill" /></div>
            <p>{message}</p>
            {terminalLines.length > 0 && (
              <details className="pdf-word-log-panel">
                <summary>Terminal realtime</summary>
                <pre className="pdf-word-terminal">{terminalLines.join('\n')}</pre>
              </details>
            )}
            {result && <ResultDownloads baseUrl={activeApiBaseUrl} result={result} />}
          </section>
        )}
      </div>
    </section>
  );
}

function OptionSelect({ label, value, disabled, options, onChange }: { label: string; value: string; disabled?: boolean; options: MineruSelectOption[]; onChange: (value: string) => void }) {
  return (
    <label className="field-label">
      {label}
      <select value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </label>
  );
}

function CheckboxLabel({ checked, disabled, onChange, children }: { checked: boolean; disabled?: boolean; onChange: (checked: boolean) => void; children: ReactNode }) {
  return (
    <label className="checkbox-label">
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
      {children}
    </label>
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
            <a href="https://colab.research.google.com/github/sin0235/MinerU/blob/main/colab_pdf_to_word_cloudflare.ipynb" target="_blank" rel="noreferrer noopener">Mở MinerU Colab</a>
          </li>
          <li><strong>Bật GPU đúng cách.</strong> Vào <span>Runtime → Change runtime type</span>, chọn <span>T4 GPU</span>, rồi bấm <span>Save</span>.</li>
          <li><strong>Chạy cell từ trên xuống.</strong> Đợi server khởi động xong. Không đóng tab trong lúc xử lý.</li>
          <li><strong>Lấy Cloudflare URL.</strong> Copy link dạng <span>https://...trycloudflare.com</span>. Kiểm tra được <span>/api/status</span> là đúng.</li>
          <li><strong>Dán link vào ô “Link xử lý MinerU”.</strong> Link được lưu localStorage cho lần refresh sau.</li>
          <li><strong>Khi runtime đổi.</strong> Cloudflare URL có thể đổi. Copy URL mới và dán lại.</li>
        </ol>

        <div className="pdf-word-guide-note">
          Ô “Link xử lý MinerU” là base API cho <span>/api/status</span>, <span>/api/convert</span>, <span>/api/jobs</span>. Ô <span>OpenAI-compatible URL</span> chỉ dùng với backend http-client.
        </div>
      </div>
    </div>
  );
}

function ResultDownloads({ baseUrl, result }: { baseUrl: string; result: MineruResult }) {
  const [preview, setPreview] = useState<PreviewState>(null);
  const artifacts = result.artifacts ?? [];
  const docx = artifacts.find((artifact) => artifact.kind === 'docx') ?? artifacts.find((artifact) => artifact.filename?.toLowerCase().endsWith('.docx'));
  const previewArtifacts = artifacts.filter((artifact) => artifact.preview_url).slice(0, 6);
  const docxHref = mineruUrl(baseUrl, docx?.download_url || result.docx_url || '');
  const zipHref = mineruUrl(baseUrl, result.artifacts_zip_url || '');

  async function openPreview(artifact: MineruArtifact) {
    const url = mineruUrl(baseUrl, artifact.preview_url || '');
    const title = artifact.filename || artifact.label || 'Preview';
    const kind = artifact.preview_kind || '';
    if (kind === 'docx') {
      setPreview({ title, kind, url, loading: true });
      try {
        const data = await getMineruDocxPreview(baseUrl, artifact.preview_url || '');
        setPreview({ title: data.filename || title, kind, url, html: data.html });
      } catch (caught) {
        setPreview({ title, kind, url, error: caught instanceof Error ? caught.message : 'Không tải được preview DOCX.' });
      }
      return;
    }
    setPreview({ title, kind, url });
  }

  return (
    <div className="pdf-word-result-detail">
      <div className="pdf-word-result-summary">
        <SummaryCell label="File" value={result.download_name || result.original_filename || docx?.filename || 'output.docx'} />
        <SummaryCell label="Backend" value={result.backend_used || '-'} />
        <SummaryCell label="Thời gian" value={result.elapsed_seconds == null ? '-' : `${result.elapsed_seconds.toFixed(2)}s`} />
        <SummaryCell label="Số trang" value={result.page_count == null ? '-' : String(result.page_count)} />
      </div>

      <div className="pdf-word-downloads">
        {(docx || result.docx_url) && <a className="pdf-word-download-primary" href={docxHref} target="_blank" rel="noreferrer">Tải DOCX</a>}
        {result.artifacts_zip_url && <a className="pdf-word-download-link" href={zipHref} target="_blank" rel="noreferrer">Tải ZIP artifact</a>}
      </div>

      {artifacts.length > 0 && (
        <div className="pdf-word-artifact-list">
          {artifacts.map((artifact) => (
            <a key={`${artifact.kind}-${artifact.relative_path}-${artifact.filename}`} href={mineruUrl(baseUrl, artifact.download_url || '')} target="_blank" rel="noreferrer">
              <span>{artifact.kind || 'file'}</span>
              <strong>{artifact.filename || artifact.label || artifact.relative_path}</strong>
              <em>{formatBytes(artifact.size_bytes ?? 0)}</em>
            </a>
          ))}
        </div>
      )}

      {previewArtifacts.length > 0 && (
        <div className="pdf-word-preview-actions">
          {previewArtifacts.map((artifact) => (
            <button key={`${artifact.preview_kind}-${artifact.preview_url}`} className="pdf-word-download-link" type="button" onClick={() => openPreview(artifact)}>
              Preview {artifact.preview_kind?.toUpperCase() || artifact.kind || 'file'}
            </button>
          ))}
        </div>
      )}

      {preview && <ArtifactPreview preview={preview} onClose={() => setPreview(null)} />}

      {(result.warnings ?? []).length > 0 && (
        <div className="pdf-word-warning-list">
          {result.warnings?.map((warning) => <div key={warning}>{warning}</div>)}
        </div>
      )}
    </div>
  );
}

function SummaryCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ArtifactPreview({ preview, onClose }: { preview: Exclude<PreviewState, null>; onClose: () => void }) {
  const srcDoc = preview.html ? `<!doctype html><meta charset="utf-8"><style>body{font-family:Arial,sans-serif;line-height:1.5;padding:16px;color:#111827}table{border-collapse:collapse;width:100%}td,th{border:1px solid #d1d5db;padding:4px 6px}</style>${preview.html}` : '';
  return (
    <div className="pdf-word-artifact-preview">
      <div className="pdf-word-preview-head">
        <strong>{preview.title}</strong>
        <button className="pdf-word-preview-close" type="button" onClick={onClose}>Đóng</button>
      </div>
      {preview.loading && <div className="pdf-word-preview-note">Đang tải preview...</div>}
      {preview.error && <div className="pdf-word-error" role="alert">{preview.error}</div>}
      {!preview.loading && !preview.error && preview.kind === 'docx' && <iframe title={preview.title} sandbox="" srcDoc={srcDoc} />}
      {!preview.loading && !preview.error && preview.kind !== 'docx' && <iframe title={preview.title} src={preview.url} />}
    </div>
  );
}

const PdfOriginalPreview = memo(function PdfOriginalPreview({ fileName, url }: { fileName: string; url: string }) {
  return (
    <div className="pdf-word-preview-panel">
      <div className="pdf-word-preview-head">
        <strong>Preview PDF upload</strong>
        <a href={url} target="_blank" rel="noreferrer">Mở tab mới</a>
      </div>
      <iframe src={url} title={`Xem trước ${fileName}`} />
    </div>
  );
});

function loadMineruApiBaseUrl(fallback: string) {
  return window.localStorage.getItem(MINERU_API_BASE_URL_STORAGE_KEY) || fallback;
}

function updateMineruApiBaseUrl(value: string, setValue: (value: string) => void) {
  setValue(value);
  const normalized = normalizeMineruBaseUrl(value);
  if (normalized) window.localStorage.setItem(MINERU_API_BASE_URL_STORAGE_KEY, normalized);
  else window.localStorage.removeItem(MINERU_API_BASE_URL_STORAGE_KEY);
}

function normalizePdfLlmProvider(provider: string | undefined) {
  const value = (provider || 'auto').trim().toLowerCase();
  if (value === '9route' || value === '9router') return 'router9';
  return ALLOWED_LLM_PROVIDERS.has(value) ? value : 'auto';
}

function providerReady(defaults: MineruProviderDefaults, provider: string): boolean {
  if (provider === 'auto') return providerReady(defaults, 'nvidia') || providerReady(defaults, 'openrouter') || providerReady(defaults, 'router9');
  return defaults[provider as 'nvidia' | 'openrouter' | 'router9']?.api_key_configured === true;
}

function modelForProvider(provider: string, defaults: MineruProviderDefaults) {
  const normalized = normalizePdfLlmProvider(provider);
  if (normalized === 'auto') return '';
  const model = defaults[normalized as 'nvidia' | 'openrouter' | 'router9']?.model || '';
  if (!model) return '';
  if (normalized === 'openrouter' && !model.startsWith('openrouter/')) return `openrouter/${model}`;
  if (normalized === 'router9' && !model.startsWith('router9/') && !model.startsWith('9route/')) return `router9/${model}`;
  return model;
}

function providerStatusText(defaults: MineruProviderDefaults, model: string) {
  const defaultsForProvider = defaults.nvidia;
  const envName = defaultsForProvider?.api_key_env || 'NVIDIA_API_KEY';
  if (!defaultsForProvider?.api_key_configured) return `Chưa cấu hình ${envName} trong notebook MinerU. LLM review đang tắt.`;
  const base = defaultsForProvider.base_url ? ` · ${defaultsForProvider.base_url}` : '';
  return `API key sẵn sàng cho NVIDIA${model ? ` · ${model}` : ''}${base}`;
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