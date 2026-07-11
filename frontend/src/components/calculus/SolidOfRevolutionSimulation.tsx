import { useMemo, useState, type ReactNode } from 'react';
import { KatexSpan } from '../KatexSpan';
import { compileExpression } from '../../utils/calculusExpression';
import { clamp, domainWarningFor, formatNumber, integrate, sampleFunction, safeEval, validateBounds } from '../../utils/calculusNumerics';
import { CalculusGraph2D } from './CalculusGraph2D';
import { RevolutionThreeView } from './CalculusThreeViews';
import { BoundsInput, FormulaInput, PresetButtons, ResultCard, SliderInput } from '../../simulation/runtime/SimulationPrimitives';

interface Props {
  step: number;
  progress: number;
  freeMode?: boolean;
}

type Axis = 'Ox' | 'Oy';
type Method = 'disk' | 'washer' | 'shell';

type State = {
  f: string;
  g: string;
  useWasher: boolean;
  a: number;
  b: number;
  sliceX: number;
  axis: Axis;
  n: number;
};

const SOLID_PRESETS: Array<{ label: string; patch: Partial<State> }> = [
  { label: 'Disk Ox', patch: { f: 'sqrt(x)', g: '0', useWasher: false, a: 0, b: 4, sliceX: 2, axis: 'Ox', n: 36 } },
  { label: 'Washer Ox', patch: { f: 'sqrt(x)', g: 'x/2', useWasher: true, a: 0, b: 4, sliceX: 2, axis: 'Ox', n: 36 } },
  { label: 'Shell $Oy$ · $x^2$', patch: { f: 'x^2', g: '0', useWasher: false, a: 0, b: 2, sliceX: 1, axis: 'Oy', n: 40 } },
  { label: 'Shell Oy · 1-x', patch: { f: '1-x', g: '0', useWasher: false, a: 0, b: 1, sliceX: 0.4, axis: 'Oy', n: 36 } },
  { label: 'Shell miền kẹp', patch: { f: '2-x', g: 'x', useWasher: true, a: 0, b: 1, sliceX: 0.5, axis: 'Oy', n: 40 } },
];

