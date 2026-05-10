import { Fragment, useEffect, useId, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { analyzeFunction, analyzeFunctionImage, type AnalyzeOptions, type AnalyzeResponse } from '../api/client';
import { GeoGebraView } from './GeoGebraView';
import { KatexSpan, sympyToLatex } from './KatexSpan';
import type { MathScene } from '../types/scene';

interface FunctionAnalyzerPanelProps {
  initialExpression?: string;
  onOpenGuide?: () => void;
}

const EXAMPLE_GROUPS = [
  {
    label: 'Đa thức',
    items: [
      { label: 'Bậc 2', value: 'x^2 - 4*x + 3' },
      { label: 'Bậc 3', value: 'x^3 - 3*x + 2' },
      { label: 'Bậc 4', value: 'x^4 - 8*x^2' },
    ],
  },
  {
    label: 'Hàm đặc biệt',
    items: [
      { label: 'Phân thức', value: '(x^2 - 1)/(x - 2)' },
      { label: 'Căn', value: 'sqrt(x^2 + 1)' },
      { label: 'Mũ', value: 'exp(x)' },
      { label: 'Logarit', value: 'log(x)' },
    ],
  },
];

const TRANSFORMS = [
  { value: 'vertical_shift', label: 'f(x) + a' },
  { value: 'horizontal_shift', label: 'f(x + a)' },
  { value: 'vertical_scale', label: 'a·f(x)' },
  { value: 'horizontal_scale', label: 'f(a·x)' },
  { value: 'reflect_x', label: '-f(x)' },
  { value: 'reflect_y', label: 'f(-x)' },
];

const TRANSFORM_LABEL_TEX: Record<string, string> = {
  vertical_shift: 'g(x)=f(x)+a',
  horizontal_shift: 'g(x)=f(x+a)',
  vertical_scale: 'g(x)=a f(x)',
  horizontal_scale: 'g(x)=f(a x)',
  reflect_x: 'g(x)=-f(x)',
  reflect_y: 'g(x)=f(-x)',
};

export function FunctionAnalyzerPanel({ initialExpression = '', onOpenGuide }: FunctionAnalyzerPanelProps) {
  const [expression, setExpression] = useState(initialExpression);
  const [loading, setLoading] = useState(false);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [intervalA, setIntervalA] = useState(-2);
  const [intervalB, setIntervalB] = useState(2);
  const [enableInterval, setEnableInterval] = useState(false);
  const [lineK, setLineK] = useState(1);
  const [lineB, setLineB] = useState(0);
  const [enableLine, setEnableLine] = useState(false);
  const [enableTransform, setEnableTransform] = useState(false);
  const [transformType, setTransformType] = useState('vertical_shift');
  const [transformValue, setTransformValue] = useState(1);
  const [isAnimatingTransform, setIsAnimatingTransform] = useState(false);
  const [showAdvancedControls, setShowAdvancedControls] = useState(true);
  const [isDraggingImage, setIsDraggingImage] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const analyzeRequestRef = useRef(0);
  const sliderDebounceRef = useRef<number | null>(null);
  const animationRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (sliderDebounceRef.current !== null) window.clearTimeout(sliderDebounceRef.current);
      if (animationRef.current !== null) window.clearInterval(animationRef.current);
    };
  }, []);

  useEffect(() => {
    if (!isAnimatingTransform) {
      if (animationRef.current !== null) window.clearInterval(animationRef.current);
      animationRef.current = null;
      return;
    }
    animationRef.current = window.setInterval(() => {
      setTransformValue((current) => {
        const next = current >= 3 ? -3 : Number((current + 0.1).toFixed(2));
        scheduleToolAnalyze({ transformValue: next, enableTransform: true });
        return next;
      });
    }, 160);
    return () => {
      if (animationRef.current !== null) window.clearInterval(animationRef.current);
      animationRef.current = null;
    };
  }, [isAnimatingTransform, expression, enableInterval, intervalA, intervalB, enableLine, lineK, lineB, transformType]);


  function buildAnalyzeOptions(overrides?: Partial<AnalyzeOptions & {
    intervalA: number;
    intervalB: number;
    enableInterval: boolean;
    lineK: number;
    lineB: number;
    enableLine: boolean;
    transformType: string;
    transformValue: number;
    enableTransform: boolean;
  }>): AnalyzeOptions {
    const nextEnableInterval = overrides?.enableInterval ?? enableInterval;
    const nextIntervalA = overrides?.intervalA ?? intervalA;
    const nextIntervalB = overrides?.intervalB ?? intervalB;
    const nextEnableLine = overrides?.enableLine ?? enableLine;
    const nextLineK = overrides?.lineK ?? lineK;
    const nextLineB = overrides?.lineB ?? lineB;
    const nextEnableTransform = overrides?.enableTransform ?? enableTransform;
    const nextTransformType = overrides?.transformType ?? transformType;
    const nextTransformValue = overrides?.transformValue ?? transformValue;
    return {
      ...(nextEnableInterval ? { interval: { a: nextIntervalA, b: nextIntervalB } } : {}),
      ...(nextEnableLine ? { line: { k: nextLineK, b: nextLineB } } : {}),
      ...(nextEnableTransform ? { transform: { type: nextTransformType, value: nextTransformValue } } : {}),
    };
  }

  function scheduleToolAnalyze(overrides?: Parameters<typeof buildAnalyzeOptions>[0]) {
    const expr = expression.trim();
    if (!expr || !result) return;
    if (sliderDebounceRef.current !== null) window.clearTimeout(sliderDebounceRef.current);
    sliderDebounceRef.current = window.setTimeout(() => {
      void runAnalyze(expr, { slider: true, requestOptions: buildAnalyzeOptions(overrides) });
    }, 220);
  }

  async function runAnalyze(expr: string, options?: { slider?: boolean; clearResult?: boolean; requestOptions?: AnalyzeOptions }) {
    const requestId = ++analyzeRequestRef.current;
    if (!options?.slider) setLoading(true);
    setError(null);
    if (options?.clearResult) setResult(null);
    try {
      const res = await analyzeFunction(expr, options?.requestOptions ?? {});
      if (requestId !== analyzeRequestRef.current) return;
      if (res.error) setError(res.error);
      else {
        setResult(res);
      }
    } catch (e: unknown) {
      if (requestId === analyzeRequestRef.current) setError(e instanceof Error ? e.message : 'Lỗi không xác định.');
    } finally {
      if (requestId === analyzeRequestRef.current && !options?.slider) setLoading(false);
    }
  }

  async function handleAnalyze() {
    const expr = expression.trim();
    if (!expr) return;
    await runAnalyze(expr, { clearResult: true, requestOptions: buildAnalyzeOptions() });
  }

  async function handleImageChange(file?: File) {
    if (!file) return;
    const requestId = ++analyzeRequestRef.current;
    setOcrLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await analyzeFunctionImage(await readFileAsDataUrl(file));
      if (requestId !== analyzeRequestRef.current) return;
      if (res.ocr_expression) setExpression(res.ocr_expression);
      if (res.error) setError(res.error);
      else {
        setResult(res);
      }
    } catch (e: unknown) {
      if (requestId === analyzeRequestRef.current) setError(e instanceof Error ? e.message : 'Lỗi OCR không xác định.');
    } finally {
      if (requestId === analyzeRequestRef.current) setOcrLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  function updateToolEnabled(key: 'interval' | 'line' | 'transform', enabled: boolean) {
    if (key === 'interval') setEnableInterval(enabled);
    if (key === 'line') setEnableLine(enabled);
    if (key === 'transform') {
      setEnableTransform(enabled);
      if (!enabled) setIsAnimatingTransform(false);
    }
    scheduleToolAnalyze({
      enableInterval: key === 'interval' ? enabled : enableInterval,
      enableLine: key === 'line' ? enabled : enableLine,
      enableTransform: key === 'transform' ? enabled : enableTransform,
    });
  }

  async function handleImageButtonClick() {
    if (loading || ocrLoading) return;
    const canReadClipboard = typeof navigator !== 'undefined' && !!navigator.clipboard?.read;
    if (!canReadClipboard) {
      fileInputRef.current?.click();
      return;
    }
    try {
      const items = await navigator.clipboard.read();
      for (const item of items) {
        const imageType = item.types.find((type) => type.startsWith('image/'));
        if (!imageType) continue;
        const blob = await item.getType(imageType);
        const file = new File([blob], 'clipboard-image.png', { type: imageType });
        await handleImageChange(file);
        return;
      }
      fileInputRef.current?.click();
    } catch {
      fileInputRef.current?.click();
    }
  }

  function imageFileFromDataTransfer(dataTransfer: DataTransfer) {
    return Array.from(dataTransfer.files).find((file) => file.type.startsWith('image/'));
  }

  function handleImageDragOver(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    if (!loading && !ocrLoading) setIsDraggingImage(true);
  }

  function handleImageDragLeave(event: React.DragEvent<HTMLDivElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setIsDraggingImage(false);
  }

  function handleImageDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDraggingImage(false);
    if (loading || ocrLoading) return;
    void handleImageChange(imageFileFromDataTransfer(event.dataTransfer));
  }

  return (
    <div className="fa2-panel">
      <div className="fa2-workspace">
        <aside className="fa2-control-panel">
          <div className="fa2-sticky-controls">
            <div className="fa2-header">
              <div className="fa2-header-icon" aria-hidden="true"><SvgIcon name="wave" /></div>
              <div>
                <div className="fa2-header-title">Khảo sát hàm số</div>
                <div className="fa2-header-sub">Nhập hàm, xem đồ thị, đạo hàm, cực trị và tiệm cận</div>
              </div>
            </div>

            <div className="fa2-control-card fa2-formula-card">
            <div className="fa2-control-card-head">
              <span>Nhập công thức</span>
              <button
                type="button"
                className="fa2-guide-btn fa2-guide-btn-link"
                aria-label="Hướng dẫn nhập hàm"
                data-guide-hover="Xem chi tiết cách gõ công thức"
                onClick={() => onOpenGuide?.()}
                disabled={loading || ocrLoading}
              >
                <SvgIcon name="hint" />
              </button>
            </div>
            <div className="fa2-formula-row-control">
              <div className="fa2-input-wrap">
                <span className="fa2-prefix">y =</span>
                <input
                  id="fa-expression-input"
                  className="fa2-input"
                  type="text"
                  placeholder="x^3 - 3*x + 2"
                  value={expression}
                  onChange={(e) => setExpression(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') void handleAnalyze(); }}
                  onMouseDown={(e) => {
                    if (e.button === 2) e.preventDefault();
                  }}
                  onContextMenu={(e) => {
                    if (loading || ocrLoading) return;
                    e.preventDefault();
                    e.currentTarget.blur();
                    void handleImageButtonClick();
                  }}
                  disabled={loading || ocrLoading}
                  autoComplete="off"
                  spellCheck={false}
                />
              </div>
              <button id="fa-submit-btn" type="button" className="sp-btn-primary" onClick={() => void handleAnalyze()} disabled={loading || ocrLoading || !expression.trim()}>
                {loading ? <span className="sp-spinner" aria-hidden="true" /> : 'Phân tích'}
              </button>
            </div>
              <button type="button" className="fa2-advanced-toggle" onClick={() => setShowAdvancedControls((value) => !value)} aria-expanded={showAdvancedControls}>
                {showAdvancedControls ? 'Ẩn tùy chọn' : 'Hiện tùy chọn'}
                <SvgIcon name="chevron" />
              </button>
            </div>
          </div>

          {showAdvancedControls && <div className="fa2-advanced-panel">
          <div className="fa2-control-card">
            <div className="fa2-control-card-head"><span>Ví dụ nhanh</span></div>
            <div className="fa2-chip-groups">
              {EXAMPLE_GROUPS.map((group) => (
                <div key={group.label} className="fa2-chip-group">
                  <div className="fa2-chip-group-title">{group.label}</div>
                  <div className="sp-chips">
                    {group.items.map((ex) => <button key={ex.value} type="button" className="sp-chip" onClick={() => setExpression(ex.value)}>{ex.label}</button>)}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="fa2-control-card fa2-upload-card">
            <div className="fa2-control-card-head"><span>Nhập bằng ảnh</span></div>
            <input ref={fileInputRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => void handleImageChange(e.target.files?.[0])} />
            <div
              className={`fa2-ocr-dropzone ${isDraggingImage ? 'is-dragging' : ''}`}
              onDragOver={handleImageDragOver}
              onDragLeave={handleImageDragLeave}
              onDrop={handleImageDrop}
            >
              <div className="fa2-ocr-dropzone-icon" aria-hidden="true"><SvgIcon name="upload" /></div>
              <strong>{ocrLoading ? 'Đang đọc ảnh...' : 'Kéo thả ảnh vào đây'}</strong>
              <span>Hoặc chọn tệp / dán ảnh từ clipboard để OCR công thức.</span>
              <div className="fa2-upload-actions">
                <button type="button" className="sp-btn-secondary" onClick={() => fileInputRef.current?.click()} disabled={loading || ocrLoading}>
                  {ocrLoading ? <span className="sp-spinner" aria-hidden="true" /> : <SvgIcon name="attach" />} Chọn ảnh
                </button>
                <button type="button" className="sp-btn-secondary" onClick={() => void handleImageButtonClick()} disabled={loading || ocrLoading}>Dán ảnh clipboard</button>
              </div>
            </div>
          </div>

          <div className="fa2-control-card">
            <div className="fa2-control-card-head"><span>Công cụ khảo sát</span></div>
            <div className="fa2-tool-strip">
              <button type="button" className={`fa2-tool-pill ${enableInterval ? 'is-active' : ''}`} onClick={() => updateToolEnabled('interval', !enableInterval)}>GTLN/GTNN</button>
              <button type="button" className={`fa2-tool-pill ${enableLine ? 'is-active' : ''}`} onClick={() => updateToolEnabled('line', !enableLine)}>Đường thẳng</button>
              <button type="button" className={`fa2-tool-pill ${enableTransform ? 'is-active' : ''}`} onClick={() => updateToolEnabled('transform', !enableTransform)}>Biến đổi</button>
            </div>

            {(enableInterval || enableLine || enableTransform) && (
              <div className="fa2-tool-panel">
                {enableInterval && (
                  <div className="fa2-tool-row">
                    <span className="fa2-tool-label">Đoạn [a,b]</span>
                    <input className="fa2-mini-input" type="number" value={intervalA} onChange={(e) => { setIntervalA(Number(e.target.value)); scheduleToolAnalyze({ intervalA: Number(e.target.value), enableInterval: true }); }} />
                    <input className="fa2-mini-input" type="number" value={intervalB} onChange={(e) => { setIntervalB(Number(e.target.value)); scheduleToolAnalyze({ intervalB: Number(e.target.value), enableInterval: true }); }} />
                  </div>
                )}

                {enableLine && (
                  <div className="fa2-tool-stack">
                    <div className="fa2-tool-label">Đường thẳng y = kx + b</div>
                    <SliderNumber label="k" value={lineK} min={-5} max={5} step={0.1} onChange={(value) => { setLineK(value); scheduleToolAnalyze({ lineK: value, enableLine: true }); }} />
                    <SliderNumber label="b" value={lineB} min={-10} max={10} step={0.1} onChange={(value) => { setLineB(value); scheduleToolAnalyze({ lineB: value, enableLine: true }); }} />
                  </div>
                )}

                {enableTransform && (
                  <div className="fa2-tool-stack">
                    <div className="fa2-tool-row">
                      <span className="fa2-tool-label">Biến đổi</span>
                      <select className="fa2-mini-input" value={transformType} onChange={(e) => { setTransformType(e.target.value); scheduleToolAnalyze({ transformType: e.target.value, enableTransform: true }); }}>
                        {TRANSFORMS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                      </select>
                      <button type="button" className="sp-btn-secondary" onClick={() => setIsAnimatingTransform((value) => !value)}>{isAnimatingTransform ? 'Dừng' : 'Animation'}</button>
                    </div>
                    <SliderNumber label="a" value={transformValue} min={-3} max={3} step={0.1} onChange={(value) => { setTransformValue(value); scheduleToolAnalyze({ transformValue: value, enableTransform: true }); }} />
                  </div>
                )}
              </div>
            )}
          </div>
          </div>}

          {error && <div className="sp-error" role="alert">{error}</div>}
        </aside>

        <section className="fa2-results-panel">
          {loading ? <AnalyzerLoadingResult /> : result ? <AnalysisResult result={result} /> : <EmptyAnalyzerResult />}
        </section>
      </div>
    </div>
  );
}

function EmptyAnalyzerResult() {
  return (
    <div className="fa2-empty-result">
      <div className="fa2-empty-icon" aria-hidden="true"><SvgIcon name="graph" /></div>
      <strong>Đồ thị và kết quả sẽ hiện ở đây</strong>
      <span>Nhập công thức ở cột trái rồi bấm Phân tích để xem đồ thị, bảng biến thiên và các điểm đặc biệt.</span>
    </div>
  );
}

function AnalyzerLoadingResult() {
  return (
    <div className="fa2-loading-result" aria-live="polite" aria-busy="true">
      <div className="fa2-skeleton fa2-skeleton-graph" />
      <div className="fa2-skeleton-stack">
        <div className="fa2-skeleton fa2-skeleton-card" />
        <div className="fa2-skeleton fa2-skeleton-card" />
        <div className="fa2-skeleton fa2-skeleton-card" />
      </div>
    </div>
  );
}

function SliderNumber({ label, value, min, max, step, onChange }: { label: string; value: number; min: number; max: number; step: number; onChange: (value: number) => void }) {
  return (
    <div className="fa2-slider-row">
      <span>{label} = {formatSliderValue(value)}</span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <input className="fa2-mini-input" type="number" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}

function clampToRange(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}

function formatSliderValue(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
}

function AnalysisResult({ result }: { result: AnalyzeResponse }) {
  const hasShapeDetails = result.concave_up_intervals.length > 0 || result.concave_down_intervals.length > 0 || result.horizontal_asymptotes.length > 0 || result.vertical_asymptotes.length > 0 || !!result.oblique_asymptote;
  const [variationBbtOpen, setVariationBbtOpen] = useState(false);
  const hasVariationTable = !!result.variation_table && result.variation_table.length > 0;

  return (
    <div className="fa2-result">
      <div className="fa2-result-shell">
        <div className="fa2-graph-column">
          <Section title="Đồ thị hàm số" icon="graph" className="fa2-graph-section">
            <FunctionGraphSvg result={result} />
          </Section>
        </div>

        <div className="fa2-analysis-column">
          <div className="fa2-result-sticky-head">
            <span>Đang xem</span>
            <KatexSpan tex={`y=${result.evaluated_expression_latex || result.expression_latex || sympyToLatex(result.evaluated_expression || result.expression)}`} />
          </div>

          <QuickSummary result={result} />


          <Section
            title="Đạo hàm và biến thiên"
            icon="derivative"
            headTrailing={
              hasVariationTable ? (
                <button type="button" className="bbt-zoom-btn bbt-zoom-btn-borderless" onClick={() => setVariationBbtOpen(true)} aria-label="Ấn để phóng to">
                  <span aria-hidden="true"><SvgIcon name="magnify" /></span>
                </button>
              ) : null
            }
          >
            <div className="fa2-formula-row"><KatexSpan tex="f'(x)=" className="fa2-label-mono fa2-label-katex" /><KatexSpan tex={result.derivative_latex || sympyToLatex(result.derivative || '')} className="fa2-katex" /></div>
            {result.second_derivative && <div className="fa2-formula-row"><KatexSpan tex="f''(x)=" className="fa2-label-mono fa2-label-katex" /><KatexSpan tex={result.second_derivative_latex || sympyToLatex(result.second_derivative)} className="fa2-katex" /></div>}
            <VariationTable rows={result.variation_table} expanded={variationBbtOpen} onExpandedChange={setVariationBbtOpen} hideZoomButton />
          </Section>

          {hasShapeDetails && (
            <Section title="Lồi lõm và tiệm cận" icon="asymptote">
              <div className="fa2-compact-list">
                {result.concave_up_intervals.length > 0 && <IntervalLine label="Lồi" value={result.concave_up_intervals.join(', ')} className="fa2-mono-inc" />}
                {result.concave_down_intervals.length > 0 && <IntervalLine label="Lõm" value={result.concave_down_intervals.join(', ')} className="fa2-mono-dec" />}
                {result.horizontal_asymptotes.map((ha, i) => <Asymptote key={`ha-${i}`} label="Ngang" tex={`y = ${sympyToLatex(ha.value)}`} />)}
                {result.vertical_asymptotes.map((va, i) => <Asymptote key={`va-${i}`} label="Đứng" tex={`x = ${sympyToLatex(va.x)}`} />)}
                {result.oblique_asymptote && <Asymptote label="Xiên" tex={sympyToLatex(result.oblique_asymptote)} />}
              </div>
            </Section>
          )}

          <div className="fa2-detail-grid">
            {result.interval_analysis && (
              <Section title="GTLN/GTNN trên đoạn" icon="points">
                <IntervalExtremaAnalysis interval={result.interval_analysis} />
              </Section>
            )}

            {result.line_analysis && (
              <Section title="Tương giao với đường thẳng" icon="graph">
                <div className="fa2-compact-list">
                  <IntervalLine label="Đường thẳng" value={result.line_analysis.equation} className="fa2-mono-inc" />
                  <IntervalLine label="Số giao điểm" value={String(result.line_analysis.intersection_count)} className="fa2-mono-inc" />
                  {result.line_analysis.intersections.map((pt, index) => <PointBadge key={`line-${index}`} label="Giao điểm" tex={`(${sympyToLatex(pt.x)},\\; ${sympyToLatex(pt.y)})`} kind="axis" />)}
                  {result.line_analysis.relative_intervals.above.length > 0 && <IntervalLine label="f(x) > d" value={result.line_analysis.relative_intervals.above.join(', ')} className="fa2-mono-inc" />}
                  {result.line_analysis.relative_intervals.below.length > 0 && <IntervalLine label="f(x) < d" value={result.line_analysis.relative_intervals.below.join(', ')} className="fa2-mono-dec" />}
                </div>
              </Section>
            )}

            {result.transform_preview && (
              <Section title="Biến đổi đồ thị" icon="graph">
                <div className="fa2-transform-formula">
                  <KatexSpan tex={TRANSFORM_LABEL_TEX[result.transform_preview.type] ?? sympyToLatex(result.transform_preview.label)} className="fa2-transform-rule" />
                  <KatexSpan tex={`g(x)=${result.transform_preview.expression_latex || sympyToLatex(result.transform_preview.expression)}`} className="fa2-katex" />
                </div>
              </Section>
            )}
          </div>

          {result.ocr_text && <div className="sp-info">OCR: {result.ocr_text}</div>}
          {result.warnings.length > 0 && <div className="sp-warnings">{result.warnings.map((w, i) => <div key={i} className="sp-warning">{w}</div>)}</div>}
        </div>
      </div>
    </div>
  );
}

function QuickSummary({ result }: { result: AnalyzeResponse }) {
  const expressionTex = result.evaluated_expression_latex || result.expression_latex || sympyToLatex(result.evaluated_expression || result.expression);

  return (
    <div className="fa2-quick-card">
      <div className="fa2-quick-head">
        <span className="fa2-quick-eyebrow">Kết quả nhanh</span>
        <KatexSpan tex={`y=${expressionTex}`} className="fa2-quick-expression" />
      </div>
      <div className="fa2-quick-rows">
        {result.domain_latex && <SummaryCard label="Tập xác định" tex={result.domain_latex} />}
        {result.range_latex && <SummaryCard label="Tập giá trị" tex={result.range_latex} />}
        {(result.derivative_latex || result.derivative) && <SummaryCard label="Đạo hàm" tex={result.derivative_latex || sympyToLatex(result.derivative || '')} />}
      </div>
    </div>
  );
}

function FunctionGraphSvg({ result }: { result: AnalyzeResponse }) {
  const data = result.graph_points || [];
  const graph = useMemo(() => buildSvgGraph(data, result), [data, result]);
  const svgId = useId();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<{ pointerId: number; x: number; y: number } | null>(null);
  const [view, setView] = useState({ scale: 1, tx: 0, ty: 0 });
  const [selectedPointKey, setSelectedPointKey] = useState<string | null>(null);
  const specialPoints = data.length >= 2 ? plotSpecialPoints(result, graph.project, SVG_WIDTH, SVG_HEIGHT, 28) : plotSpecialPoints(result, projectFallbackPoint, SVG_WIDTH, SVG_HEIGHT, 28);
  const visibleSpecialPoints = specialPoints.filter((point) => point.x >= 0 && point.x <= SVG_WIDTH && point.y >= 0 && point.y <= SVG_HEIGHT);
  const selectedPoint = visibleSpecialPoints.find((point) => point.key === selectedPointKey) ?? null;
  if (result.geogebra_commands.length > 0) {
    const scene = result.graph_scene ?? createFallbackGraphScene(result.expression);
    const overlayPoints = visibleSpecialPoints.filter((point) => point.kind !== 'axis-x' && point.kind !== 'axis-y');
    const overlaySelected = overlayPoints.find((point) => point.key === selectedPointKey) ?? null;
    return (
      <div className="fa2-graph-card fa2-geogebra-graph-card">
        <GeoGebraView
          commands={result.geogebra_commands}
          renderer="geogebra_2d"
          scene={scene}
          view={scene.view}
          embedded
        />
        <GraphPointOverlay points={overlayPoints} selectedPoint={overlaySelected} onSelectPoint={setSelectedPointKey} />
      </div>
    );
  }
  if (data.length < 2) return <div className="info-box">Chưa đủ dữ liệu để vẽ đồ thị.</div>;

  const clipId = `${svgId}-clip`;
  const scaleMin = 0.7;
  const scaleMax = 5;

  function toLocalPoint(clientX: number, clientY: number) {
    const svg = svgRef.current;
    if (!svg) return { x: SVG_WIDTH / 2, y: SVG_HEIGHT / 2 };
    const rect = svg.getBoundingClientRect();
    const x = ((clientX - rect.left) / rect.width) * SVG_WIDTH;
    const y = ((clientY - rect.top) / rect.height) * SVG_HEIGHT;
    return { x, y };
  }

  function zoomAt(multiplier: number, clientX?: number, clientY?: number) {
    setView((current) => {
      const nextScale = Math.max(scaleMin, Math.min(scaleMax, current.scale * multiplier));
      if (Math.abs(nextScale - current.scale) < 1e-6) return current;
      const focus = clientX !== undefined && clientY !== undefined
        ? toLocalPoint(clientX, clientY)
        : { x: SVG_WIDTH / 2, y: SVG_HEIGHT / 2 };
      const ratio = nextScale / current.scale;
      return {
        scale: nextScale,
        tx: focus.x - (focus.x - current.tx) * ratio,
        ty: focus.y - (focus.y - current.ty) * ratio,
      };
    });
  }

  function handleWheel(event: React.WheelEvent<SVGSVGElement>) {
    event.preventDefault();
    zoomAt(event.deltaY < 0 ? 1.14 : 1 / 1.14, event.clientX, event.clientY);
  }

  function handlePointerDown(event: React.PointerEvent<SVGSVGElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
  }

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const deltaX = event.clientX - drag.x;
    const deltaY = event.clientY - drag.y;
    dragRef.current = { ...drag, x: event.clientX, y: event.clientY };
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    setView((current) => ({
      ...current,
      tx: current.tx + (deltaX / rect.width) * SVG_WIDTH,
      ty: current.ty + (deltaY / rect.height) * SVG_HEIGHT,
    }));
  }

  function handlePointerUp(event: React.PointerEvent<SVGSVGElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    dragRef.current = null;
  }

  return (
    <div className="fa2-graph-card">
      <div className="fa2-graph-toolbar">
        <span>Kéo để di chuyển | Con lăn để zoom</span>
        <div className="fa2-graph-toolbar-actions">
          <button type="button" className="sp-btn-secondary" onClick={() => zoomAt(1.14)} aria-label="Phóng to">+</button>
          <button type="button" className="sp-btn-secondary" onClick={() => zoomAt(1 / 1.14)} aria-label="Thu nhỏ">-</button>
          <button type="button" className="sp-btn-secondary" onClick={() => setView({ scale: 1, tx: 0, ty: 0 })}>Reset</button>
        </div>
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
        role="img"
        aria-label={`Đồ thị y = ${result.expression}`}
        className="fa2-svg-graph"
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <defs>
          <clipPath id={clipId}>
            <rect x="0" y="0" width={SVG_WIDTH} height={SVG_HEIGHT} rx="8" />
          </clipPath>
        </defs>
        <rect x="0" y="0" width={SVG_WIDTH} height={SVG_HEIGHT} rx="8" className="fa2-graph-bg" />
        <g clipPath={`url(#${clipId})`} transform={`translate(${view.tx} ${view.ty}) scale(${view.scale})`}>
          {graph.grid.map((line, i) => <line key={`grid-${i}`} {...line} className="fa2-graph-grid" />)}
          <line x1={graph.xAxis.x1} y1={graph.xAxis.y1} x2={graph.xAxis.x2} y2={graph.xAxis.y2} className="fa2-graph-axis" />
          <line x1={graph.yAxis.x1} y1={graph.yAxis.y1} x2={graph.yAxis.x2} y2={graph.yAxis.y2} className="fa2-graph-axis" />
          {graph.paths.map((path, i) => <path key={`path-${i}`} d={path} className="fa2-graph-path" />)}
          {visibleSpecialPoints.map((point) => (
            <g
              key={point.key}
              className="fa2-graph-special-point"
              role="button"
              tabIndex={0}
              aria-label={`${point.label} ${point.coordsText}`}
              onClick={(event) => {
                event.stopPropagation();
                setSelectedPointKey(point.key);
              }}
              onPointerDown={(event) => event.stopPropagation()}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  setSelectedPointKey(point.key);
                }
              }}
            >
              <circle cx={point.x} cy={point.y} r="6" className={`fa2-graph-point fa2-graph-point-${point.kind}`} />
              <text
                x={point.labelX}
                y={point.labelY}
                textAnchor={point.anchor}
                className="fa2-graph-label"
              >
                {point.label}
              </text>
            </g>
          ))}
          {selectedPoint && (
            <g className="fa2-graph-point-popover" transform={`translate(${selectedPoint.popoverX} ${selectedPoint.popoverY})`}>
              <rect x="0" y="0" width={selectedPoint.popoverWidth} height="46" rx="10" />
              <text x="10" y="18" className="fa2-graph-popover-label">{selectedPoint.label}</text>
              <text x="10" y="36" className="fa2-graph-popover-coords">{selectedPoint.coordsText}</text>
            </g>
          )}
        </g>
        {graph.xTicks.map((tick, idx) => (
          <text key={`xt-${idx}`} x={tick.x} y={SVG_HEIGHT - 6} className="fa2-graph-tick">{tick.label}</text>
        ))}
        {graph.yTicks.map((tick, idx) => (
          <text key={`yt-${idx}`} x={6} y={tick.y + 4} className="fa2-graph-tick">{tick.label}</text>
        ))}
      </svg>
    </div>
  );
}

function GraphPointOverlay({ points, selectedPoint, onSelectPoint }: {
  points: ReturnType<typeof plotSpecialPoints>;
  selectedPoint: ReturnType<typeof plotSpecialPoints>[number] | null;
  onSelectPoint: (key: string) => void;
}) {
  if (points.length === 0) return null;
  return (
    <div className="fa2-geogebra-point-overlay">
      {points.map((point) => (
        <button
          key={point.key}
          type="button"
          className={`fa2-geogebra-point fa2-geogebra-point-${point.kind}`}
          style={{ left: `${(point.x / SVG_WIDTH) * 100}%`, top: `${(point.y / SVG_HEIGHT) * 100}%` }}
          aria-label={`${point.label} ${point.coordsText}`}
          onClick={() => onSelectPoint(point.key)}
        >
          <span>{point.label}</span>
        </button>
      ))}
      {selectedPoint && (
        <div
          className="fa2-geogebra-point-popover"
          style={{ left: `${(selectedPoint.popoverX / SVG_WIDTH) * 100}%`, top: `${(selectedPoint.popoverY / SVG_HEIGHT) * 100}%` }}
        >
          <span>{selectedPoint.label}</span>
          <strong>{selectedPoint.coordsText}</strong>
        </div>
      )}
    </div>
  );
}

function createFallbackGraphScene(expression: string): MathScene {
  return {
    problem_text: `Khảo sát hàm số y = ${expression}`,
    grade: null,
    topic: 'function_graph',
    renderer: 'geogebra_2d',
    objects: [{ type: 'function_graph', name: 'f', expression }],
    relations: [],
    annotations: [],
    view: {
      dimension: '2d',
      show_axes: true,
      show_grid: true,
      show_coordinates: false,
    },
  };
}

const SVG_WIDTH = 720;
const SVG_HEIGHT = 300;

function projectFallbackPoint(point: { x: number; y: number }) {
  return {
    x: SVG_WIDTH / 2 + point.x * 42,
    y: SVG_HEIGHT / 2 - point.y * 42,
  };
}

function buildSvgGraph(points: Array<{ x: number; y: number }>, result: AnalyzeResponse) {
  const width = SVG_WIDTH;
  const height = SVG_HEIGHT;
  const pad = 28;
  const finitePoints = points.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y)).sort((a, b) => a.x - b.x);
  if (finitePoints.length < 2) {
    return {
      paths: [],
      grid: [],
      xTicks: [],
      yTicks: [],
      project: (p: { x: number; y: number }) => ({ x: p.x, y: p.y }),
      xAxis: { x1: pad, y1: height / 2, x2: width - pad, y2: height / 2 },
      yAxis: { x1: width / 2, y1: pad, x2: width / 2, y2: height - pad },
    };
  }
  const specialXs = [
    ...result.critical_points.map((p) => Number(p.x)),
    ...result.inflection_points.map((p) => Number(p.x)),
    ...result.x_intercepts.map(Number),
    0,
  ].filter(Number.isFinite);
  const quantileMinX = quantile(finitePoints.map((p) => p.x), 0.08);
  const quantileMaxX = quantile(finitePoints.map((p) => p.x), 0.92);
  const keyMinX = specialXs.length > 0 ? Math.min(...specialXs) : quantileMinX;
  const keyMaxX = specialXs.length > 0 ? Math.max(...specialXs) : quantileMaxX;
  const baseMinX = Math.min(quantileMinX, keyMinX);
  const baseMaxX = Math.max(quantileMaxX, keyMaxX);
  const span = Math.max(baseMaxX - baseMinX, 4);
  const xMargin = Math.max(0.9, span * 0.18);
  const x0 = baseMinX - xMargin;
  const x1 = baseMaxX + xMargin;
  const focused = finitePoints.filter((p) => p.x >= x0 && p.x <= x1);
  const usable = focused.length >= 16 ? focused : finitePoints;
  const specialYs = [
    ...result.critical_points.map((p) => Number(p.y)),
    ...result.inflection_points.map((p) => Number(p.y)),
    Number(result.y_intercept),
    0,
  ].filter(Number.isFinite);
  const usableYs = usable.map((p) => p.y);
  const lo = quantile(usableYs, 0.08);
  const hi = quantile(usableYs, 0.92);
  const minY = Math.min(lo, ...specialYs, -1);
  const maxY = Math.max(hi, ...specialYs, 1);
  const dy = Math.max(maxY - minY, 1);
  let y0 = minY - dy * 0.16;
  let y1 = maxY + dy * 0.16;
  let left = x0;
  let right = x1;
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;
  const unit = Math.min(plotW / (right - left), plotH / (y1 - y0));
  const targetXRange = plotW / unit;
  const targetYRange = plotH / unit;
  const cx = (left + right) / 2;
  const cy = (y0 + y1) / 2;
  left = cx - targetXRange / 2;
  right = cx + targetXRange / 2;
  y0 = cy - targetYRange / 2;
  y1 = cy + targetYRange / 2;
  const project = (p: { x: number; y: number }) => ({ x: pad + ((p.x - left) / (right - left)) * plotW, y: height - pad - ((p.y - y0) / (y1 - y0)) * plotH });
  const yJump = Math.max(2.2, quantile(usableYs.map((v) => Math.abs(v)), 0.9));
  const segments: Array<Array<{ x: number; y: number }>> = [];
  for (const point of usable) {
    const lastSegment = segments[segments.length - 1];
    const lastPoint = lastSegment?.[lastSegment.length - 1];
    if (!lastSegment || !lastPoint || Math.abs(point.x - lastPoint.x) > 0.2 || Math.abs(point.y - lastPoint.y) > yJump) segments.push([point]);
    else lastSegment.push(point);
  }
  const paths = segments.filter((segment) => segment.length > 1).map((segment) => segment.map((p, i) => `${i === 0 ? 'M' : 'L'} ${project(p).x.toFixed(2)} ${project(p).y.toFixed(2)}`).join(' '));
  const xTicks = createTicks(left, right, 8).map((value) => ({ value, x: project({ x: value, y: y0 }).x, label: shortNumber(value) }));
  const yTicks = createTicks(y0, y1, 6).map((value) => ({ value, y: project({ x: left, y: value }).y, label: shortNumber(value) }));
  const grid = [
    ...xTicks.map((tick) => ({ x1: tick.x, y1: pad, x2: tick.x, y2: height - pad })),
    ...yTicks.map((tick) => ({ x1: pad, y1: tick.y, x2: width - pad, y2: tick.y })),
  ];
  const axis0 = project({ x: 0, y: 0 });
  const axisX = Math.min(width - pad, Math.max(pad, axis0.x));
  const axisY = Math.min(height - pad, Math.max(pad, axis0.y));
  return { paths, grid, xTicks, yTicks, project, xAxis: { x1: pad, y1: axisY, x2: width - pad, y2: axisY }, yAxis: { x1: axisX, y1: pad, x2: axisX, y2: height - pad } };
}

