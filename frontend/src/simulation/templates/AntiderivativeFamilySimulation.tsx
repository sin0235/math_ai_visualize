import { useMemo, useState } from 'react';
import { KatexSpan } from '../../components/KatexSpan';
import { FormulaInput, PresetButtons, ResultCard, SliderInput } from '../runtime/SimulationPrimitives';
import { formatNumber, integrate, sampleFunction, validateBounds } from '../../utils/calculusNumerics';
import { numericalDerivative, parseUserFunction } from '../math/derivativeAnalysis';
import { RichGraph2D } from '../renderers/RichGraph2D';
import type { SamplePoint } from '../../utils/calculusNumerics';

type Props = { step: number; progress: number; freeMode?: boolean };

type State = {
  f: string;
  a: number;
  b: number;
  xAnchor: number;
  c: number;
  showFamily: boolean;
  nCompare: number;
};

const PRESETS = [
  { label: '2x', patch: { f: '2*x', a: -2, b: 2, xAnchor: 0, c: 0 } },
  { label: '$3x^2$', patch: { f: '3*x^2', a: -1.5, b: 1.5, xAnchor: 0, c: 1 } },
  { label: 'cos x', patch: { f: 'cos(x)', a: -6.3, b: 6.3, xAnchor: 0, c: 0 } },
  { label: 'e^x', patch: { f: 'exp(x)', a: -2, b: 2, xAnchor: 0, c: 0 } },
  { label: '1/x (x>0)', patch: { f: '1/x', a: 0.3, b: 4, xAnchor: 1, c: 0 } },
];

export function AntiderivativeFamilySimulation({ step, progress, freeMode = false }: Props) {
  const [state, setState] = useState<State>({
    f: '2*x',
    a: -2,
    b: 2,
    xAnchor: 0,
    c: 0,
    showFamily: true,
    nCompare: 5,
  });

  const model = useMemo(() => build(state, step, progress), [state, step, progress]);
  const canF = freeMode || step >= 1;
  const canAnchor = freeMode || step >= 2;
  const canC = freeMode || step >= 3;
  const canFamily = freeMode || step >= 4;

  return (
    <div className="csim-module-grid csim-module-grid-wide sim-deep-grid">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head">
            <strong>Họ nguyên hàm</strong>
            <span><KatexSpan tex={String.raw`F(x)+C`} /></span>
          </div>
          <FormulaInput label="f(x) = F'(x)" value={state.f} onChange={(f) => setState({ ...state, f })} disabled={!canF} />
          <div className={!canF ? 'is-step-locked' : undefined}>
            <PresetButtons presets={PRESETS} onApply={(p) => canF && setState((s) => ({ ...s, ...p.patch }))} />
          </div>
          <div className={`csim-two-cols${!canF ? ' is-step-locked' : ''}`}>
            <label className="csim-field"><span>a</span><input type="number" disabled={!canF} value={state.a} onChange={(e) => setState({ ...state, a: Number(e.target.value) })} /></label>
            <label className="csim-field"><span>b</span><input type="number" disabled={!canF} value={state.b} onChange={(e) => setState({ ...state, b: Number(e.target.value) })} /></label>
          </div>
          <SliderInput label={<>Mốc tích phân <KatexSpan tex="x_*" /></>} value={state.xAnchor} min={state.a} max={state.b} step={(state.b - state.a) / 200 || 0.01} onChange={(xAnchor) => setState({ ...state, xAnchor })} disabled={!canAnchor} />
          <SliderInput label={<>Hằng số <KatexSpan tex="C" /></>} value={state.c} min={-5} max={5} step={0.1} onChange={(c) => setState({ ...state, c })} disabled={!canC} />
          <SliderInput label="Số đường trong họ" value={state.nCompare} min={1} max={9} step={1} onChange={(nCompare) => setState({ ...state, nCompare })} disabled={!canFamily} />
          <label className={`csim-check${!canFamily ? ' is-step-locked' : ''}`}>
            <input type="checkbox" disabled={!canFamily} checked={state.showFamily} onChange={(e) => setState({ ...state, showFamily: e.target.checked })} />
            Hiện nhiều đường <KatexSpan tex="F+C_i" /> {!canFamily && '(bước 4)'}
          </label>
        </div>

        <ResultCard
          title="Kiểm chứng"
          error={model.error}
          formula={String.raw`F(x)=\int_{x_*}^{x} f(t)\,dt + C`}
          highlight={step >= 3}
          rows={[
            ['F(x) tại điểm giữa', formatNumber(model.fMid, 4)],
            ['$F^{\\prime}\\approx f$ (sai số lớn nhất)', formatNumber(model.derivErr, 5)],
            ['$\\Delta C$ giữa hai đường kề', formatNumber(model.deltaC, 3)],
            ['$\\int_a^b f(x)\\,dx$', formatNumber(model.signedArea, 4)],
          ]}
        />

        <div className="csim-card">
          <div className="csim-card-head"><strong>Ý nghĩa hình học</strong><span>Tịnh tiến thẳng đứng</span></div>
          <p className="sim-muted">
            Mọi nguyên hàm của cùng một f chỉ khác nhau một hằng số: đồ thị tịnh tiến theo phương Oy.
            Đạo hàm (hệ số góc) tại mỗi x giữ nguyên — các tiếp tuyến song song theo từng x cố định.
          </p>
        </div>
      </aside>

      <section className="csim-visual-stack">
        <RichGraph2D title={titles[step - 1] ?? titles[0]} curves={model.curves} markers={model.markers} />
        <div className="csim-card csim-step-copy">
          <strong>{titles[step - 1] ?? titles[0]}</strong>
          <p>{copies[step - 1] ?? copies[0]}</p>
          <KatexSpan tex={String.raw`\frac{d}{dx}\big(F(x)+C\big)=f(x)`} />
        </div>
      </section>
    </div>
  );
}

