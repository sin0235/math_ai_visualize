import { useMemo, useState, type ReactNode } from 'react';
import { KatexSpan } from '../KatexSpan';
import { compileExpression } from '../../utils/calculusExpression';
import { clamp, domainWarningFor, formatNumber, integrate, sampleFunction, safeEval, validateBounds } from '../../utils/calculusNumerics';
import { CalculusGraph2D } from './CalculusGraph2D';
import { RevolutionThreeView } from './CalculusThreeViews';
import { BoundsInput, FormulaInput, PresetButtons, ResultCard, SliderInput } from './AreaBetweenCurvesSimulation';

interface Props {
  step: number;
  progress: number;
}

type State = { f: string; g: string; useWasher: boolean; a: number; b: number; sliceX: number; axis: 'Ox' | 'Oy'; n: number };

const SOLID_PRESETS: Array<{ label: string; patch: Partial<State> }> = [
  { label: 'sqrt(x) quanh Ox', patch: { f: 'sqrt(x)', g: 'x/2', useWasher: false, a: 0, b: 4, sliceX: 2, n: 36 } },
  { label: 'Washer', patch: { f: 'sqrt(x)', g: 'x/2', useWasher: true, a: 0, b: 4, sliceX: 2, n: 36 } },
];

export function SolidOfRevolutionSimulation({ step, progress }: Props) {
  const [state, setState] = useState<State>({ f: 'sqrt(x)', g: 'x/2', useWasher: false, a: 0, b: 4, sliceX: 2, axis: 'Ox', n: 36 });
  const computed = useMemo(() => computeSolid(state), [state]);
  const sweep = (step === 2 ? progress : step > 2 ? 1 : 0) * Math.PI * 2;
  const sweepRatio = clamp(sweep / (Math.PI * 2), 0, 1);
  const sweptVolume = computed.volume * sweepRatio;
  const visibleDisks = step >= 4 ? Math.ceil(state.n * progress) : 0;
  const diskSum = computed.partialSumAt?.(visibleDisks) ?? NaN;
  const safeSliceX = clamp(state.sliceX, state.a, state.b);

  return (
    <div className="csim-module-grid csim-module-grid-wide">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head"><strong>Khối tròn xoay</strong><span><KatexSpan tex={String.raw`\text{Disk / Washer quanh }Ox`} /></span></div>
          <FormulaInput label="f(x)" value={state.f} onChange={(f) => setState({ ...state, f })} />
          <label className="csim-check"><input type="checkbox" checked={state.useWasher} onChange={(e) => setState({ ...state, useWasher: e.target.checked })} /> Dùng biến thể washer với <KatexSpan tex="g(x)" /></label>
          {state.useWasher && <FormulaInput label="g(x)" value={state.g} onChange={(g) => setState({ ...state, g })} />}
          <PresetButtons presets={SOLID_PRESETS} onApply={(preset) => setState((current) => ({ ...current, ...preset.patch }))} />
          <BoundsInput a={state.a} b={state.b} onChange={(patch) => setState((current) => ({ ...current, ...patch, sliceX: clamp(current.sliceX, patch.a ?? current.a, patch.b ?? current.b) }))} />
          <label className="csim-field"><span>Trục quay</span><select value={state.axis} onChange={(e) => setState({ ...state, axis: e.target.value as State['axis'] })}><option value="Ox">Ox — hỗ trợ đầy đủ</option><option value="Oy" disabled>Oy — sắp có</option></select></label>
          <SliderInput label={<>Vị trí lát cắt <KatexSpan tex="x" /></>} value={safeSliceX} min={state.a} max={state.b} step={(state.b - state.a) / 200 || 0.01} onChange={(sliceX) => setState({ ...state, sliceX })} />
          <SliderInput label={<>Số lát tích phân <KatexSpan tex="n" /></>} value={state.n} min={6} max={120} step={1} onChange={(n) => setState({ ...state, n })} />
        </div>
        <ResultCard title="Thể tích" error={computed.error} formula={state.useWasher ? String.raw`V=\pi\int_a^b\left(R(x)^2-r(x)^2\right)\,dx` : String.raw`V=\pi\int_a^b f(x)^2\,dx`} highlight={step >= 4} rows={[
          [step >= 4 ? 'Cộng dồn lát đĩa' : 'Cộng dồn phần đã quét', formatNumber(step >= 4 ? diskSum : sweptVolume)],
          ['Tổng Riemann', formatNumber(computed.riemannSum)],
          ['Thể tích V', formatNumber(computed.volume)],
          ['Bán kính ngoài tại x', formatNumber(computed.outerRadius)],
          ['Diện tích lát cắt', formatNumber(computed.sliceArea)],
        ]} />
      </aside>
      <section className="csim-visual-stack">
        <div className="csim-split-visuals">
          <CalculusGraph2D primary={computed.fPoints} secondary={computed.gPoints} fillBetween={state.useWasher} markerX={safeSliceX} title="Đồ thị sinh khối tròn xoay" primaryLabel="f(x)" secondaryLabel={state.useWasher ? 'g(x)' : 'Ox'} />
          {computed.fCompiled && !computed.error ? <RevolutionThreeView f={computed.fCompiled} g={state.useWasher ? computed.gCompiled : null} a={state.a} b={state.b} sweep={sweep} sliceX={safeSliceX} visibleDisks={visibleDisks} totalDisks={state.n} showSurface={step >= 2} showSelectedSlice={step === 3} showDiskStack={step >= 4} /> : <div className="csim-three-card csim-empty-three">Nhập hàm hợp lệ để xem 3D.</div>}
        </div>
        <div className="csim-card csim-step-copy"><strong>{solidStepTitle(step)}</strong><p>{solidStepCopy(step, state.useWasher)}</p><KatexSpan tex={state.useWasher ? String.raw`A(x)=\pi\left(R(x)^2-r(x)^2\right)` : String.raw`A(x)=\pi f(x)^2`} /></div>
      </section>
    </div>
  );
}