function createTicks(min: number, max: number, targetCount: number) {
  const range = Math.max(max - min, 1e-8);
  const rough = range / Math.max(targetCount, 2);
  const step = niceStep(rough);
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + step * 0.5; v += step) ticks.push(roundTick(v));
  if (ticks.length < 2) return [roundTick(min), roundTick(max)];
  return ticks;
}

function niceStep(raw: number) {
  const exponent = Math.floor(Math.log10(raw));
  const fraction = raw / 10 ** exponent;
  const niceFraction = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
  return niceFraction * 10 ** exponent;
}

function roundTick(value: number) {
  return Math.round(value * 1_000_000) / 1_000_000;
}

function shortNumber(value: number) {
  const abs = Math.abs(value);
  if (abs >= 1000) return value.toFixed(0);
  if (abs >= 10) return value.toFixed(1).replace(/\.0$/, '');
  if (abs >= 1) return value.toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1');
  return value.toFixed(3).replace(/\.?0+$/, '');
}

function quantile(values: number[], q: number) {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = (sorted.length - 1) * q;
  const low = Math.floor(index);
  const high = Math.ceil(index);
  if (low === high) return sorted[low];
  const ratio = index - low;
  return sorted[low] * (1 - ratio) + sorted[high] * ratio;
}

function plotSpecialPoints(
  result: AnalyzeResponse,
  project: (point: { x: number; y: number }) => { x: number; y: number },
  width: number,
  height: number,
  pad: number,
) {
  const points = [
    ...result.critical_points.map((cp, i) => ({ key: `cp-${i}`, kind: cp.kind, label: cp.kind === 'max' ? 'CĐ' : cp.kind === 'min' ? 'CT' : 'T', raw: { x: Number(cp.x), y: Number(cp.y) }, coordsText: `(${cp.x_exact || cp.x}; ${cp.y})` })),
    ...result.inflection_points.map((pt, i) => ({ key: `ip-${i}`, kind: 'inflection', label: 'U', raw: { x: Number(pt.x), y: Number(pt.y) }, coordsText: `(${pt.x_exact || pt.x}; ${pt.y})` })),
    ...(result.y_intercept !== null ? [{ key: 'oy', kind: 'axis-y', label: 'Oy', raw: { x: 0, y: Number(result.y_intercept) }, coordsText: `(0; ${result.y_intercept})` }] : []),
    ...result.x_intercepts.map((xv, i) => ({ key: `ox-${i}`, kind: 'axis-x', label: 'Ox', raw: { x: Number(xv), y: 0 }, coordsText: `(${xv}; 0)` })),
  ].filter((p) => Number.isFinite(p.raw.x) && Number.isFinite(p.raw.y)).map((p) => ({ ...p, ...project(p.raw) }));
  const minSepPx = 20;
  const uniqueScreen: typeof points = [];
  for (const p of points) {
    if (uniqueScreen.every((k) => Math.hypot(k.x - p.x, k.y - p.y) >= minSepPx)) uniqueScreen.push(p);
  }
  const occupied: Array<{ x: number; y: number }> = [];
  const candidates: Array<{ dx: number; dy: number; anchor: 'start' | 'middle' | 'end' }> = [
    { dx: 12, dy: -10, anchor: 'start' },
    { dx: 12, dy: 16, anchor: 'start' },
    { dx: -12, dy: -10, anchor: 'end' },
    { dx: -12, dy: 16, anchor: 'end' },
    { dx: 0, dy: -14, anchor: 'middle' },
    { dx: 0, dy: 20, anchor: 'middle' },
  ];
  return uniqueScreen.map((point) => {
    const selected = candidates.find((option) => {
      const x = point.x + option.dx;
      const y = point.y + option.dy;
      const inBounds = x >= pad + 6 && x <= width - pad - 6 && y >= pad + 8 && y <= height - pad - 6;
      if (!inBounds) return false;
      return occupied.every((placed) => Math.abs(placed.x - x) > 30 || Math.abs(placed.y - y) > 15);
    }) ?? { dx: 12, dy: -10, anchor: 'start' as const };
    const labelX = point.x + selected.dx;
    const labelY = point.y + selected.dy;
    occupied.push({ x: labelX, y: labelY });
    const popoverWidth = Math.min(Math.max(point.coordsText.length * 8 + 20, 92), 180);
    const popoverX = Math.min(Math.max(point.x + 10, pad), width - popoverWidth - pad);
    const popoverY = Math.min(Math.max(point.y - 56, pad), height - 52 - pad);
    return { ...point, labelX, labelY, anchor: selected.anchor, popoverX, popoverY, popoverWidth };
  });
}

