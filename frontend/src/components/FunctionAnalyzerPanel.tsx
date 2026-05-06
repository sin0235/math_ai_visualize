import { Fragment, useId, useMemo, useRef, useState } from 'react';
import { analyzeFunction, analyzeFunctionImage, type AnalyzeResponse } from '../api/client';
import { GeoGebraView } from './GeoGebraView';
import { KatexSpan, sympyToLatex } from './KatexSpan';
import type { MathScene } from '../types/scene';

interface FunctionAnalyzerPanelProps {
  initialExpression?: string;
  onOpenGuide?: () => void;
}

const EXAMPLES = [
  { label: 'Bậc 3', value: 'x^3 - 3*x + 2' },
  { label: 'Phân thức', value: '(x^2 - 1)/(x - 2)' },
  { label: 'Bậc 4', value: 'x^4 - 8*x^2' },
  { label: 'Căn', value: 'sqrt(x^2 + 1)' },
  { label: 'Mũ', value: 'exp(x)' },
];

export function FunctionAnalyzerPanel({ initialExpression = '', onOpenGuide }: FunctionAnalyzerPanelProps) {
  const [expression, setExpression] = useState(initialExpression);
  const [loading, setLoading] = useState(false);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function handleAnalyze() {
    const expr = expression.trim();
    if (!expr) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await analyzeFunction(expr);
      if (res.error) setError(res.error);
      else setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lỗi không xác định.');
    } finally {
      setLoading(false);
    }
  }

  async function handleImageChange(file?: File) {
    if (!file) return;
    setOcrLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await analyzeFunctionImage(await readFileAsDataUrl(file));
      if (res.ocr_expression) setExpression(res.ocr_expression);
      if (res.error) setError(res.error);
      else setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lỗi OCR không xác định.');
    } finally {
      setOcrLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
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

  return (
    <div className="fa2-panel">
      <div className="fa2-header">
        <div className="fa2-header-icon" aria-hidden="true"><SvgIcon name="wave" /></div>
        <div>
          <div className="fa2-header-title">Khảo sát hàm số</div>
          <div className="fa2-header-sub">Nhập hàm, xem đồ thị, đạo hàm, cực trị và tiệm cận</div>
        </div>
      </div>

      <div className="fa2-input-wrap">
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
        <input ref={fileInputRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => void handleImageChange(e.target.files?.[0])} />
        <button type="button" className="sp-btn-secondary" onClick={() => fileInputRef.current?.click()} disabled={loading || ocrLoading} aria-label="Chọn tệp ảnh">
          {ocrLoading ? <span className="sp-spinner" aria-hidden="true" /> : <SvgIcon name="attach" />}
        </button>
        <button id="fa-submit-btn" type="button" className="sp-btn-primary" onClick={() => void handleAnalyze()} disabled={loading || ocrLoading || !expression.trim()}>
          {loading ? <span className="sp-spinner" aria-hidden="true" /> : 'Phân tích'}
        </button>
      </div>

      <div className="sp-chips">
        {EXAMPLES.map((ex) => <button key={ex.value} type="button" className="sp-chip" onClick={() => setExpression(ex.value)}>{ex.label}</button>)}
      </div>

      {error && <div className="sp-error" role="alert">{error}</div>}
      {result && <AnalysisResult result={result} />}
    </div>
  );
}