export function SolidOfRevolutionSimulation({ step, progress, freeMode = false }: Props) {
  const [state, setState] = useState<State>({
    f: 'sqrt(x)',
    g: 'x/2',
    useWasher: false,
    a: 0,
    b: 4,
    sliceX: 2,
    axis: 'Ox',
    n: 36,
  });
  const method: Method = state.axis === 'Oy' ? 'shell' : state.useWasher ? 'washer' : 'disk';
  const computed = useMemo(() => computeSolid(state, method), [state, method]);
  // So sánh song song disk Ox vs shell Oy cùng f,g,a,b (bước 5)
  const altAxis: Axis = state.axis === 'Ox' ? 'Oy' : 'Ox';
  const altMethod: Method = altAxis === 'Oy' ? 'shell' : state.useWasher ? 'washer' : 'disk';
  const altComputed = useMemo(
    () => computeSolid({ ...state, axis: altAxis, a: Math.max(0, state.a) }, altMethod),
    [state, altAxis, altMethod],
  );
  const sweep = (step === 2 ? progress : step > 2 ? 1 : 0) * Math.PI * 2;
  const sweepRatio = clamp(sweep / (Math.PI * 2), 0, 1);
  const sweptVolume = computed.volume * sweepRatio;
  const visibleDisks = step >= 4 ? Math.ceil(state.n * Math.min(1, step === 4 ? progress : 1)) : 0;
  const diskSum = computed.partialSumAt?.(visibleDisks) ?? NaN;
  const safeSliceX = clamp(state.sliceX, state.a, state.b);
  const canEditSetup = freeMode || step >= 1;
  const canSlice = freeMode || step >= 3;
  const canN = freeMode || step >= 4;
  const showCompare = freeMode || step >= 5;

  return (
    <div className="csim-module-grid csim-module-grid-wide">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head">
            <strong>Khối tròn xoay</strong>
            <span>{methodLabel(method)}</span>
          </div>
          <FormulaInput label="$f(x)$" value={state.f} onChange={(f) => setState({ ...state, f })} disabled={!canEditSetup} />
          <label className={`csim-check${!canEditSetup ? ' is-step-locked' : ''}`}>
            <input
              type="checkbox"
              disabled={!canEditSetup}
              checked={state.useWasher}
              onChange={(e) => setState({ ...state, useWasher: e.target.checked })}
            />
            {state.axis === 'Oy'
              ? <>Miền giữa <KatexSpan tex="f" /> và <KatexSpan tex="g" /> (shell)</>
              : <>Washer với <KatexSpan tex="g(x)" /></>}
          </label>
          {state.useWasher && <FormulaInput label="$g(x)$" value={state.g} onChange={(g) => setState({ ...state, g })} disabled={!canEditSetup} />}
          <div className={!canEditSetup ? 'is-step-locked' : undefined}>
            <PresetButtons presets={SOLID_PRESETS} onApply={(preset) => canEditSetup && setState((current) => ({ ...current, ...preset.patch }))} />
          </div>
          <BoundsInput
            a={state.a}
            b={state.b}
            disabled={!canEditSetup}
            onChange={(patch) => setState((current) => ({
              ...current,
              ...patch,
              sliceX: clamp(current.sliceX, patch.a ?? current.a, patch.b ?? current.b),
            }))}
          />
          <label className={`csim-field${!canEditSetup ? ' is-step-locked' : ''}`}>
            <span>Trục quay</span>
            <select
              value={state.axis}
              disabled={!canEditSetup}
              onChange={(e) => {
                const axis = e.target.value as Axis;
                setState({
                  ...state,
                  axis,
                  a: axis === 'Oy' ? Math.max(0, state.a) : state.a,
                });
              }}
            >
              <option value="Ox">Ox — Disk / Washer</option>
              <option value="Oy">Oy — Shell (vỏ trụ)</option>
            </select>
          </label>
          {state.axis === 'Oy' && state.a < 0 && (
            <p className="sim-muted">Shell quanh Oy với x&lt;0: dùng |x| làm bán kính vỏ (mô hình |x|).</p>
          )}
          <SliderInput
            label={<>Vị trí lát / vỏ tại <KatexSpan tex="x" /></>}
            value={safeSliceX}
            min={state.a}
            max={state.b}
            step={(state.b - state.a) / 200 || 0.01}
            onChange={(sliceX) => setState({ ...state, sliceX })}
            disabled={!canSlice}
          />
          <SliderInput
            label={<>Số lát <KatexSpan tex="n" /></>}
            value={state.n}
            min={6}
            max={120}
            step={1}
            onChange={(n) => setState({ ...state, n })}
            disabled={!canN}
          />
        </div>

        <ResultCard
          title="Thể tích"
          error={computed.error}
          formula={computed.formula}
          highlight={step >= 4}
          rows={[
            [step >= 4 ? 'Cộng dồn lát/vỏ' : 'Cộng dồn phần đã quét', formatNumber(step >= 4 ? diskSum : sweptVolume)],
            ['Tổng Riemann', formatNumber(computed.riemannSum)],
            ['Thể tích V', formatNumber(computed.volume)],
            ['Sai số |Riemann − V|', formatNumber(Math.abs(computed.riemannSum - computed.volume))],
            [method === 'shell' ? 'Bán kính vỏ |x|' : 'Bán kính ngoài', formatNumber(computed.outerRadius)],
            [method === 'shell' ? 'Chiều cao vỏ h(x)' : 'Bán kính trong', formatNumber(computed.innerRadius)],
            [method === 'shell' ? 'Diện tích “mặt” vỏ 2πrh' : 'Diện tích lát A(x)', formatNumber(computed.sliceArea)],
          ]}
        />

        <div className="csim-card">
          <div className="csim-card-head"><strong>Phương pháp</strong><span>{methodLabel(method)}</span></div>
          <ul className="sim-mono-list">
            {method === 'shell' ? (
              <>
                <li>Quay quanh <strong>Oy</strong>: dùng vỏ trụ (cylindrical shells).</li>
                <li>Vỏ tại x có bán kính |x|, chiều cao h(x)=|f−g| (hoặc f nếu g=0).</li>
                <li><KatexSpan tex={String.raw`V=\int_a^b 2\pi |x|\,h(x)\,dx`} /></li>
                <li>Lát “đứng” song song Oy — khác disk (⊥ Ox).</li>
              </>
            ) : (
              <>
                <li>Lát cắt ⊥ Ox là {method === 'washer' ? 'vòng đệm' : 'đĩa'}.</li>
                <li>A(x) = {method === 'washer' ? 'π(R²−r²)' : 'πR²'}.</li>
                <li>Tăng n → Riemann tiến tới V.</li>
              </>
            )}
          </ul>
        </div>
        {showCompare && !computed.error && !altComputed.error && (
          <div className="csim-card">
            <div className="csim-card-head"><strong>So sánh Ox vs Oy</strong><span>cùng miền f (ước lượng)</span></div>
            <div className="sim-kv-list">
              <div className="sim-kv-row highlight"><span>V hiện tại ({methodLabel(method)})</span><strong>{formatNumber(computed.volume)}</strong></div>
              <div className="sim-kv-row"><span>V nếu {methodLabel(altMethod)}</span><strong>{formatNumber(altComputed.volume)}</strong></div>
              <div className="sim-kv-row"><span>|V_Ox − V_Oy|</span><strong>{formatNumber(Math.abs(computed.volume - altComputed.volume))}</strong></div>
            </div>
            <p className="sim-muted">Hai phương pháp quay khác trục → khối khác nhau. Đổi trục ở bước 1 để kiểm chứng.</p>
          </div>
        )}
      </aside>

      <section className="csim-visual-stack">
        <div className="csim-split-visuals">
          <CalculusGraph2D
            primary={computed.fPoints}
            secondary={computed.gPoints}
            fillBetween={state.useWasher || method === 'shell'}
            markerX={safeSliceX}
            title={method === 'shell' ? 'Miền quay quanh Oy (shell)' : 'Đồ thị sinh khối quanh Ox'}
            primaryLabel="f(x)"
            secondaryLabel={state.useWasher ? 'g(x)' : method === 'shell' ? 'Ox' : 'Ox'}
          />
          {computed.fCompiled && !computed.error ? (
            <RevolutionThreeView
              f={computed.fCompiled}
              g={state.useWasher || method === 'shell' ? computed.gCompiled : null}
              a={state.a}
              b={state.b}
              sweep={sweep}
              sliceX={safeSliceX}
              visibleDisks={visibleDisks}
              totalDisks={state.n}
              showSurface={step >= 2}
              showSelectedSlice={step === 3 || (method === 'shell' && step >= 3)}
              showDiskStack={step >= 4}
              axis={state.axis}
            />
          ) : (
            <div className="csim-three-card csim-empty-three">Nhập hàm hợp lệ để xem 3D.</div>
          )}
        </div>
        <div className="csim-card csim-step-copy">
          <strong>{solidStepTitle(step, method)}</strong>
          <p>{solidStepCopy(step, method)}</p>
          <KatexSpan tex={computed.formula} />
        </div>
      </section>
    </div>
  );
}

