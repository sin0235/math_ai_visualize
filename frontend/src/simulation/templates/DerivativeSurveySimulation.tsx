import { useMemo, useState } from 'react';
import { KatexSpan, MixedTextRenderer } from '../../components/KatexSpan';
import { FormulaInput, PresetButtons, ResultCard, SliderInput } from '../runtime/SimulationPrimitives';
import { formatNumber, sampleFunction, validateBounds } from '../../utils/calculusNumerics';
import {
  buildVariationTable,
  detectAsymptotes,
  findCriticalPoints,
  globalExtremaOnInterval,
  monotonicIntervals,
  numericalDerivative,
  parseUserFunction,
  sampleDerivative,
  secantLine,
  tangentLine,
} from '../math/derivativeAnalysis';
import { RichGraph2D } from '../renderers/RichGraph2D';

type Props = { step: number; progress: number; freeMode?: boolean };

type State = {
  f: string;
  a: number;
  b: number;
  x0: number;
  h: number;
  showFPrime: boolean;
  showAsymptotes: boolean;
};

const PRESETS: Array<{ label: string; patch: Partial<State> }> = [
  { label: '$x^3-3x$', patch: { f: 'x^3 - 3*x', a: -3, b: 3, x0: 1.2, h: 1.2 } },
  { label: '$x^2$', patch: { f: 'x^2', a: -2.5, b: 2.5, x0: 1, h: 1 } },
  { label: '$x^3$', patch: { f: 'x^3', a: -2, b: 2, x0: 0.8, h: 0.9 } },
  { label: '1/x', patch: { f: '1/x', a: -4, b: 4, x0: 1.5, h: 1.2, showAsymptotes: true } },
  { label: 'x + 1/x', patch: { f: 'x + 1/x', a: 0.3, b: 4, x0: 1.2, h: 0.8, showAsymptotes: true } },
  { label: 'sin x', patch: { f: 'sin(x)', a: -6.3, b: 6.3, x0: 1, h: 1.2 } },
  { label: 'e^x', patch: { f: 'exp(x)', a: -2, b: 2, x0: 0.4, h: 0.8 } },
];

