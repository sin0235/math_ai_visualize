import { useMemo, useState } from 'react';
import { KatexSpan, MixedTextRenderer } from '../../components/KatexSpan';
import { SliderInput } from '../runtime/SimulationPrimitives';
import { formatNumber } from '../../utils/calculusNumerics';
import {
  degToRad,
  formatAngleLabel,
  normalizeAngleRad,
  radToDeg,
  sampleTrigWave,
} from '../../utils/trigonometryNumerics';
import { RichGraph2D } from '../renderers/RichGraph2D';

type Props = { step: number; progress: number };

type FnKey = 'sin' | 'cos' | 'tan';

type State = {
  fn: FnKey;
  m: number;
  /** hiển thị nghiệm trong [0, 2π] hoặc [-2π, 2π] */
  window: '0-2pi' | '-2pi-2pi';
  showGeneral: boolean;
};

const TAU = Math.PI * 2;

export function TrigEquationsSimulation({ step, progress }: Props) {
  const [state, setState] = useState<State>({
    fn: 'sin',
    m: 0.5,
    window: '0-2pi',
    showGeneral: true,
  });

  const model = useMemo(() => solve(state, step, progress), [state, step, progress]);

  return (
    <div className="csim-module-grid csim-module-grid-wide sim-deep-grid">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head"><strong>Phương trình lượng giác</strong><span>sin / cos / tan = m</span></div>
          <label className="csim-field">
            <span>Dạng</span>
            <select value={state.fn} onChange={(e) => setState({ ...state, fn: e.target.value as FnKey, m: clampM(e.target.value as FnKey, state.m) })}>
              <option value="sin">sin x = m</option>
              <option value="cos">cos x = m</option>
              <option value="tan">tan x = m</option>
            </select>
          </label>
          <SliderInput
            label={<>m = {formatNumber(state.m, 3)}</>}
            value={state.m}
            min={state.fn === 'tan' ? -3 : -1}
            max={state.fn === 'tan' ? 3 : 1}
            step={0.05}
            onChange={(m) => setState({ ...state, m: clampM(state.fn, m) })}
          />
          <label className="csim-field">
            <span>Cửa sổ nghiệm</span>
            <select value={state.window} onChange={(e) => setState({ ...state, window: e.target.value as State['window'] })}>
              <option value="0-2pi">Một chu kỳ dương</option>
              <option value="-2pi-2pi">Hai chu kỳ quanh 0</option>
            </select>
          </label>
          <label className="csim-check">
            <input type="checkbox" checked={state.showGeneral} onChange={(e) => setState({ ...state, showGeneral: e.target.checked })} />
            Hiện họ nghiệm tổng quát
          </label>
          <div className="sim-preset-row">
            {[0, 0.5, Math.SQRT1_2, Math.sqrt(3) / 2, 1, -0.5].map((m) => (
              <button key={m} type="button" className="csim-chip" onClick={() => setState({ ...state, m: clampM(state.fn, m) })}>
                m={formatNumber(m, 3)}
              </button>
            ))}
          </div>
        </div>

        <div className="csim-card">
          <div className="csim-card-head"><strong>Kết quả</strong><span>{model.status}</span></div>
          <div className="sim-kv-list">
            <div className="sim-kv-row"><span>Phương trình</span><strong><KatexSpan tex={model.eqTex} /></strong></div>
            <div className="sim-kv-row highlight"><span>Số nghiệm (cửa sổ)</span><strong>{model.solutions.length}</strong></div>
            {model.solutions.map((s, i) => (
              <div key={i} className="sim-kv-row">
                <span><KatexSpan tex={`x_${i + 1}`} /></span>
                <strong><KatexSpan tex={`${formatAngleLabel(s, false)}\\;(${formatNumber(radToDeg(s), 1)}^\\circ)`} /></strong>
              </div>
            ))}
            {state.showGeneral && model.general.map((g) => (
              <div key={g} className="sim-kv-row"><span>Họ</span><strong><KatexSpan tex={g} /></strong></div>
            ))}
          </div>
        </div>
      </aside>

      <section className="csim-visual-stack">
        <div className="sim-trig-eq-layout">
          <UnitCircleSolutions
            fn={state.fn}
            m={state.m}
            solutions={model.baseAngles}
            progress={step >= 2 ? Math.min(1, step === 2 ? progress : 1) : 0}
          />
          <RichGraph2D
            title="Đồ thị & đường y = m"
            curves={[
              { points: model.wave, className: 'csim-path-f', label: `${state.fn} x` },
            ]}
            hLines={[{ y: state.m, className: 'sim-asymp-h', label: `y=${formatNumber(state.m, 2)}` }]}
            markers={model.graphMarkers}
            vLines={model.fn === 'tan' ? model.asympV : []}
          />
        </div>

        <div className="csim-card csim-step-copy">
          <strong><MixedTextRenderer text={titles[step - 1] ?? titles[0]} /></strong>
          <p><MixedTextRenderer text={copies[step - 1] ?? copies[0]} /></p>
          <ul className="sim-mono-list">
            <li><KatexSpan tex={String.raw`\sin x=m,\ |m|\le1:\quad x=(-1)^k\alpha+k\pi`} /></li>
            <li><KatexSpan tex={String.raw`\cos x=m:\quad x=\pm\alpha+2k\pi`} /></li>
            <li><KatexSpan tex={String.raw`\tan x=m:\quad x=\alpha+k\pi`} /></li>
          </ul>
        </div>
      </section>
    </div>
  );
}