function methodLabel(method: Method) {
  if (method === 'shell') return 'Shell quanh Oy';
  if (method === 'washer') return 'Washer quanh Ox';
  return 'Disk quanh Ox';
}

function computeSolid(state: State, method: Method) {
  const zero = compileExpression('0');
  const empty = {
    fPoints: [] as ReturnType<typeof sampleFunction>,
    gPoints: [] as ReturnType<typeof sampleFunction>,
    fCompiled: null as ReturnType<typeof compileExpression> | null,
    gCompiled: null as ReturnType<typeof compileExpression> | null,
    partialSumAt: null as ((visibleSlices: number) => number) | null,
    volume: NaN,
    riemannSum: NaN,
    outerRadius: NaN,
    innerRadius: NaN,
    sliceArea: NaN,
    error: null as string | null,
    formula: String.raw`V=\pi\int_a^b f(x)^2\,dx`,
  };
  const boundsError = validateBounds(state.a, state.b);
  if (boundsError) return { ...empty, error: boundsError };
  try {
    const f = compileExpression(state.f);
    const g = state.useWasher || method === 'shell' ? (state.useWasher ? compileExpression(state.g) : zero) : zero;
    // for shell without washer, g=0
    const gUse = method === 'shell' && !state.useWasher ? zero : g;
    const fPoints = sampleFunction(f, state.a, state.b, 240);
    const gPoints = sampleFunction(gUse, state.a, state.b, 240);
    const domainError = domainWarningFor(fPoints, 'f(x)')
      ?? ((state.useWasher || method === 'shell') ? domainWarningFor(gPoints, 'g(x)') : null);
    if (domainError) return { ...empty, fPoints, gPoints, fCompiled: f, gCompiled: gUse, error: domainError };

    let formula = String.raw`V=\pi\int_a^b f(x)^2\,dx`;
    let crossAt: (x: number) => number;

    if (method === 'shell') {
      formula = state.useWasher
        ? String.raw`V=\int_a^b 2\pi |x|\,|f(x)-g(x)|\,dx`
        : String.raw`V=\int_a^b 2\pi |x|\,|f(x)|\,dx`;
      crossAt = (x: number) => {
        const fv = safeEval(f, x);
        const gv = state.useWasher ? safeEval(gUse, x) : 0;
        if (!Number.isFinite(fv) || !Number.isFinite(gv)) return NaN;
        const height = Math.abs(fv - gv);
        return 2 * Math.PI * Math.abs(x) * height;
      };
    } else {
      formula = state.useWasher
        ? String.raw`V=\pi\int_a^b\left(R(x)^2-r(x)^2\right)\,dx`
        : String.raw`V=\pi\int_a^b f(x)^2\,dx`;
      crossAt = (x: number) => {
        const fv = Math.max(0, safeEval(f, x));
        const gv = Math.max(0, safeEval(gUse, x));
        const outer = state.useWasher ? Math.max(fv, gv) : fv;
        const inner = state.useWasher ? Math.min(fv, gv) : 0;
        return Math.PI * (outer * outer - inner * inner);
      };
    }

    const volume = integrate(crossAt, state.a, state.b);
    const fv = safeEval(f, state.sliceX);
    const gv = state.useWasher ? safeEval(gUse, state.sliceX) : 0;
    let outerRadius: number;
    let innerRadius: number;
    let sliceArea: number;
    if (method === 'shell') {
      outerRadius = Math.abs(state.sliceX);
      innerRadius = Math.abs(fv - (state.useWasher ? gv : 0));
      sliceArea = 2 * Math.PI * outerRadius * innerRadius;
    } else {
      const fvp = Math.max(0, fv);
      const gvp = Math.max(0, gv);
      outerRadius = state.useWasher ? Math.max(fvp, gvp) : fvp;
      innerRadius = state.useWasher ? Math.min(fvp, gvp) : 0;
      sliceArea = Math.PI * (outerRadius * outerRadius - innerRadius * innerRadius);
    }

    const dx = (state.b - state.a) / state.n;
    const partials: number[] = [];
    let riemannSum = 0;
    for (let i = 0; i < state.n; i += 1) {
      riemannSum += crossAt(state.a + (i + 0.5) * dx) * dx;
      partials.push(riemannSum);
    }
    const partialSumAt = (visibleSlices: number) => partials[Math.max(0, Math.min(partials.length, visibleSlices)) - 1] ?? 0;
    return {
      fPoints,
      gPoints,
      fCompiled: f,
      gCompiled: gUse,
      partialSumAt,
      volume,
      riemannSum,
      outerRadius,
      innerRadius,
      sliceArea,
      error: null,
      formula,
    };
  } catch (error) {
    return { ...empty, error: error instanceof Error ? error.message : 'Không đọc được biểu thức.' };
  }
}