function SummaryCard({ label, tex }: { label: string; tex: string }) {
  return <div className="fa2-summary-card"><span>{label}</span><KatexSpan tex={tex} /></div>;
}

function PointBadge({ label, tex, kind }: { label: string; tex: string; kind: string }) {
  const icon = kind === 'max' ? 'triangleUp' : kind === 'min' ? 'triangleDown' : kind === 'inflection' ? 'trend' : 'target';
  return <div className={`fa2-ext fa2-ext-${kind}`}><span className="fa2-ext-icon" aria-hidden="true"><SvgIcon name={icon} /></span><div className="fa2-ext-body"><span className="fa2-ext-kind">{label}</span><KatexSpan tex={tex} className="fa2-ext-coords" /></div></div>;
}

function Asymptote({ label, tex }: { label: string; tex: string }) {
  return <div className="fa2-asym"><span className="fa2-asym-tag">{label}</span><KatexSpan tex={tex} /></div>;
}

function VariationTable({
  rows,
  expanded: expandedProp,
  onExpandedChange,
  hideZoomButton = false,
}: {
  rows: AnalyzeResponse['variation_table'];
  expanded?: boolean;
  onExpandedChange?: (open: boolean) => void;
  hideZoomButton?: boolean;
}) {
  const [internalExpanded, setInternalExpanded] = useState(false);
  const controlled = expandedProp !== undefined && onExpandedChange !== undefined;
  const isExpanded = controlled ? expandedProp : internalExpanded;
  const setIsExpanded = (open: boolean) => {
    if (controlled) onExpandedChange(open);
    else setInternalExpanded(open);
  };
  if (!rows || rows.length === 0) return null;
  const dynamicCols = rows.length * 2 - 1;
  const forceTimeline = rows.length > 4;
  const gridStyle = { '--bbt-cols': dynamicCols } as CSSProperties;

  return (
    <div className={`bbt-layout ${forceTimeline ? 'bbt-layout-force-timeline' : ''}`}>
      {!hideZoomButton && (
        <div className="bbt-actions">
          <button type="button" className="bbt-zoom-btn" onClick={() => setIsExpanded(true)} aria-label="Ấn để phóng to">
            <span aria-hidden="true"><SvgIcon name="magnify" /></span>
          </button>
        </div>
      )}
      <VariationGrid rows={rows} style={gridStyle} />
      <div className="bbt-timeline">
        {rows.slice(0, -1).map((row, index) => {
          const next = rows[index + 1];
          const direction = normalizeDirection(row.arrow_to_next);
          return (
            <div key={`tl-${index}`} className={`bbt-timeline-item ${direction === 'up' ? 'bbt-timeline-up' : direction === 'down' ? 'bbt-timeline-down' : ''}`}>
              <div className="bbt-timeline-range"><KatexSpan tex={`${sympyToLatex(row.x)} \\to ${sympyToLatex(next.x)}`} /></div>
              <div className="bbt-timeline-trend">{renderArrowLatex(row.arrow_to_next)}</div>
              <div className="bbt-timeline-values"><KatexSpan tex={`${nodeValueTex(rows, index)} \\to ${nodeValueTex(rows, index + 1)}`} /></div>
            </div>
          );
        })}
      </div>
      {isExpanded && (
        <div className="bbt-modal" role="dialog" aria-modal="true" aria-label="Bảng biến thiên phóng to" onClick={() => setIsExpanded(false)}>
          <div className="bbt-modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="bbt-modal-head">
              <span>Bảng biến thiên phóng to</span>
              <button type="button" className="bbt-modal-close" onClick={() => setIsExpanded(false)} aria-label="Đóng bảng biến thiên phóng to">Đóng</button>
            </div>
            <VariationGrid rows={rows} style={gridStyle} className="bbt-wrap-expanded" />
          </div>
        </div>
      )}
    </div>
  );
}