export function DerivativeSurveySimulation({ step, progress, freeMode = false }: Props) {
  const [state, setState] = useState<State>({
    f: 'x^3 - 3*x',
    a: -3,
    b: 3,
    x0: 1.2,
    h: 1.2,
    showFPrime: true,
    showAsymptotes: false,
  });

  const model = useMemo(() => analyze(state, step, progress), [state, step, progress]);
  const canEditF = freeMode || step >= 1;
  const canEditH = freeMode || step <= 3;
  const canShowPrime = freeMode || step >= 4;
  const canBounds = freeMode || step >= 5;

  return (
    <div className="csim-module-grid csim-module-grid-wide sim-deep-grid">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head">
            <strong>Khảo sát hàm & đạo hàm</strong>
            <span>Cát tuyến → tiếp tuyến → BBT</span>
          </div>
          <FormulaInput label="$f(x)$" value={state.f} onChange={(f) => setState({ ...state, f })} disabled={!canEditF} />
          <div className={!canEditF ? 'is-step-locked' : undefined}>
            <PresetButtons presets={PRESETS} onApply={(p) => canEditF && setState((s) => ({ ...s, ...p.patch }))} />
          </div>
          <div className={`csim-two-cols${!canBounds ? ' is-step-locked' : ''}`}>
            <label className="csim-field">
              <span>a</span>
              <input type="number" disabled={!canBounds} value={state.a} onChange={(e) => setState({ ...state, a: Number(e.target.value) })} />
            </label>
            <label className="csim-field">
              <span>b</span>
              <input type="number" disabled={!canBounds} value={state.b} onChange={(e) => setState({ ...state, b: Number(e.target.value) })} />
            </label>
          </div>
          <SliderInput
            label={<>Điểm <KatexSpan tex="x_0" /></>}
            value={state.x0}
            min={state.a}
            max={state.b}
            step={(state.b - state.a) / 300 || 0.01}
            onChange={(x0) => setState({ ...state, x0 })}
          />
          {(freeMode || step <= 3) && (
            <SliderInput
              label={<>Bước cát tuyến <KatexSpan tex="h" /></>}
              value={model.effectiveH}
              min={0.05}
              max={2.5}
              step={0.01}
              onChange={(h) => setState({ ...state, h })}
              disabled={!canEditH && step > 2}
            />
          )}
          <label className={`csim-check${!canShowPrime ? ' is-step-locked' : ''}`}>
            <input type="checkbox" disabled={!canShowPrime} checked={state.showFPrime} onChange={(e) => setState({ ...state, showFPrime: e.target.checked })} />
            Hiện đồ thị <KatexSpan tex="f'(x)" /> {!canShowPrime && '(bước 4+)'}
          </label>
          <label className={`csim-check${!canShowPrime ? ' is-step-locked' : ''}`}>
            <input type="checkbox" disabled={!canShowPrime} checked={state.showAsymptotes} onChange={(e) => setState({ ...state, showAsymptotes: e.target.checked })} />
            Dò tiệm cận (số)
          </label>
        </div>

        <ResultCard
          title="Giá trị tại điểm"
          error={model.error}
          formula={String.raw`f'(x_0)=\lim_{h\to 0}\frac{f(x_0+h)-f(x_0)}{h}`}
          highlight={step >= 3}
          rows={[
            [<KatexSpan tex="x_0" />, formatNumber(state.x0, 3)],
            [<KatexSpan tex="f(x_0)" />, formatNumber(model.y0, 4)],
            [<><KatexSpan tex="h" /> (cát tuyến)</>, formatNumber(model.effectiveH, 3)],
            ['Hệ số góc cát tuyến', formatNumber(model.secantSlope, 4)],
            ['Hệ số góc tiếp tuyến $\\approx f^{\\prime}$', formatNumber(model.tangentSlope, 4)],
            ['$|m_{\\text{cát}}-m_{\\text{tiếp}}|$', formatNumber(model.slopeGap, 4)],
          ]}
        />

        {step >= 4 && !model.error && (
          <div className="csim-card">
            <div className="csim-card-head"><strong>Cực trị trên <KatexSpan tex="[a,b]" /></strong><span><KatexSpan tex="f'(x)=0" /> và đầu mút</span></div>
            <div className="sim-kv-list">
              {model.critical.map((c) => (
                <div key={`${c.x}-${c.kind}`} className="sim-kv-row">
                  <span>{c.kind}</span>
                  <strong>({formatNumber(c.x, 3)}; {formatNumber(c.y, 3)})</strong>
                </div>
              ))}
              {model.critical.length === 0 && <p className="sim-muted">Không tìm thấy điểm tới hạn nội tại (hoặc đạo hàm không đổi dấu).</p>}
              <div className="sim-kv-row"><span>GTLN trên [a,b]</span><strong>{formatNumber(model.extrema.max.y, 3)} tại x={formatNumber(model.extrema.max.x, 3)}</strong></div>
              <div className="sim-kv-row"><span>GTNN trên [a,b]</span><strong>{formatNumber(model.extrema.min.y, 3)} tại x={formatNumber(model.extrema.min.x, 3)}</strong></div>
            </div>
          </div>
        )}
      </aside>

      <section className="csim-visual-stack">
        <RichGraph2D
          title={stepTitle(step)}
          curves={model.curves}
          segments={model.segments}
          markers={model.markers}
          vLines={model.vLines}
          hLines={model.hLines}
          bands={model.bands}
        />

        {step >= 5 && !model.error && (
          <div className="csim-card sim-bbt-card">
            <div className="csim-card-head"><strong>Bảng biến thiên (rút gọn)</strong><span>Dấu <KatexSpan tex="f'(x)" /> theo khoảng</span></div>
            <div className="sim-bbt-scroll">
              <table className="sim-bbt-table">
                <thead>
                  <tr>
                    <th><KatexSpan tex="x" /></th>
                    {model.table.xs.map((x) => <th key={x}>{formatNumber(x, 2)}</th>)}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th><KatexSpan tex="f'(x)" /></th>
                    {model.table.mono.flatMap((iv, i) => {
                      const cells = [
                        <td key={`s-${i}`} className={iv.sign > 0 ? 'pos' : iv.sign < 0 ? 'neg' : ''}>
                          {iv.sign > 0 ? '+' : iv.sign < 0 ? '−' : '0'}
                        </td>,
                      ];
                      if (i < model.table.mono.length - 1 || true) {
                        /* point columns already in xs; mono is between points */
                      }
                      return cells;
                    })}
                  </tr>
                  <tr>
                    <th>Biến thiên</th>
                    {model.table.mono.map((iv, i) => (
                      <td key={`m-${i}`}>{iv.sign > 0 ? '↗' : iv.sign < 0 ? '↘' : '→'}</td>
                    ))}
                  </tr>
                  <tr>
                    <th><KatexSpan tex="f(x)" /></th>
                    {model.table.xs.map((x) => {
                      const y = model.evalF(x);
                      const crit = model.critical.find((c) => Math.abs(c.x - x) < 1e-4);
                      return <td key={`f-${x}`}>{formatNumber(y, 2)}{crit ? ` (${crit.kind})` : ''}</td>;
                    })}
                  </tr>
                </tbody>
              </table>
            </div>
            <ul className="sim-mono-list">
              {model.mono.map((iv) => (
                <li key={`${iv.from}-${iv.to}`}>
                  Trên ({formatNumber(iv.from, 2)}; {formatNumber(iv.to, 2)}): <strong>{iv.label}</strong>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="csim-card csim-step-copy">
          <strong><MixedTextRenderer text={stepTitle(step)} /></strong>
          <p><MixedTextRenderer text={stepCopy(step)} /></p>
          {step >= 3 && model.tangent && (
            <p className="sim-eq-line">Phương trình tiếp tuyến: <code>{model.tangent.equation}</code></p>
          )}
        </div>
      </section>
    </div>
  );
}

function analyze(state: State, step: number, progress: number) {
  const boundsError = validateBounds(state.a, state.b);
  if (boundsError) {
    return empty(boundsError);
  }
  try {
    const fn = parseUserFunction(state.f);
    const x0 = Math.min(state.b - 1e-6, Math.max(state.a + 1e-6, state.x0));
    // Animate h → small on step 2
    const effectiveH = step === 2
      ? Math.max(0.04, state.h * (1 - 0.92 * progress))
      : step >= 3
        ? Math.max(0.04, Math.min(state.h, 0.08))
        : state.h;

    const fPoints = sampleFunction(fn, state.a, state.b, 320);
    const fPrimePoints = sampleDerivative(fn, state.a, state.b, 320);
    const y0 = fn.evaluate(x0);
    const sec = secantLine(fn, x0, effectiveH);
    const tan = tangentLine(fn, x0);
    const critical = findCriticalPoints(fn, state.a, state.b);
    const mono = monotonicIntervals(fn, state.a, state.b);
    const extrema = globalExtremaOnInterval(fn, state.a, state.b);
    const asymptotes = state.showAsymptotes ? detectAsymptotes(fn, state.a, state.b) : { vertical: [], horizontal: null, oblique: null };
    const table = buildVariationTable(fn, state.a, state.b);

    const span = state.b - state.a;
    const linePad = span * 0.08;
    const xL = state.a - linePad;
    const xR = state.b + linePad;

    const curves = [
      { points: fPoints, className: 'csim-path-f', label: 'f(x)' },
      ...(state.showFPrime && step >= 4
        ? [{ points: fPrimePoints, className: 'csim-path-g', label: "f'(x)", dashed: true as const }]
        : []),
    ];

    const segments = [];
    if (step >= 1 && step <= 3 && Number.isFinite(sec.slope)) {
      segments.push({
        x1: xL,
        y1: sec.evaluate(xL),
        x2: xR,
        y2: sec.evaluate(xR),
        className: step >= 3 ? 'sim-secant is-fading' : 'sim-secant',
      });
    }
    if (step >= 3 && Number.isFinite(tan.slope)) {
      segments.push({
        x1: xL,
        y1: tan.evaluate(xL),
        x2: xR,
        y2: tan.evaluate(xR),
        className: 'sim-tangent',
      });
    }

    const markers = [
      { x: x0, y: y0, label: `A(${formatNumber(x0, 2)}; ${formatNumber(y0, 2)})`, className: 'sim-marker' },
    ];
    if (step <= 3 && Number.isFinite(sec.y1)) {
      markers.push({ x: sec.x1, y: sec.y1, label: 'B', className: 'sim-marker-secondary' });
    }
    if (step >= 4) {
      for (const c of critical) {
        markers.push({
          x: c.x,
          y: c.y,
          label: c.kind === 'cực đại' ? 'CĐ' : c.kind === 'cực tiểu' ? 'CT' : '•',
          className: c.kind === 'cực đại' ? 'sim-marker-max' : c.kind === 'cực tiểu' ? 'sim-marker-min' : 'sim-marker',
        });
      }
    }

    const bands = step >= 5
      ? mono.map((iv) => ({
          from: iv.from,
          to: iv.to,
          className: iv.sign > 0 ? 'sim-band-up' : iv.sign < 0 ? 'sim-band-down' : 'sim-band-flat',
        }))
      : [];

    const vLines = [
      ...(step >= 1 ? [{ x: x0, className: 'csim-marker-line', label: 'x_0' }] : []),
      ...asymptotes.vertical.map((x) => ({ x, className: 'sim-asymp-v', label: 'TC đứng' })),
    ];
    const hLines = [
      ...(asymptotes.horizontal !== null
        ? [{ y: asymptotes.horizontal, className: 'sim-asymp-h', label: 'TC ngang' }]
        : []),
    ];

    return {
      error: null as string | null,
      y0,
      effectiveH,
      secantSlope: sec.slope,
      tangentSlope: tan.slope,
      slopeGap: Math.abs(sec.slope - tan.slope),
      tangent: tan,
      critical,
      mono,
      extrema,
      table,
      curves,
      segments,
      markers,
      vLines,
      hLines,
      bands,
      evalF: (x: number) => fn.evaluate(x),
    };
  } catch (e) {
    return empty(e instanceof Error ? e.message : 'Biểu thức không hợp lệ.');
  }
}

function empty(error: string) {
  return {
    error,
    y0: NaN,
    effectiveH: NaN,
    secantSlope: NaN,
    tangentSlope: NaN,
    slopeGap: NaN,
    tangent: null as ReturnType<typeof tangentLine> | null,
    critical: [] as ReturnType<typeof findCriticalPoints>,
    mono: [] as ReturnType<typeof monotonicIntervals>,
    extrema: { min: { x: NaN, y: NaN }, max: { x: NaN, y: NaN } },
    table: { xs: [] as number[], crit: [], mono: [] as ReturnType<typeof monotonicIntervals> },
    curves: [],
    segments: [],
    markers: [],
    vLines: [],
    hLines: [],
    bands: [],
    evalF: (_x: number) => NaN,
  };
}

function stepTitle(step: number) {
  return [
    'Bước 1 — Đồ thị và điểm khảo sát',
    'Bước 2 — Cát tuyến khi $h\\to0$',
    'Bước 3 — Tiếp tuyến và $f^{\\prime}(x_0)$',
    'Bước 4 — Liên hệ $f$ và $f^{\\prime}$, điểm tới hạn',
    'Bước 5 — Khoảng đồng/nghịch biến',
    'Bước 6 — Bảng biến thiên & GTLN/GTNN',
  ][Math.max(0, Math.min(5, step - 1))];
}

function stepCopy(step: number) {
  return [
    'Chọn hàm và điểm $x_0$. Quan sát hình dạng đồ thị trước khi nói về đạo hàm.',
    'Cát tuyến qua $A(x_0,f(x_0))$ và $B(x_0+h,f(x_0+h))$ có hệ số góc $\\dfrac{f(x_0+h)-f(x_0)}{h}$. Cho $h$ nhỏ dần.',
    'Giới hạn khi $h\\to0$ là $f^{\\prime}(x_0)$ khi tồn tại. So sánh tiếp tuyến với cát tuyến.',
    'Đồ thị $f^{\\prime}$ cho biết tốc độ biến thiên. Nghiệm $f^{\\prime}=0$ là ứng viên cực trị.',
    '$f^{\\prime}>0$ cho khoảng đồng biến; $f^{\\prime}<0$ cho khoảng nghịch biến.',
    'Tổng hợp dòng $x$, dấu $f^{\\prime}$, mũi tên biến thiên và giá trị $f$ trên đoạn $[a,b]$.',
  ][Math.max(0, Math.min(5, step - 1))];
}