function computeSolid(state: State) {
  const zero = compileExpression('0');
  const empty = { fPoints: [], gPoints: [], fCompiled: null, gCompiled: null, partialSumAt: null as ((visibleSlices: number) => number) | null, volume: NaN, riemannSum: NaN, outerRadius: NaN, sliceArea: NaN, error: null as string | null };
  const boundsError = validateBounds(state.a, state.b);
  if (boundsError) return { ...empty, error: boundsError };
  try {
    const f = compileExpression(state.f);
    const g = state.useWasher ? compileExpression(state.g) : zero;
    const fPoints = sampleFunction(f, state.a, state.b, 240);
    const gPoints = state.useWasher ? sampleFunction(g, state.a, state.b, 240) : sampleFunction(zero, state.a, state.b, 2);
    const domainError = domainWarningFor(fPoints, 'f(x)') ?? (state.useWasher ? domainWarningFor(gPoints, 'g(x)') : null);
    if (domainError) return { ...empty, fPoints, gPoints, fCompiled: f, gCompiled: g, error: domainError };
    const crossAreaAt = (x: number) => {
      const fv = Math.max(0, safeEval(f, x));
      const gv = Math.max(0, safeEval(g, x));
      const outer = state.useWasher ? Math.max(fv, gv) : fv;
      const inner = state.useWasher ? Math.min(fv, gv) : 0;
      return Math.PI * (outer * outer - inner * inner);
    };
    const volume = integrate(crossAreaAt, state.a, state.b);
    const fv = Math.max(0, safeEval(f, state.sliceX));
    const gv = state.useWasher ? Math.max(0, safeEval(g, state.sliceX)) : 0;
    const outerRadius = state.useWasher ? Math.max(fv, gv) : fv;
    const innerRadius = state.useWasher ? Math.min(fv, gv) : 0;
    const sliceArea = Math.PI * (outerRadius * outerRadius - innerRadius * innerRadius);
    const dx = (state.b - state.a) / state.n;
    const partials: number[] = [];
    let riemannSum = 0;
    for (let i = 0; i < state.n; i += 1) {
      riemannSum += crossAreaAt(state.a + (i + 0.5) * dx) * dx;
      partials.push(riemannSum);
    }
    const partialSumAt = (visibleSlices: number) => partials[Math.max(0, Math.min(partials.length, visibleSlices)) - 1] ?? 0;
    return { fPoints, gPoints, fCompiled: f, gCompiled: g, partialSumAt, volume, riemannSum, outerRadius, sliceArea, error: null };
  } catch (error) {
    return { ...empty, error: error instanceof Error ? error.message : 'Không đọc được biểu thức.' };
  }
}

function solidStepTitle(step: number) {
  return ['Bước 1 — Đồ thị và trục quay', 'Bước 2 — Quét quanh trục Ox', 'Bước 3 — Cắt lát đĩa / vành khăn', 'Bước 4 — Tổng hợp công thức'][step - 1] ?? 'Mô phỏng';
}

function solidStepCopy(step: number, washer: boolean): ReactNode {
  if (step === 1) return <>Quan sát đồ thị trên đoạn <KatexSpan tex="[a,b]" /> và trục <KatexSpan tex="Ox" /> được dùng làm trục quay.</>;
  if (step === 2) return <>Đường cong quay quanh <KatexSpan tex="Ox" />, quét ra bề mặt 3D của khối tròn xoay. Bạn có thể xoay góc nhìn bằng chuột.</>;
  if (step === 3) return washer
    ? <>Kéo vị trí <KatexSpan tex="x" /> để xem một vành khăn đại diện: diện tích ngoài trừ diện tích lỗ bên trong.</>
    : <>Kéo vị trí <KatexSpan tex="x" /> để xem một lát đĩa đại diện: bán kính là <KatexSpan tex="f(x)" />, nên diện tích là <KatexSpan tex={String.raw`\pi f(x)^2`} />.</>;
  return <>Các lát đĩa/vành khăn mỏng xuất hiện dọc trục <KatexSpan tex="x" />; tổng <KatexSpan tex={String.raw`\sum_i A(x_i)\Delta x`} /> tiến dần tới tích phân thể tích.</>;
}
