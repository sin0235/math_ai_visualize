import { useMemo, useState } from 'react';
import { KatexSpan } from '../../components/KatexSpan';
import { SliderInput } from '../../components/calculus/AreaBetweenCurvesSimulation';
import { formatNumber } from '../../utils/calculusNumerics';
import { RichGraph2D } from '../renderers/RichGraph2D';
import type { SamplePoint } from '../../utils/calculusNumerics';

type Props = { step: number; progress: number };

type Kind = 'arithmetic' | 'geometric' | 'recursive' | 'compound';

type State = {
  kind: Kind;
  u1: number;
  d: number;
  q: number;
  n: number;
  /** recursive u_{n+1}=p*u_n+r */
  p: number;
  r: number;
  /** compound: A(1+i)^n */
  principal: number;
  rate: number;
};

export function SequencesLabSimulation({ step, progress }: Props) {
  const [state, setState] = useState<State>({
    kind: 'arithmetic',
    u1: 3,
    d: 2,
    q: 1.5,
    n: 12,
    p: 0.5,
    r: 1,
    principal: 100,
    rate: 0.08,
  });

  const model = useMemo(() => build(state, step, progress), [state, step, progress]);

  return (
    <div className="csim-module-grid csim-module-grid-wide sim-deep-grid">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head"><strong>Dãy số · CSC · CSN</strong><span>Lớp 11</span></div>
          <label className="csim-field">
            <span>Loại dãy</span>
            <select value={state.kind} onChange={(e) => setState({ ...state, kind: e.target.value as Kind })}>
              <option value="arithmetic">Cấp số cộng (CSC)</option>
              <option value="geometric">Cấp số nhân (CSN)</option>
              <option value="recursive">Truy hồi uₙ₊₁ = p·uₙ + r</option>
              <option value="compound">Lãi kép A(1+i)ⁿ</option>
            </select>
          </label>

          {state.kind === 'arithmetic' && (
            <>
              <SliderInput label={<>u₁</>} value={state.u1} min={-10} max={20} step={0.5} onChange={(u1) => setState({ ...state, u1 })} />
              <SliderInput label={<>Công sai d</>} value={state.d} min={-5} max={5} step={0.25} onChange={(d) => setState({ ...state, d })} />
            </>
          )}
          {state.kind === 'geometric' && (
            <>
              <SliderInput label={<>u₁</>} value={state.u1} min={-5} max={10} step={0.25} onChange={(u1) => setState({ ...state, u1 })} />
              <SliderInput label={<>Công bội q</>} value={state.q} min={-2.5} max={2.5} step={0.05} onChange={(q) => setState({ ...state, q })} />
            </>
          )}
          {state.kind === 'recursive' && (
            <>
              <SliderInput label={<>u₁</>} value={state.u1} min={-5} max={10} step={0.5} onChange={(u1) => setState({ ...state, u1 })} />
              <SliderInput label="p" value={state.p} min={-1.5} max={1.5} step={0.05} onChange={(p) => setState({ ...state, p })} />
              <SliderInput label="r" value={state.r} min={-5} max={5} step={0.25} onChange={(r) => setState({ ...state, r })} />
            </>
          )}
          {state.kind === 'compound' && (
            <>
              <SliderInput label="Vốn A₀" value={state.principal} min={10} max={500} step={10} onChange={(principal) => setState({ ...state, principal })} />
              <SliderInput label="Lãi suất i (năm)" value={state.rate} min={0.01} max={0.25} step={0.005} onChange={(rate) => setState({ ...state, rate })} />
            </>
          )}
          <SliderInput label="Số hạng hiển thị N" value={state.n} min={3} max={40} step={1} onChange={(n) => setState({ ...state, n })} />
        </div>

        <div className="csim-card">
          <div className="csim-card-head"><strong>Công thức</strong><span>{model.formulaLabel}</span></div>
          <p className="sim-eq-line"><KatexSpan tex={model.formulaTex} /></p>
          <div className="sim-kv-list">
            <div className="sim-kv-row"><span>u_N</span><strong>{formatNumber(model.uN, 4)}</strong></div>
            <div className="sim-kv-row highlight"><span>Tổng S_N</span><strong>{formatNumber(model.sN, 4)}</strong></div>
            {model.extra.map(([k, v]) => (
              <div key={k} className="sim-kv-row"><span>{k}</span><strong>{v}</strong></div>
            ))}
          </div>
        </div>
      </aside>

      <section className="csim-visual-stack">
        <RichGraph2D
          title={stepTitles[step - 1] ?? 'Dãy số'}
          curves={[
            { points: model.stemPoints, className: 'csim-path-g', label: 'u_n', dashed: true },
          ]}
          markers={model.markers}
          segments={model.stems}
        />

        <div className="csim-card">
          <div className="csim-card-head"><strong>Bảng số hạng</strong><span>n = 1…{model.visibleN}</span></div>
          <div className="sim-bbt-scroll">
            <table className="sim-bbt-table">
              <thead>
                <tr>
                  <th>n</th>
                  <th>u_n</th>
                  <th>S_n (cộng dồn)</th>
                </tr>
              </thead>
              <tbody>
                {model.rows.map((row) => (
                  <tr key={row.n} className={row.n === model.visibleN ? 'sim-row-active' : ''}>
                    <td>{row.n}</td>
                    <td>{formatNumber(row.u, 4)}</td>
                    <td>{formatNumber(row.s, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="csim-card">
          <div className="csim-card-head"><strong>Biểu đồ cột u_n</strong></div>
          <div className="sim-hist" aria-hidden="true">
            {model.rows.map((row) => {
              const maxAbs = Math.max(1, ...model.rows.map((r) => Math.abs(r.u)));
              const h = (Math.abs(row.u) / maxAbs) * 140;
              return (
                <div key={row.n} className="sim-hist-col">
                  <div className="sim-hist-bar" style={{ height: `${h}px`, background: row.u < 0 ? '#dc2626' : undefined }} />
                  <span className="sim-hist-label">{row.n}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="csim-card csim-step-copy">
          <strong>{stepTitles[step - 1] ?? stepTitles[0]}</strong>
          <p>{stepCopies[step - 1] ?? stepCopies[0]}</p>
        </div>
      </section>
    </div>
  );
}

function build(state: State, step: number, progress: number) {
  const N = state.n;
  const visibleN = step <= 2 ? Math.max(2, Math.ceil(N * (0.25 + 0.75 * progress))) : N;
  const terms: number[] = [];
  for (let n = 1; n <= N; n += 1) {
    terms.push(termAt(state, n));
  }
  let s = 0;
  const rows = terms.map((u, i) => {
    s += u;
    return { n: i + 1, u, s };
  }).slice(0, visibleN);

  const fullSum = terms.reduce((a, b) => a + b, 0);
  const markers = rows.map((row) => ({
    x: row.n,
    y: row.u,
    label: row.n === visibleN ? `u_${row.n}` : undefined,
    className: 'sim-marker',
  }));
  const stems = rows.map((row) => ({
    x1: row.n,
    y1: 0,
    x2: row.n,
    y2: row.u,
    className: 'sim-secant',
  }));
  const stemPoints: SamplePoint[] = rows.map((row) => ({ x: row.n, y: row.u, valid: true }));

  const meta = formulas(state, N, terms[N - 1], fullSum);

  return {
    rows,
    visibleN,
    markers,
    stems,
    stemPoints,
    uN: terms[N - 1],
    sN: fullSum,
    ...meta,
  };
}

function termAt(state: State, n: number): number {
  if (state.kind === 'arithmetic') return state.u1 + (n - 1) * state.d;
  if (state.kind === 'geometric') return state.u1 * state.q ** (n - 1);
  if (state.kind === 'compound') return state.principal * (1 + state.rate) ** n;
  // recursive
  let u = state.u1;
  for (let i = 2; i <= n; i += 1) u = state.p * u + state.r;
  return u;
}

function formulas(state: State, N: number, uN: number, sN: number) {
  if (state.kind === 'arithmetic') {
    const closed = N * (2 * state.u1 + (N - 1) * state.d) / 2;
    return {
      formulaLabel: 'CSC',
      formulaTex: String.raw`u_n=u_1+(n-1)d,\quad S_n=\frac{n}{2}(2u_1+(n-1)d)`,
      extra: [
        ['S_N (công thức)', formatNumber(closed, 4)],
        ['|S_ct − S_cộng|', formatNumber(Math.abs(closed - sN), 6)],
      ] as Array<[string, string]>,
    };
  }
  if (state.kind === 'geometric') {
    const q = state.q;
    const closed = Math.abs(q - 1) < 1e-12
      ? N * state.u1
      : state.u1 * (1 - q ** N) / (1 - q);
    return {
      formulaLabel: 'CSN',
      formulaTex: String.raw`u_n=u_1 q^{n-1},\quad S_n=u_1\frac{1-q^n}{1-q}\ (q\neq 1)`,
      extra: [
        ['S_N (công thức)', formatNumber(closed, 4)],
        ['|q|>1?', Math.abs(q) > 1 ? 'dãy |u| tăng' : Math.abs(q) < 1 ? 'dãy |u| → 0 (nếu u₁ cố định)' : '|q|=1'],
      ] as Array<[string, string]>,
    };
  }
  if (state.kind === 'compound') {
    return {
      formulaLabel: 'Lãi kép',
      formulaTex: String.raw`A_n=A_0(1+i)^n`,
      extra: [
        ['A_N', formatNumber(uN, 2)],
        ['Lãi A_N−A₀', formatNumber(uN - state.principal, 2)],
      ] as Array<[string, string]>,
    };
  }
  return {
    formulaLabel: 'Truy hồi',
    formulaTex: String.raw`u_{n+1}=p u_n+r`,
    extra: [
      ['u_N', formatNumber(uN, 4)],
      ['Điểm bất động r/(1−p) (p≠1)', Math.abs(state.p - 1) < 1e-9 ? '—' : formatNumber(state.r / (1 - state.p), 4)],
    ] as Array<[string, string]>,
  };
}

const stepTitles = [
  'Bước 1 — Chọn loại dãy và tham số',
  'Bước 2 — Sinh các số hạng trên trục n',
  'Bước 3 — Bảng u_n và tổng cộng dồn',
  'Bước 4 — Đối chiếu công thức đóng S_n',
  'Bước 5 — Ứng dụng: tăng trưởng / lãi kép / hội tụ',
];

const stepCopies = [
  'CSC: cộng thêm d. CSN: nhân q. Truy hồi: mỗi số hạng từ số trước. Lãi kép là CSN với q=1+i.',
  'Biểu đồ “stem”: mỗi n gắn một giá trị u_n. Quan sát đường thẳng (CSC) vs mũ (CSN).',
  'S_n = u_1+…+u_n. So sánh tốc độ tăng tổng.',
  'CSC/CSN có công thức S_n gọn — kiểm tra sai số với cộng từng số hạng.',
  '|q|<1 ⇒ CSN triệt tiêu; lãi kép |q|>1 ⇒ tăng. Điểm bất động truy hồi: u=p u+r.',
];
