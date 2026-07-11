import { useMemo, useState } from 'react';
import { KatexSpan, MixedTextRenderer } from '../../components/KatexSpan';
import { FormulaInput, PresetButtons, ResultCard, SliderInput } from '../runtime/SimulationPrimitives';
import { formatNumber, sampleFunction, validateBounds } from '../../utils/calculusNumerics';
import { classifyContinuity, parseFn, twoSidedLimit } from '../math/limitsAnalysis';
import { RichGraph2D } from '../renderers/RichGraph2D';
import type { SamplePoint } from '../../utils/calculusNumerics';

type Props = { step: number; progress: number };

type Mode = 'smooth' | 'hole' | 'jump' | 'pole' | 'sinx_x' | 'custom';

type State = {
  mode: Mode;
  expr: string;
  a: number;
  b: number;
  x0: number;
  /** Giá trị gán lại f(x0) khi khử gián đoạn */
  patchValue: number;
  usePatch: boolean;
  /** jump: f = x if x<x0 else x+k */
  jumpK: number;
};

const HS = [0.5, 0.2, 0.1, 0.05, 0.01, 0.001];

export function LimitsContinuitySimulation({ step, progress }: Props) {
  const [state, setState] = useState<State>({
    mode: 'hole',
    expr: '(x^2-1)/(x-1)',
    a: -1,
    b: 3,
    x0: 1,
    patchValue: 2,
    usePatch: false,
    jumpK: 1.5,
  });

  const model = useMemo(() => build(state, step, progress), [state, step, progress]);

  return (
    <div className="csim-module-grid csim-module-grid-wide sim-deep-grid">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head"><strong>Giới hạn & liên tục</strong><span>Bảng giá trị · một phía</span></div>
          <label className="csim-field">
            <span>Mẫu hàm</span>
            <select
              value={state.mode}
              onChange={(e) => {
                const mode = e.target.value as Mode;
                const patch = modePatch(mode);
                setState((s) => ({ ...s, mode, ...patch }));
              }}
            >
              <option value="hole">Hố khử được</option>
              <option value="jump">Nhảy (từng khúc)</option>
              <option value="pole">Giới hạn vô cực</option>
              <option value="sinx_x">Giới hạn lượng giác</option>
              <option value="smooth">Hàm trơn</option>
              <option value="custom">Tùy chỉnh biểu thức</option>
            </select>
          </label>
          {state.mode === 'custom' && (
            <FormulaInput label="$f(x)$" value={state.expr} onChange={(expr) => setState({ ...state, expr })} />
          )}
          {state.mode === 'jump' && (
            <SliderInput label="Độ nhảy $k$: $f=x$ nếu $x<a$, $f=x+k$ nếu $x\\ge a$" value={state.jumpK} min={-3} max={3} step={0.1} onChange={(jumpK) => setState({ ...state, jumpK })} />
          )}
          <div className="csim-two-cols">
            <label className="csim-field"><span>Cửa sổ a</span><input type="number" value={state.a} onChange={(e) => setState({ ...state, a: Number(e.target.value) })} /></label>
            <label className="csim-field"><span>Cửa sổ b</span><input type="number" value={state.b} onChange={(e) => setState({ ...state, b: Number(e.target.value) })} /></label>
          </div>
          <SliderInput label={<>Điểm <KatexSpan tex="a" /> (giới hạn tại a)</>} value={state.x0} min={state.a} max={state.b} step={(state.b - state.a) / 200 || 0.01} onChange={(x0) => setState({ ...state, x0 })} />
          <label className="csim-check">
            <input type="checkbox" checked={state.usePatch} onChange={(e) => setState({ ...state, usePatch: e.target.checked })} />
            Gán lại f(a) = c (thử khử gián đoạn)
          </label>
          {state.usePatch && (
            <SliderInput label="c = f(a)" value={state.patchValue} min={-5} max={5} step={0.1} onChange={(patchValue) => setState({ ...state, patchValue })} />
          )}
          <PresetButtons
            presets={[
              { label: 'Hố tại 1', patch: { mode: 'hole' as Mode, expr: '(x^2-1)/(x-1)', x0: 1, a: -1, b: 3, usePatch: false } },
              { label: 'sinx/x → 1', patch: { mode: 'sinx_x' as Mode, expr: 'sin(x)/x', x0: 0, a: -3, b: 3, usePatch: false } },
              { label: '1/x tại 0', patch: { mode: 'pole' as Mode, expr: '1/x', x0: 0, a: -3, b: 3, usePatch: false } },
            ]}
            onApply={(p) => setState((s) => ({ ...s, ...p.patch, ...modePatch((p.patch.mode as Mode) ?? s.mode) }))}
          />
        </div>

        <ResultCard
          title="Giới hạn tại a"
          error={model.error}
          formula={String.raw`\lim_{x\to a}f(x)`}
          highlight={step >= 3}
          rows={[
            [<KatexSpan tex="a" />, formatNumber(state.x0, 3)],
            ['lim trái', formatNumber(model.left, 4)],
            ['lim phải', formatNumber(model.right, 4)],
            ['Hai phía L', model.L === null ? 'không tồn tại' : formatNumber(model.L, 4)],
            [<KatexSpan tex="f(a)" />, formatNumber(model.fa, 4)],
            ['Phân loại', model.kind],
          ]}
        />

        <div className="csim-card">
          <div className="csim-card-head"><strong>Kết luận</strong><span>{model.kind}</span></div>
          <p className="sim-muted">{model.detail}</p>
        </div>
      </aside>

      <section className="csim-visual-stack">
        <RichGraph2D
          title={titles[step - 1] ?? 'Giới hạn'}
          curves={[{ points: model.points, className: 'csim-path-f', label: 'f(x)' }]}
          markers={model.markers}
          vLines={[{ x: state.x0, className: 'csim-marker-line', label: 'a' }]}
          hLines={model.L !== null && step >= 3 ? [{ y: model.L, className: 'sim-asymp-h', label: 'y=L' }] : []}
        />

        <div className="csim-card">
          <div className="csim-card-head"><strong>Bảng tiến tới a</strong><span>h → 0</span></div>
          <div className="sim-bbt-scroll">
            <table className="sim-bbt-table">
              <thead>
                <tr>
                  <th>h</th>
                  <th>x=a−h</th>
                  <th>f(a−h)</th>
                  <th>x=a+h</th>
                  <th>f(a+h)</th>
                </tr>
              </thead>
              <tbody>
                {model.tableRows.map((row) => (
                  <tr key={row.h} className={row.highlight ? 'sim-row-active' : ''}>
                    <td>{formatNumber(row.h, 4)}</td>
                    <td>{formatNumber(row.xl, 4)}</td>
                    <td>{formatNumber(row.yl, 4)}</td>
                    <td>{formatNumber(row.xr, 4)}</td>
                    <td>{formatNumber(row.yr, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="csim-card csim-step-copy">
          <strong><MixedTextRenderer text={titles[step - 1] ?? titles[0]} /></strong>
          <p><MixedTextRenderer text={copies[step - 1] ?? copies[0]} /></p>
          <ul className="sim-mono-list">
            <li>lim tồn tại ⇔ lim trái = lim phải (hữu hạn).</li>
            <li>Liên tục tại a ⇔ lim = f(a) (f xác định tại a).</li>
            <li>Hố: lim có, f(a) sai/không có — gán f(a)=L để khử.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

function modePatch(mode: Mode): Partial<State> {
  switch (mode) {
    case 'hole':
      return { expr: '(x^2-1)/(x-1)', x0: 1, a: -1, b: 3 };
    case 'jump':
      return { expr: 'x', x0: 0, a: -2, b: 2, jumpK: 1.5 };
    case 'pole':
      return { expr: '1/x', x0: 0, a: -3, b: 3 };
    case 'sinx_x':
      return { expr: 'sin(x)/x', x0: 0, a: -4, b: 4 };
    case 'smooth':
      return { expr: 'x^2', x0: 1, a: -1, b: 3 };
    default:
      return {};
  }
}

function build(state: State, step: number, progress: number) {
  const err = validateBounds(state.a, state.b);
  if (err) return blank(err);
  try {
    const base = state.mode === 'jump'
      ? null
      : parseFn(state.mode === 'custom' || state.mode === 'smooth' || state.mode === 'hole' || state.mode === 'pole' || state.mode === 'sinx_x' ? state.expr : state.expr);

    const evaluate = (x: number) => {
      if (state.usePatch && Math.abs(x - state.x0) < 1e-12) return state.patchValue;
      if (state.mode === 'jump') {
        return x < state.x0 ? x : x + state.jumpK;
      }
      if (state.mode === 'sinx_x' && Math.abs(x) < 1e-12) return state.usePatch ? state.patchValue : NaN;
      return base ? base.evaluate(x) : NaN;
    };

    const fn = { source: 'f', evaluate };
    const { left, right, fa: faRaw, L } = twoSidedLimit(fn, state.x0, HS);
    const fa = state.usePatch ? state.patchValue : faRaw;
    const cls = classifyContinuity(
      {
        source: 'f',
        evaluate: (x) => (state.usePatch && Math.abs(x - state.x0) < 1e-12 ? state.patchValue : evaluate(x)),
      },
      state.x0,
    );

    // sample with gap at pole/hole
    const rawPoints = sampleFunction({ source: 'f', evaluate }, state.a, state.b, 360);
    const points: SamplePoint[] = rawPoints.map((p) => {
      if (state.mode === 'jump' && Math.abs(p.x - state.x0) < (state.b - state.a) / 400) {
        return { ...p, valid: false, y: NaN };
      }
      if (!Number.isFinite(p.y) || Math.abs(p.y) > 40) return { ...p, valid: false, y: NaN };
      return p;
    });

    const visibleHs = step <= 2 ? HS.slice(0, Math.max(2, Math.ceil(HS.length * (0.35 + 0.65 * progress)))) : HS;
    const tableRows = HS.map((h, i) => {
      const xl = state.x0 - h;
      const xr = state.x0 + h;
      return {
        h,
        xl,
        xr,
        yl: evaluate(xl),
        yr: evaluate(xr),
        highlight: visibleHs.includes(h) && i === visibleHs.length - 1,
      };
    });

    const markers = [];
    if (Number.isFinite(fa)) markers.push({ x: state.x0, y: fa, label: 'f(a)', className: 'sim-marker' });
    if (L !== null && step >= 3) markers.push({ x: state.x0, y: L, label: 'L', className: 'sim-marker-secondary' });
    if (Number.isFinite(left.estimate) && step >= 2) {
      markers.push({ x: state.x0 - 0.001, y: left.estimate, label: 'lim⁻', className: 'sim-marker-min' });
    }
    if (Number.isFinite(right.estimate) && step >= 2) {
      markers.push({ x: state.x0 + 0.001, y: right.estimate, label: 'lim⁺', className: 'sim-marker-max' });
    }

    // override kind if patch makes continuous
    let kind = cls.kind;
    let detail = cls.detail;
    if (state.usePatch && L !== null && Math.abs(state.patchValue - L) < 0.05 * Math.max(1, Math.abs(L))) {
      kind = 'liên tục';
      detail = 'Đã gán f(a)=L — hàm trở nên liên tục tại a (mô hình số).';
    }

    return {
      error: null as string | null,
      points,
      markers,
      left: left.estimate,
      right: right.estimate,
      L,
      fa,
      kind,
      detail,
      tableRows,
    };
  } catch (e) {
    return blank(e instanceof Error ? e.message : 'Lỗi biểu thức');
  }
}

function blank(error: string) {
  return {
    error,
    points: [] as SamplePoint[],
    markers: [],
    left: NaN,
    right: NaN,
    L: null as number | null,
    fa: NaN,
    kind: 'không xác định',
    detail: error,
    tableRows: [] as Array<{ h: number; xl: number; xr: number; yl: number; yr: number; highlight: boolean }>,
  };
}

const titles = [
  'Bước 1 — Chọn hàm và điểm $a$',
  'Bước 2 — Bảng giá trị hai phía khi $h\\to0$',
  'Bước 3 — So sánh giới hạn trái và phải',
  'Bước 4 — So với $f(a)$: liên tục hay gián đoạn?',
  'Bước 5 — Khử gián đoạn nếu có thể',
  'Bước 6 — Phân loại: khử được, nhảy hoặc vô hạn',
];

const copies = [
  'Giới hạn mô tả xu hướng của $f(x)$ khi $x\\to a$, không nhất thiết bằng $f(a)$.',
  'Thu nhỏ $h$: nếu $f(a\\pm h)$ ổn định quanh $L$ thì có cơ sở dự đoán giới hạn bằng $L$.',
  'Hai giới hạn một phía phải bằng nhau. Gián đoạn nhảy có hai phía khác nhau; gián đoạn vô hạn làm $|f(x)|$ tăng không giới hạn.',
  'Ba điều kiện liên tục: $f(a)$ xác định, $\\lim_{x\\to a}f(x)$ tồn tại và giới hạn bằng $f(a)$.',
  'Với hố, đặt $f(a)=L$. Gián đoạn nhảy hoặc vô hạn không thể khử bằng cách đổi một điểm.',
  'Đặt đúng tên loại gián đoạn để chọn phương pháp xử lý.',
];