function VariationGrid({ rows, style, className = '' }: { rows: AnalyzeResponse['variation_table']; style: CSSProperties; className?: string }) {
  return (
    <div className={`bbt-wrap ${className}`.trim()} style={style}>
      <div className="bbt-row bbt-row-x">
        <div className="bbt-cell bbt-label"><KatexSpan tex="x" className="bbt-label-tex" /></div>
        {rows.map((row, index) => (
          <Fragment key={`x-${index}`}>
            <div className="bbt-cell bbt-x-val"><KatexSpan tex={sympyToLatex(row.x)} /></div>
            {index < rows.length - 1 && <div className="bbt-cell bbt-gap" />}
          </Fragment>
        ))}
      </div>
      <div className="bbt-row bbt-row-fp">
        <div className="bbt-cell bbt-label"><KatexSpan tex="f'(x)" className="bbt-label-tex" /></div>
        {rows.map((row, index) => (
          <Fragment key={`fp-${index}`}>
            <div className="bbt-cell bbt-zero">{renderMarkerLatex(row.kind)}</div>
            {index < rows.length - 1 && (
              <div className="bbt-cell bbt-gap bbt-fp-arrow">
                {renderDerivativeSignLatex(row.arrow_to_next)}
              </div>
            )}
          </Fragment>
        ))}
      </div>
      <div className="bbt-row bbt-row-f">
        <div className="bbt-cell bbt-label"><KatexSpan tex="f(x)" className="bbt-label-tex" /></div>
        {rows.map((row, index) => (
          <Fragment key={`f-${index}`}>
            <div className={`bbt-cell bbt-f-val ${valueLevelClass(rows, index)} ${row.kind === 'max' ? 'bbt-fmax' : row.kind === 'min' ? 'bbt-fmin' : ''}`}>
              {renderFunctionValueLatex(rows, row, index)}
            </div>
            {index < rows.length - 1 && (
              <div className="bbt-cell bbt-gap bbt-curve-cell">
                <VariationStroke direction={normalizeDirection(row.arrow_to_next)} />
              </div>
            )}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

function renderMarkerLatex(kind: string) {
  if (kind === 'max' || kind === 'min') return <KatexSpan tex="0" className="bbt-katex-inline" />;
  if (kind === 'asymptote') return <KatexSpan tex="\\parallel" className="bbt-katex-inline" />;
  return <span className="bbt-katex-placeholder" aria-hidden="true"> </span>;
}

function arrowSymbol(value: string | null) {
  const direction = normalizeDirection(value);
  if (direction === 'up') return '↗';
  if (direction === 'down') return '↘';
  return '→';
}

function arrowClass(value: string | null) {
  const direction = normalizeDirection(value);
  if (direction === 'up') return 'bbt-up';
  if (direction === 'down') return 'bbt-down';
  return '';
}

function derivativeSign(value: string | null) {
  const direction = normalizeDirection(value);
  if (direction === 'up') return '+';
  if (direction === 'down') return '−';
  return '';
}

function derivativeSignClass(value: string | null) {
  const direction = normalizeDirection(value);
  if (direction === 'up') return 'bbt-sign-pos';
  if (direction === 'down') return 'bbt-sign-neg';
  return '';
}

function normalizeDirection(value: string | null): 'up' | 'down' | null {
  if (!value) return null;
  const raw = value.trim().toLowerCase();
  if (raw.includes('↗') || raw.includes('up') || raw.includes('increase') || raw.includes('inc') || raw === '+') return 'up';
  if (raw.includes('↘') || raw.includes('down') || raw.includes('decrease') || raw.includes('dec') || raw === '-' || raw === '−') return 'down';
  return null;
}

function renderDerivativeSignLatex(value: string | null) {
  const sign = derivativeSign(value);
  if (!sign) return <span className="bbt-katex-placeholder" aria-hidden="true"> </span>;
  return <KatexSpan tex={sign === '+' ? '+' : '-'} className={`bbt-katex-inline ${derivativeSignClass(value)}`} />;
}

function renderArrowLatex(value: string | null) {
  const symbol = arrowSymbol(value);
  const tex = symbol === '↗' ? '\\nearrow' : symbol === '↘' ? '\\searrow' : '\\to';
  return <KatexSpan tex={tex} className={`bbt-katex-inline ${arrowClass(value)}`} />;
}

function renderFunctionValueLatex(
  rows: AnalyzeResponse['variation_table'],
  row: AnalyzeResponse['variation_table'][number],
  index: number,
) {
  if (row.y) return <KatexSpan tex={sympyToLatex(row.y)} />;
  if (row.kind === 'boundary') return <KatexSpan tex={boundaryInfinityTex(rows, index)} className="bbt-boundary" />;
  if (row.kind === 'asymptote') return <span className="bbt-katex-placeholder" aria-hidden="true"> </span>;
  return <span className="bbt-katex-placeholder" aria-hidden="true"> </span>;
}

function boundaryInfinityTex(rows: AnalyzeResponse['variation_table'], index: number) {
  if (index === 0) {
    const direction = normalizeDirection(rows[index]?.arrow_to_next ?? null);
    if (direction === 'down') return '+\\infty';
    if (direction === 'up') return '-\\infty';
    return '\\infty';
  }
  if (index === rows.length - 1) {
    const direction = normalizeDirection(rows[index - 1]?.arrow_to_next ?? null);
    if (direction === 'up') return '+\\infty';
    if (direction === 'down') return '-\\infty';
    return '\\infty';
  }
  return '\\infty';
}

function nodeValueTex(rows: AnalyzeResponse['variation_table'], index: number) {
  const row = rows[index];
  if (!row) return '\\varnothing';
  if (row.y) return sympyToLatex(row.y);
  if (row.kind === 'boundary') return boundaryInfinityTex(rows, index);
  return '\\varnothing';
}

function valueLevelClass(rows: AnalyzeResponse['variation_table'], index: number) {
  const current = rows[index];
  if (!current || current.kind === 'asymptote') return '';
  const incoming = normalizeDirection(index > 0 ? rows[index - 1]?.arrow_to_next ?? null : null);
  const outgoing = normalizeDirection(rows[index]?.arrow_to_next ?? null);

  if (!incoming && outgoing) return outgoing === 'up' ? 'bbt-level-low' : 'bbt-level-high';
  if (incoming && !outgoing) return incoming === 'up' ? 'bbt-level-high' : 'bbt-level-low';
  if (incoming === 'up' && outgoing === 'down') return 'bbt-level-high';
  if (incoming === 'down' && outgoing === 'up') return 'bbt-level-low';
  if (incoming === 'up' && outgoing === 'up') return 'bbt-level-mid';
  if (incoming === 'down' && outgoing === 'down') return 'bbt-level-mid';
  return '';
}

function VariationStroke({ direction }: { direction: 'up' | 'down' | null }) {
  const markerId = `${useId()}bbt-arrow`;
  const path = direction === 'up' ? 'M 8 34 L 92 8' : direction === 'down' ? 'M 8 8 L 92 34' : 'M 8 21 L 92 21';
  return (
    <svg viewBox="0 0 100 42" className={`bbt-stroke ${direction === 'up' ? 'bbt-up' : direction === 'down' ? 'bbt-down' : ''}`} aria-hidden="true">
      <defs>
        <marker id={markerId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
        </marker>
      </defs>
      <path d={path} fill="none" stroke="currentColor" strokeWidth="1.75" markerEnd={`url(#${markerId})`} />
    </svg>
  );
}

type IntervalAnalysis = NonNullable<AnalyzeResponse['interval_analysis']>;

type IntervalCandidate = { label: string; x: string; y: string };

function intervalExtremaConclusionTex(kind: 'max' | 'min', data: IntervalAnalysis): string {
  const a = sympyToLatex(data.a);
  const b = sympyToLatex(data.b);
  const pt = kind === 'max' ? data.max_point : data.min_point;
  const op = kind === 'max' ? '\\max' : '\\min';
  const xv = sympyToLatex(pt.x);
  const yv = sympyToLatex(pt.y);
  return `\\displaystyle ${op}_{x\\in\\left[${a},\\,${b}\\right]} f(x)=f\\left(${xv}\\right)=${yv}`;
}

function IntervalExtremaAnalysis({ interval }: { interval: IntervalAnalysis }) {
  const candidates: IntervalCandidate[] = [
    { label: 'Cận trái', x: interval.a, y: interval.fa },
    { label: 'Cận phải', x: interval.b, y: interval.fb },
    ...interval.extrema_inside.map((point) => ({ label: point.label, x: point.x_exact || point.x, y: point.y })),
  ];

  return (
    <div className="fa2-interval-analysis">
      <div className="fa2-interval-note">
        <KatexSpan tex={`x\\in[${sympyToLatex(interval.a)},${sympyToLatex(interval.b)}]`} />
        <span>Xét giá trị tại hai cận và các điểm cực trị nằm trong đoạn.</span>
      </div>
      <table className="fa2-result-table fa2-interval-table"><thead><tr><th>Điểm xét</th><th><KatexSpan tex="x" /></th><th><KatexSpan tex="f(x)" /></th></tr></thead><tbody>
        {candidates.map((candidate) => (
          <tr key={`${candidate.label}-${candidate.x}-${candidate.y}`}>
            <th>{candidate.label}</th>
            <td><KatexSpan tex={sympyToLatex(candidate.x)} /></td>
            <td><KatexSpan tex={sympyToLatex(candidate.y)} /></td>
          </tr>
        ))}
      </tbody></table>
      <div className="fa2-extrema-conclusion">
        <div className="fa2-extrema-formula">
          <KatexSpan display tex={intervalExtremaConclusionTex('max', interval)} />
        </div>
        <div className="fa2-extrema-formula">
          <KatexSpan display tex={intervalExtremaConclusionTex('min', interval)} />
        </div>
      </div>
    </div>
  );
}

function IntervalLine({ label, value, className }: { label: string; value: string; className: string }) {
  return <div className={`fa2-mono ${className}`}><span className="fa2-mono-label">{label}:</span><span className="fa2-mono-val"><KatexSpan tex={sympyToLatex(value)} /></span></div>;
}

function Section({
  title,
  icon,
  children,
  className = '',
  headTrailing,
}: {
  title: string;
  icon: IconName;
  children: ReactNode;
  className?: string;
  headTrailing?: ReactNode;
}) {
  return (
    <div className={`fa2-section ${className}`.trim()}>
      <div className="fa2-section-head">
        <span className="fa2-section-icon" aria-hidden="true"><SvgIcon name={icon} /></span>
        <span className="fa2-section-title">{title}</span>
        {headTrailing != null && headTrailing !== false && <div className="fa2-section-trailing">{headTrailing}</div>}
      </div>
      <div className="fa2-section-body">{children}</div>
    </div>
  );
}

type IconName = 'wave' | 'camera' | 'graph' | 'derivative' | 'points' | 'asymptote' | 'hint' | 'attach' | 'upload' | 'chevron' | 'trend' | 'target' | 'triangleUp' | 'triangleDown' | 'magnify';

function SvgIcon({ name }: { name: IconName }) {
  if (name === 'magnify') return <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'block' }}><circle cx="11" cy="11" r="7" /><path d="M9 11h4M11 9v4" /><path d="m20 20-4.35-4.35" /></svg>;
  if (name === 'camera') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 8h4l2-3h4l2 3h4v11H4z" /><circle cx="12" cy="13" r="4" /></svg>;
  if (name === 'attach') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" /></svg>;
  if (name === 'hint') return <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'block' }}><circle cx="12" cy="12" r="9.5" /><path d="M12 11v5" /><circle cx="12" cy="7.5" r="0.5" fill="currentColor" stroke="none" /></svg>;
  if (name === 'graph') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19V5" /><path d="M4 19h16" /><path d="M6 15c3-8 6 8 12-6" /></svg>;
  if (name === 'derivative') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 18c4-1 4-11 8-12" /><path d="M9 12h8" /><path d="M15 8l4 4-4 4" /></svg>;
  if (name === 'points') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="7" cy="16" r="2" /><circle cx="12" cy="8" r="2" /><circle cx="17" cy="16" r="2" /><path d="M7 16l5-8 5 8" /></svg>;
  if (name === 'asymptote') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 18c4-10 12-10 16 0" /><path d="M4 6h16" strokeDasharray="3 3" /></svg>;
  if (name === 'upload') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 16V4" /><path d="M7 9l5-5 5 5" /><path d="M5 16v3h14v-3" /></svg>;
  if (name === 'chevron') return <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>;
  if (name === 'trend') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 17l6-6 4 4 6-8" /><path d="M15 7h5v5" /></svg>;
  if (name === 'target') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" /><path d="M12 2v4M12 18v4M2 12h4M18 12h4" /></svg>;
  if (name === 'triangleUp') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"><path d="M12 5 20 19H4Z" /></svg>;
  if (name === 'triangleDown') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"><path d="M4 5h16l-8 14Z" /></svg>;
  return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>;
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error('Không đọc được ảnh.'));
    reader.readAsDataURL(file);
  });
}