function clampM(fn: FnKey, m: number) {
  if (fn === 'tan') return Math.min(3, Math.max(-3, m));
  return Math.min(1, Math.max(-1, m));
}

function solve(state: State, step: number, progress: number) {
  const { fn, m, window } = state;
  const eqTex = fn === 'sin' ? String.raw`\sin x = ${fmt(m)}` : fn === 'cos' ? String.raw`\cos x = ${fmt(m)}` : String.raw`\tan x = ${fmt(m)}`;

  let status = 'Có nghiệm';
  let baseAngles: number[] = [];
  let general: string[] = [];

  if (fn !== 'tan' && Math.abs(m) > 1 + 1e-12) {
    status = 'Vô nghiệm (|m|>1)';
    baseAngles = [];
  } else if (fn === 'sin') {
    if (Math.abs(m) > 1) {
      status = 'Vô nghiệm';
    } else {
      const a = Math.asin(m);
      baseAngles = uniqueAngles([a, Math.PI - a]);
      general = [String.raw`x=(-1)^k(${fmt(a)})+k\pi`, String.raw`\alpha=\arcsin(m)\approx ${fmt(a)}`];
    }
  } else if (fn === 'cos') {
    const a = Math.acos(m);
    baseAngles = uniqueAngles([a, -a]);
    general = [String.raw`x=\pm(${fmt(a)})+2k\pi`, String.raw`\alpha=\arccos(m)\approx ${fmt(a)}`];
  } else {
    const a = Math.atan(m);
    baseAngles = [normalizeAngleRad(a)];
    general = [String.raw`x=${fmt(a)}+k\pi`, String.raw`\alpha=\arctan(m)\approx ${fmt(a)}`];
  }

  const [w0, w1] = window === '0-2pi' ? [0, TAU] : [-TAU, TAU];
  const solutions = expandSolutions(fn, baseAngles, w0, w1);
  const showCount = step <= 2 ? Math.max(0, Math.ceil(solutions.length * (step === 1 ? 0 : progress))) : solutions.length;
  const shown = solutions.slice(0, Math.max(step >= 2 ? 1 : 0, showCount));

  const waveMin = w0;
  const waveMax = w1;
  const wave = sampleTrigWave(fn === 'tan' ? 'tan' : fn, waveMin, waveMax, 480).map((p) => ({
    x: p.x,
    y: p.valid ? p.y : NaN,
    valid: p.valid && Math.abs(p.y) < 6,
  }));

  const graphMarkers = shown.map((x, i) => ({
    x,
    y: fn === 'sin' ? Math.sin(x) : fn === 'cos' ? Math.cos(x) : Math.tan(x),
    label: `x${i + 1}`,
    className: 'sim-marker',
  }));

  const asympV = fn === 'tan'
    ? [-3, -1, 1, 3].map((k) => ({ x: Math.PI / 2 + k * Math.PI, className: 'sim-asymp-v', label: 'TC' }))
      .filter((v) => v.x >= w0 && v.x <= w1)
    : [];

  return {
    eqTex,
    status,
    baseAngles,
    solutions: shown,
    general: state.showGeneral && step >= 4 ? general : [],
    wave,
    graphMarkers,
    asympV,
    fn,
  };
}