function AnalysisResult({ result }: { result: AnalyzeResponse }) {
  return (
    <div className="fa2-result">
      <Section title="Đồ thị hàm số" icon="graph">
        <FunctionGraphSvg result={result} />
      </Section>

      <div className="fa2-summary-grid">
        {result.domain_latex && <SummaryCard label="Tập xác định" tex={result.domain_latex} />}
        {result.range_latex && <SummaryCard label="Tập giá trị" tex={result.range_latex} />}
      </div>

      <Section title="Đạo hàm và biến thiên" icon="derivative">
        <div className="fa2-formula-row"><KatexSpan tex="f'(x)=" className="fa2-label-mono fa2-label-katex" /><KatexSpan tex={result.derivative_latex || sympyToLatex(result.derivative || '')} className="fa2-katex" /></div>
        {result.second_derivative && <div className="fa2-formula-row"><KatexSpan tex="f''(x)=" className="fa2-label-mono fa2-label-katex" /><KatexSpan tex={result.second_derivative_latex || sympyToLatex(result.second_derivative)} className="fa2-katex" /></div>}
        <VariationTable rows={result.variation_table} />
      </Section>

      {(result.critical_points.length > 0 || result.inflection_points.length > 0) && (
        <Section title="Điểm đặc biệt" icon="points">
          <div className="fa2-extrema">
            {result.inflection_points.map((pt, i) => <PointBadge key={`ip-${i}`} label="Điểm uốn" tex={`(${sympyToLatex(pt.x_exact)},\\; ${sympyToLatex(pt.y)})`} kind="inflection" />)}
            {result.y_intercept !== null && <PointBadge label="Giao Oy" tex={`(0,\\; ${sympyToLatex(result.y_intercept)})`} kind="axis" />}
            {result.x_intercepts.map((xv, i) => <PointBadge key={`ox-${i}`} label="Giao Ox" tex={`(${sympyToLatex(xv)},\\; 0)`} kind="axis" />)}
          </div>
        </Section>
      )}

      {(result.concave_up_intervals.length > 0 || result.concave_down_intervals.length > 0 || result.horizontal_asymptotes.length > 0 || result.vertical_asymptotes.length > 0 || result.oblique_asymptote) && (
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

      {result.ocr_text && <div className="sp-info">OCR: {result.ocr_text}</div>}
      {result.warnings.length > 0 && <div className="sp-warnings">{result.warnings.map((w, i) => <div key={i} className="sp-warning">{w}</div>)}</div>}
    </div>
  );
}

function FunctionGraphSvg({ result }: { result: AnalyzeResponse }) {
  if (result.geogebra_commands.length > 0) {
    const scene = result.graph_scene ?? createFallbackGraphScene(result.expression);
    return (
      <div className="fa2-graph-card">
        <GeoGebraView
          commands={result.geogebra_commands}
          renderer="geogebra_2d"
          scene={scene}
          view={scene.view}
          embedded
        />
      </div>
    );
  }
  const data = result.graph_points || [];
  const graph = useMemo(() => buildSvgGraph(data, result), [data, result]);
  const svgId = useId();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const dragRef = useRef<{ pointerId: number; x: number; y: number } | null>(null);
  const [view, setView] = useState({ scale: 1, tx: 0, ty: 0 });
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
          {plotSpecialPoints(result, graph.project, SVG_WIDTH, SVG_HEIGHT, 28).map((point) => (
            <g key={point.key}>
              <circle cx={point.x} cy={point.y} r="5" className={`fa2-graph-point fa2-graph-point-${point.kind}`} />
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
    ...result.critical_points.map((cp, i) => ({ key: `cp-${i}`, kind: cp.kind, label: cp.kind === 'max' ? 'CĐ' : cp.kind === 'min' ? 'CT' : 'T', raw: { x: Number(cp.x), y: Number(cp.y) } })),
    ...result.inflection_points.map((pt, i) => ({ key: `ip-${i}`, kind: 'inflection', label: 'U', raw: { x: Number(pt.x), y: Number(pt.y) } })),
  ].filter((p) => Number.isFinite(p.raw.x) && Number.isFinite(p.raw.y)).map((p) => ({ ...p, ...project(p.raw) }));
  const occupied: Array<{ x: number; y: number }> = [];
  const candidates: Array<{ dx: number; dy: number; anchor: 'start' | 'middle' | 'end' }> = [
    { dx: 12, dy: -10, anchor: 'start' },
    { dx: 12, dy: 16, anchor: 'start' },
    { dx: -12, dy: -10, anchor: 'end' },
    { dx: -12, dy: 16, anchor: 'end' },
    { dx: 0, dy: -14, anchor: 'middle' },
    { dx: 0, dy: 20, anchor: 'middle' },
  ];
  return points.map((point) => {
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
    return { ...point, labelX, labelY, anchor: selected.anchor };
  });
}

function SummaryCard({ label, tex }: { label: string; tex: string }) {
  return <div className="fa2-summary-card"><span>{label}</span><KatexSpan tex={tex} /></div>;
}

function PointBadge({ label, tex, kind }: { label: string; tex: string; kind: string }) {
  return <div className={`fa2-ext fa2-ext-${kind}`}><div className="fa2-ext-body"><span className="fa2-ext-kind">{label}</span><KatexSpan tex={tex} className="fa2-ext-coords" /></div></div>;
}

function Asymptote({ label, tex }: { label: string; tex: string }) {
  return <div className="fa2-asym"><span className="fa2-asym-tag">{label}</span><KatexSpan tex={tex} /></div>;
}

function VariationTable({ rows }: { rows: AnalyzeResponse['variation_table'] }) {
  if (!rows || rows.length === 0) return null;
  const dynamicCols = rows.length * 2 - 1;
  return (
    <div className="bbt-wrap" style={{ '--bbt-cols': dynamicCols } as Record<string, number>}>
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
  const path = direction === 'up' ? 'M 8 34 L 92 8' : direction === 'down' ? 'M 8 8 L 92 34' : 'M 8 21 L 92 21';
  return (
    <svg viewBox="0 0 100 42" className={`bbt-stroke ${direction === 'up' ? 'bbt-up' : direction === 'down' ? 'bbt-down' : ''}`} aria-hidden="true">
      <defs>
        <marker id="bbt-arrow-head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
        </marker>
      </defs>
      <path d={path} fill="none" stroke="currentColor" strokeWidth="1.75" markerEnd="url(#bbt-arrow-head)" />
    </svg>
  );
}

function IntervalLine({ label, value, className }: { label: string; value: string; className: string }) {
  return <div className={`fa2-mono ${className}`}><span className="fa2-mono-label">{label}:</span><span className="fa2-mono-val">{value}</span></div>;
}

function Section({ title, icon, children }: { title: string; icon: IconName; children: React.ReactNode }) {
  return <div className="fa2-section"><div className="fa2-section-head"><span className="fa2-section-icon" aria-hidden="true"><SvgIcon name={icon} /></span><span className="fa2-section-title">{title}</span></div><div className="fa2-section-body">{children}</div></div>;
}

type IconName = 'wave' | 'camera' | 'graph' | 'derivative' | 'points' | 'asymptote' | 'hint' | 'attach';

function SvgIcon({ name }: { name: IconName }) {
  if (name === 'camera') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 8h4l2-3h4l2 3h4v11H4z" /><circle cx="12" cy="13" r="4" /></svg>;
  if (name === 'attach') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" /></svg>;
  if (name === 'hint') return <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'block' }}><circle cx="12" cy="12" r="9.5" /><path d="M12 11v5" /><circle cx="12" cy="7.5" r="0.5" fill="currentColor" stroke="none" /></svg>;
  if (name === 'graph') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19V5" /><path d="M4 19h16" /><path d="M6 15c3-8 6 8 12-6" /></svg>;
  if (name === 'derivative') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 18c4-1 4-11 8-12" /><path d="M9 12h8" /><path d="M15 8l4 4-4 4" /></svg>;
  if (name === 'points') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="7" cy="16" r="2" /><circle cx="12" cy="8" r="2" /><circle cx="17" cy="16" r="2" /><path d="M7 16l5-8 5 8" /></svg>;
  if (name === 'asymptote') return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 18c4-10 12-10 16 0" /><path d="M4 6h16" strokeDasharray="3 3" /></svg>;
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
