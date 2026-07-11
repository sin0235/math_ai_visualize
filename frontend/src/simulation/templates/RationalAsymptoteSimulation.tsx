import { useMemo, useState } from 'react';
import { KatexSpan, MixedTextRenderer } from '../../components/KatexSpan';
import { FormulaInput, PresetButtons, ResultCard, SliderInput } from '../runtime/SimulationPrimitives';
import { formatNumber, validateBounds } from '../../utils/calculusNumerics';
import {
  findCriticalPoints,
  monotonicIntervals,
  numericalDerivative,
} from '../math/derivativeAnalysis';
import { analyzeRational, sampleRational } from '../math/rationalAsymptotes';
import { RichGraph2D } from '../renderers/RichGraph2D';

type Props = { step: number; progress: number; freeMode?: boolean };

type State = {
  num: string;
  den: string;
  a: number;
  b: number;
  x0: number;
  showOblique: boolean;
  showFPrimeSign: boolean;
};

const PRESETS: Array<{ label: string; patch: Partial<State> }> = [
  { label: '$\\dfrac{x^2-1}{x-1}$ · hố', patch: { num: 'x^2-1', den: 'x-1', a: -3, b: 4, x0: 2 } },
  { label: '$\\dfrac{2x+1}{x-2}$ · ngang', patch: { num: '2*x+1', den: 'x-2', a: -2, b: 6, x0: 0 } },
  { label: '$\\dfrac{x^2+1}{x-1}$ · xiên', patch: { num: 'x^2+1', den: 'x-1', a: -3, b: 5, x0: 2 } },
  { label: '$\\dfrac{x}{x^2-1}$ · hai TC', patch: { num: 'x', den: 'x^2-1', a: -4, b: 4, x0: 0.5 } },
  { label: '$\\dfrac{x^3-x}{x^2+1}$', patch: { num: 'x^3-x', den: 'x^2+1', a: -4, b: 4, x0: 1 } },
  { label: '$\\dfrac{1}{x}$', patch: { num: '1', den: 'x', a: -5, b: 5, x0: 1.5 } },
];