function expandSolutions(fn: FnKey, base: number[], w0: number, w1: number) {
  const out: number[] = [];
  if (base.length === 0) return out;
  if (fn === 'sin') {
    // (-1)^k α + kπ
    const a = base[0];
    for (let k = -8; k <= 8; k += 1) {
      const x = ((-1) ** k) * a + k * Math.PI;
      if (x >= w0 - 1e-9 && x <= w1 + 1e-9) out.push(x);
    }
  } else if (fn === 'cos') {
    const a = Math.abs(base[0]);
    for (let k = -6; k <= 6; k += 1) {
      for (const s of [a, -a]) {
        const x = s + 2 * k * Math.PI;
        if (x >= w0 - 1e-9 && x <= w1 + 1e-9) out.push(x);
      }
    }
  } else {
    const a = base[0];
    for (let k = -8; k <= 8; k += 1) {
      const x = a + k * Math.PI;
      if (x >= w0 - 1e-9 && x <= w1 + 1e-9) out.push(x);
    }
  }
  return uniqueAngles(out).sort((l, r) => l - r);
}

function uniqueAngles(xs: number[]) {
  const out: number[] = [];
  for (const x of xs) {
    if (out.some((y) => Math.abs(y - x) < 1e-6)) continue;
    out.push(x);
  }
  return out;
}

function fmt(n: number) {
  return formatNumber(n, 3).replace(',', '.');
}

function UnitCircleSolutions({
  fn,
  m,
  solutions,
  progress,
}: {
  fn: FnKey;
  m: number;
  solutions: number[];
  progress: number;
}) {
  const R = 100;
  const cx = 120;
  const cy = 120;
  const shown = solutions.slice(0, Math.max(0, Math.ceil(solutions.length * Math.max(progress, 0.01))));
  // reference line y=m for sin → horizontal; x=m for cos
  return (
    <div className="csim-card">
      <div className="csim-card-head"><strong>Đường tròn lượng giác</strong><span>nghiệm góc</span></div>
      <svg viewBox="0 0 240 240" className="sim-unit-eq-svg">
        <circle cx={cx} cy={cy} r={R} className="sim-unit-circle" />
        <line x1={cx - R - 10} x2={cx + R + 10} y1={cy} y2={cy} className="sim-unit-axis" />
        <line x1={cx} x2={cx} y1={cy - R - 10} y2={cy + R + 10} className="sim-unit-axis" />
        {fn === 'sin' && Math.abs(m) <= 1 && (
          <line x1={cx - R} x2={cx + R} y1={cy - m * R} y2={cy - m * R} className="sim-unit-ref" />
        )}
        {fn === 'cos' && Math.abs(m) <= 1 && (
          <line x1={cx + m * R} x2={cx + m * R} y1={cy - R} y2={cy + R} className="sim-unit-ref" />
        )}
        {shown.map((ang, i) => {
          const x = cx + Math.cos(ang) * R;
          const y = cy - Math.sin(ang) * R;
          return (
            <g key={i}>
              <line x1={cx} y1={cy} x2={x} y2={y} className="sim-unit-ray" />
              <circle cx={x} cy={y} r={5} className="sim-unit-point" />
              <text x={x + 8} y={y - 8} className="sim-unit-lbl">{i + 1}</text>
            </g>
          );
        })}
      </svg>
      <p className="sim-muted">
        {fn === 'sin' && 'Giao đường y = m với đường tròn → các góc nghiệm (mod chu kỳ).'}
        {fn === 'cos' && 'Giao đường x = m với đường tròn.'}
        {fn === 'tan' && 'tan = sin/cos: hướng tia có sin/cos = m (tránh cos=0).'}
      </p>
    </div>
  );
}

const titles = [
  'Bước 1 — Chọn $\\sin x$, $\\cos x$ hoặc $\\tan x$ bằng $m$',
  'Bước 2 — Đánh dấu nghiệm trên đường tròn',
  'Bước 3 — Giao điểm trên đồ thị $y=m$',
  'Bước 4 — Họ nghiệm tổng quát',
  'Bước 5 — Đổi cửa sổ và đếm số nghiệm',
];

const copies = [
  '$|m|>1$ khiến phương trình sin/cos vô nghiệm; phương trình tan luôn có nghiệm với mọi $m$.',
  'Mỗi nghiệm là một hướng từ gốc trên đường tròn đơn vị.',
  'Đồ thị sóng cắt đường ngang $y=m$ tại các hoành độ nghiệm.',
  'Tham số $k\\in\\mathbb{Z}$ sinh vô hạn nghiệm; đề thi thường giới hạn trên một đoạn.',
  'Đổi $[0,2\\pi]$ và $[-2\\pi,2\\pi]$ để quan sát chu kỳ lặp.',
];