function solidStepTitle(step: number, method: Method) {
  if (method === 'shell') {
    return [
      'Bước 1 — Miền phẳng và trục Oy',
      'Bước 2 — Quay quanh Oy (vỏ trụ)',
      'Bước 3 — Một vỏ trụ tại x',
      'Bước 4 — Cộng dồn các vỏ',
      'Bước 5 — Riemann shell vs tích phân',
    ][step - 1] ?? 'Shell';
  }
  return [
    'Bước 1 — Đồ thị và trục quay Ox',
    'Bước 2 — Quét quanh trục Ox',
    'Bước 3 — Cắt lát đĩa / vành khăn',
    'Bước 4 — Xếp chồng lát (Riemann thể tích)',
    'Bước 5 — Đối chiếu tổng Riemann với tích phân V',
  ][step - 1] ?? 'Mô phỏng';
}

function solidStepCopy(step: number, method: Method): ReactNode {
  if (method === 'shell') {
    if (step === 1) return <>Miền dưới (hoặc giữa) đồ thị sẽ quay quanh <KatexSpan tex="Oy" />. Shell không cần đổi biến y.</>;
    if (step === 2) return <>Mỗi “dải đứng” tại x quét thành vỏ trụ. Quan sát khối 3D quanh trục đứng.</>;
    if (step === 3) return <>Vỏ tại x: bán kính <KatexSpan tex="|x|" />, chiều cao <KatexSpan tex="h(x)" />, “diện tích” <KatexSpan tex={String.raw`2\pi|x|h(x)`} />.</>;
    if (step === 4) return <>Cộng các vỏ mỏng: <KatexSpan tex={String.raw`\sum 2\pi|x_i|h(x_i)\Delta x`} />.</>;
    if (step === 5) return <>So Riemann với <KatexSpan tex={String.raw`V=\int 2\pi|x|h(x)\,dx`} />. Đổi n, so với disk quanh Ox trên cùng miền (nếu có).</>;
    return null;
  }
  if (step === 1) return <>Quan sát đồ thị trên đoạn <KatexSpan tex="[a,b]" /> và trục <KatexSpan tex="Ox" />. Bật washer nếu có lỗ trong.</>;
  if (step === 2) return <>Đường cong quay quanh <KatexSpan tex="Ox" />, quét ra bề mặt 3D.</>;
  if (step === 3) return method === 'washer'
    ? <>Lát cắt vành khăn với <KatexSpan tex="A(x)=\\pi(R^2-r^2)" />.</>
    : <>Lát cắt đĩa với <KatexSpan tex="A(x)=\\pi f(x)^2" />.</>;
  if (step === 4) return <>Các lát mỏng xếp chồng thành tổng <KatexSpan tex="\\sum A(x_i^*)\\Delta x" />.</>;
  if (step === 5) return <>Đối chiếu tổng Riemann với <KatexSpan tex="V=\\int A(x)\\,dx" />.</>;
  return null;
}