export function RationalAsymptoteSimulation({ step, progress, freeMode = false }: Props) {
  const [state, setState] = useState<State>({
    num: 'x^2+1',
    den: 'x-1',
    a: -3,
    b: 5,
    x0: 2,
    showOblique: true,
    showFPrimeSign: true,
  });

  const model = useMemo(() => build(state, step, progress), [state, step, progress]);
  const canPQ = freeMode || step >= 1;
  const canX0 = freeMode || step >= 4;
  const canOblique = freeMode || step >= 3;
  const canPrime = freeMode || step >= 5;

  return (
    <div className="csim-module-grid csim-module-grid-wide sim-deep-grid">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head">
            <strong>Hàm hữu tỉ & tiệm cận</strong>
            <span><KatexSpan tex={String.raw`f=\frac{P}{Q}`} /></span>
          </div>
          <FormulaInput label="$P(x)$ tử" value={state.num} onChange={(num) => setState({ ...state, num })} disabled={!canPQ} />
          <FormulaInput label="$Q(x)$ mẫu" value={state.den} onChange={(den) => setState({ ...state, den })} disabled={!canPQ} />
          <div className={!canPQ ? 'is-step-locked' : undefined}>
            <PresetButtons presets={PRESETS} onApply={(p) => canPQ && setState((s) => ({ ...s, ...p.patch }))} />
          </div>
          <div className={`csim-two-cols${!canPQ ? ' is-step-locked' : ''}`}>
            <label className="csim-field"><span>a</span><input type="number" disabled={!canPQ} value={state.a} onChange={(e) => setState({ ...state, a: Number(e.target.value) })} /></label>
            <label className="csim-field"><span>b</span><input type="number" disabled={!canPQ} value={state.b} onChange={(e) => setState({ ...state, b: Number(e.target.value) })} /></label>
          </div>
          <SliderInput
            label={<>Điểm khảo sát <KatexSpan tex="x_0" /></>}
            value={state.x0}
            min={state.a}
            max={state.b}
            step={(state.b - state.a) / 300 || 0.01}
            onChange={(x0) => setState({ ...state, x0 })}
            disabled={!canX0}
          />
          <label className={`csim-check${!canOblique ? ' is-step-locked' : ''}`}>
            <input type="checkbox" disabled={!canOblique} checked={state.showOblique} onChange={(e) => setState({ ...state, showOblique: e.target.checked })} />
            Hiện tiệm cận xiên (nếu có)
          </label>
          <label className={`csim-check${!canPrime ? ' is-step-locked' : ''}`}>
            <input type="checkbox" disabled={!canPrime} checked={state.showFPrimeSign} onChange={(e) => setState({ ...state, showFPrimeSign: e.target.checked })} />
            Tô khoảng đồng/nghịch biến {!canPrime && '(bước 5)'}
          </label>
        </div>

        <ResultCard
          title="Phân tích tiệm cận"
          error={model.error}
          formula={String.raw`f(x)=\frac{P(x)}{Q(x)}`}
          highlight={step >= 3}
          rows={[
            ['TC đứng (x=…)', model.verticalText],
            ['TC ngang y=…', model.horizontalText],
            ['TC xiên', model.obliqueText],
            ['Hố (lỗ) có thể', model.holesText],
            [<KatexSpan tex="f(x_0)" />, formatNumber(model.y0, 4)],
            [<KatexSpan tex="f'(x_0)" />, formatNumber(model.dy0, 4)],
          ]}
        />

        <div className="csim-card">
          <div className="csim-card-head"><strong>Ghi chú thuật toán</strong><span>số + quy tắc bậc</span></div>
          <ul className="sim-mono-list">
            {model.notes.map((n) => <li key={n}><MixedTextRenderer text={n} /></li>)}
            {model.notes.length === 0 && <li>Nhập P, Q đa thức để dò nghiệm mẫu và hành vi vô cùng.</li>}
          </ul>
        </div>

        {step >= 5 && !model.error && (
          <div className="csim-card">
            <div className="csim-card-head"><strong>Cực trị (số)</strong><span>trên (a,b) tránh cực</span></div>
            <div className="sim-kv-list">
              {model.critical.map((c) => (
                <div key={c.x} className="sim-kv-row">
                  <span>{c.kind}</span>
                  <strong>({formatNumber(c.x, 3)}; {formatNumber(c.y, 3)})</strong>
                </div>
              ))}
              {model.critical.length === 0 && <p className="sim-muted">Không thấy điểm tới hạn nội tại trong cửa sổ.</p>}
            </div>
          </div>
        )}
      </aside>

      <section className="csim-visual-stack">
        <RichGraph2D
          title={titles[step - 1] ?? 'Hàm hữu tỉ'}
          curves={model.curves}
          markers={model.markers}
          vLines={model.vLines}
          hLines={model.hLines}
          segments={model.segments}
          bands={model.bands}
          yPadFactor={0.12}
        />
        <div className="csim-card csim-step-copy">
          <strong><MixedTextRenderer text={titles[step - 1] ?? titles[0]} /></strong>
          <p><MixedTextRenderer text={copies[step - 1] ?? copies[0]} /></p>
          <ul className="sim-mono-list">
            <li>TC đứng: <KatexSpan tex="Q(x)=0" /> nhưng <KatexSpan tex="P(x)\\ne0" /> sau rút gọn.</li>
            <li>Hố: nhân tử chung triệt tiêu — gián đoạn khử được.</li>
            <li>TC ngang / xiên: so sánh bậc P và Q (ở đây ước lượng bằng hành vi |x| lớn).</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

function build(state: State, step: number, progress: number) {
  const boundsError = validateBounds(state.a, state.b);
  if (boundsError) return blank(boundsError);
  try {
    const rat = analyzeRational(state.num, state.den, { a: state.a, b: state.b });
    const skip = [...rat.vertical.map((v) => v.x), ...rat.holes];
    const points = sampleRational(rat.f, state.a, state.b, 420, skip);
    // reveal asymptotes progressively
    const showV = step >= 2;
    const showH = step >= 3;
    const showO = step >= 3 && state.showOblique && rat.oblique;
    const showBands = step >= 5 && state.showFPrimeSign;

    const y0 = rat.f.evaluate(state.x0);
    const dy0 = numericalDerivative(rat.f, state.x0);

    // critical on subintervals avoiding poles
    const critical = step >= 5 ? findCriticalPoints(rat.f, state.a, state.b).filter((c) => Number.isFinite(c.y) && Math.abs(c.y) < 60) : [];
    const mono = showBands ? monotonicIntervals(rat.f, state.a, state.b) : [];

    const curves = [
      { points, className: 'csim-path-f', label: 'f(x)=P/Q' },
    ];

    // animate drawing of oblique line
    const segments = [];
    if (showO && rat.oblique) {
      const t = step === 3 ? progress : 1;
      const x1 = state.a;
      const x2 = state.a + (state.b - state.a) * Math.max(0.15, t);
      segments.push({
        x1,
        y1: rat.oblique.m * x1 + rat.oblique.b,
        x2,
        y2: rat.oblique.m * x2 + rat.oblique.b,
        className: 'sim-asymp-oblique',
      });
    }

    const vLines = [
      ...(showV ? rat.vertical.map((v) => ({ x: v.x, className: 'sim-asymp-v', label: `x=${formatNumber(v.x, 2)}` })) : []),
      ...(step >= 2 ? rat.holes.map((h) => ({ x: h, className: 'sim-hole-line', label: 'hố' })) : []),
      { x: state.x0, className: 'csim-marker-line', label: 'x_0' },
    ];
    const hLines = showH && rat.horizontal !== null
      ? [{ y: rat.horizontal, className: 'sim-asymp-h', label: `y=${formatNumber(rat.horizontal, 2)}` }]
      : [];

    const markers = [
      ...(Number.isFinite(y0) ? [{ x: state.x0, y: y0, label: 'f(x_0)', className: 'sim-marker' }] : []),
      ...rat.holes.map((h) => {
        // hole y limit from nearby
        const yl = rat.f.evaluate(h - 1e-3);
        const yr = rat.f.evaluate(h + 1e-3);
        const y = Number.isFinite(yl) ? yl : yr;
        return { x: h, y: Number.isFinite(y) ? y : 0, label: '○ hố', className: 'sim-marker-hole' };
      }),
      ...critical.map((c) => ({
        x: c.x,
        y: c.y,
        label: c.kind === 'cực đại' ? 'CĐ' : c.kind === 'cực tiểu' ? 'CT' : '•',
        className: c.kind === 'cực đại' ? 'sim-marker-max' : 'sim-marker-min',
      })),
    ];

    const bands = mono.map((iv) => ({
      from: iv.from,
      to: iv.to,
      className: iv.sign > 0 ? 'sim-band-up' : iv.sign < 0 ? 'sim-band-down' : 'sim-band-flat',
    }));

    return {
      error: null as string | null,
      notes: rat.notes,
      verticalText: rat.vertical.length ? rat.vertical.map((v) => formatNumber(v.x, 3)).join('; ') : 'không trong cửa sổ',
      horizontalText: rat.horizontal === null ? 'không / không rõ' : formatNumber(rat.horizontal, 3),
      obliqueText: rat.oblique
        ? `y = ${formatNumber(rat.oblique.m, 3)}x + ${formatNumber(rat.oblique.b, 3)}`
        : 'không / không rõ',
      holesText: rat.holes.length ? rat.holes.map((h) => formatNumber(h, 3)).join('; ') : 'không',
      y0,
      dy0,
      critical,
      curves,
      markers,
      vLines,
      hLines,
      segments,
      bands,
    };
  } catch (e) {
    return blank(e instanceof Error ? e.message : 'Biểu thức không hợp lệ');
  }
}

function blank(error: string) {
  return {
    error,
    notes: [] as string[],
    verticalText: '—',
    horizontalText: '—',
    obliqueText: '—',
    holesText: '—',
    y0: NaN,
    dy0: NaN,
    critical: [] as ReturnType<typeof findCriticalPoints>,
    curves: [],
    markers: [],
    vLines: [],
    hLines: [],
    segments: [],
    bands: [],
  };
}

const titles = [
  'Bước 1 — Nhập $P$, $Q$ và cửa sổ đồ thị',
  'Bước 2 — Nghiệm mẫu: tiệm cận đứng và hố',
  'Bước 3 — Hành vi vô cùng: ngang hoặc xiên',
  'Bước 4 — Đọc đồ thị gần các đường tiệm cận',
  'Bước 5 — Dấu $f^{\\prime}$ và cực trị cục bộ',
  'Bước 6 — Tổng hợp khảo sát hàm hữu tỉ',
];

const copies = [
  'Tách tử/mẫu giúp máy dò nghiệm $Q(x)=0$ và so sánh bậc. Chọn preset để thấy đủ ba loại tiệm cận.',
  'Nếu $Q(x_0)=0$ và $P(x_0)\\ne0$ thì nhánh tiến tới $\\pm\\infty$. Nếu cả hai triệt tiêu thì nghi ngờ có hố.',
  '$\\deg P<\\deg Q$ cho tiệm cận $y=0$; hai bậc bằng nhau cho $y=L$; $\\deg P=\\deg Q+1$ cho tiệm cận xiên.',
  'Đồ thị không cắt tiệm cận đứng; có thể cắt tiệm cận ngang hoặc xiên. Quan sát hai phía mỗi cực.',
  'Tránh lân cận cực khi tìm $f^{\\prime}(x)=0$. Nền xanh biểu thị đồng biến, nền đỏ biểu thị nghịch biến.',
  'Tổng hợp tập xác định, tiệm cận, giao trục, cực trị, bảng biến thiên và phác đồ thị.',
];