const titles = [
  'Bước 1 — Đồ thị hàm dưới dấu tích phân f',
  'Bước 2 — Dựng một nguyên hàm F bằng tích phân biến thiên',
  'Bước 3 — Họ F + C khi đổi hằng số',
  'Bước 4 — Kiểm chứng F′ ≈ f',
];

const copies = [
  'f là “tốc độ biến thiên”. Diện tích có hướng dưới đồ thị f liên quan đến sự thay đổi của nguyên hàm.',
  'Cố định mốc x_*, đặt F(x) = ∫_{x_*}^x f(t) dt. Đây là một nguyên hàm (khi f liên tục).',
  'Thêm C dịch chuyển đồ thị lên/xuống. Mọi đường trong họ có cùng hình dạng “nghiêng” theo f.',
  'So sánh đạo hàm số của F với f: sai số nhỏ chứng tỏ F đúng là nguyên hàm (trong giới hạn số).',
];

function build(state: State, step: number, progress: number) {
  const err = validateBounds(state.a, state.b);
  if (err) return blank(err);
  try {
    const f = parseUserFunction(state.f);
    const fPoints = sampleFunction(f, state.a, state.b, 300);
    const anchor = Math.min(state.b, Math.max(state.a, state.xAnchor));

    const F = (x: number, c: number) => {
      const base = x >= anchor
        ? integrate((t) => f.evaluate(t), anchor, x)
        : -integrate((t) => f.evaluate(t), x, anchor);
      return base + c;
    };

    const animatedC = step === 3 ? state.c * progress + (-state.c) * (1 - progress) * 0 : state.c;
    // On step 3, sweep C visually using progress across family
    const mainC = step === 3 ? state.c * (0.15 + 0.85 * progress) : state.c;

    const mainFPoints: SamplePoint[] = sampleFunction(
      { source: 'F', evaluate: (x) => F(x, mainC) },
      state.a,
      state.b,
      300,
    );

    const family: SamplePoint[][] = [];
    if (state.showFamily && step >= 3) {
      const n = state.nCompare;
      for (let i = 0; i < n; i += 1) {
        const t = n === 1 ? 0.5 : i / (n - 1);
        const ci = -4 + 8 * t;
        family.push(sampleFunction({ source: `F+${ci}`, evaluate: (x) => F(x, ci) }, state.a, state.b, 180));
      }
    }

    // derivative check
    let derivErr = 0;
    let samples = 0;
    const mid = (state.a + state.b) / 2;
    for (let i = 0; i < 40; i += 1) {
      const x = state.a + ((state.b - state.a) * (i + 0.5)) / 40;
      const dF = numericalDerivative({ source: 'F', evaluate: (t) => F(t, mainC) }, x);
      const fv = f.evaluate(x);
      if (Number.isFinite(dF) && Number.isFinite(fv)) {
        derivErr = Math.max(derivErr, Math.abs(dF - fv));
        samples += 1;
      }
    }

    const curves = [
      ...(step >= 1 ? [{ points: fPoints, className: 'csim-path-g', label: 'f(x)', dashed: true as const }] : []),
      ...(step >= 2 ? [{ points: mainFPoints, className: 'csim-path-f', label: 'F(x)+C' }] : []),
      ...family.slice(0, step >= 3 ? family.length : 0).map((points, i) => ({
        points,
        className: 'sim-family-curve',
        label: i === 0 ? 'Họ F+Cᵢ' : undefined,
        dashed: true as const,
      })),
    ];

    const signedArea = integrate((t) => f.evaluate(t), state.a, state.b);

    return {
      error: null as string | null,
      fMid: F(mid, mainC),
      derivErr: samples ? derivErr : NaN,
      deltaC: state.nCompare > 1 ? 8 / (state.nCompare - 1) : 0,
      signedArea,
      curves,
      markers: [
        { x: anchor, y: F(anchor, mainC), label: `x_*=${formatNumber(anchor, 2)}`, className: 'sim-marker' },
      ],
      animatedC,
    };
  } catch (e) {
    return blank(e instanceof Error ? e.message : 'Lỗi biểu thức');
  }
}

function blank(error: string) {
  return {
    error,
    fMid: NaN,
    derivErr: NaN,
    deltaC: NaN,
    signedArea: NaN,
    curves: [],
    markers: [],
    animatedC: 0,
  };
}
