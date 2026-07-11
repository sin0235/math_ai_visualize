import { useMemo, useState, type ReactNode } from 'react';
import { KatexSpan } from '../KatexSpan';
import { compileExpression } from '../../utils/calculusExpression';
import { clamp, domainWarningFor, formatNumber, integrate, sampleFunction, safeEval, validateBounds } from '../../utils/calculusNumerics';
import { CalculusGraph2D } from './CalculusGraph2D';
import { CrossSectionThreeView } from './CalculusThreeViews';
import { BoundsInput, FormulaInput, PresetButtons, ResultCard, SliderInput } from '../../simulation/runtime/SimulationPrimitives';

interface Props {
  step: number;
  progress: number;
  freeMode?: boolean;
}

type Shape = 'square' | 'rectangle' | 'triangle' | 'circle';
type State = { base: string; a: number; b: number; shape: Shape; ratio: number; n: number; sliceX: number };

const CROSS_PRESETS: Array<{ label: string; patch: Partial<State> }> = [
  { label: 'sqrt(x)', patch: { base: 'sqrt(x)', a: 0, b: 4, sliceX: 2, shape: 'square', n: 28 } },
  { label: 'x(1-x)', patch: { base: 'x*(1-x)', a: 0, b: 1, sliceX: 0.5, shape: 'square', n: 32 } },
];

export function CrossSectionVolumeSimulation({ step, progress, freeMode = false }: Props) {
  const [state, setState] = useState<State>({ base: 'sqrt(x)', a: 0, b: 4, shape: 'square', ratio: 1.5, n: 28, sliceX: 2 });
  const computed = useMemo(() => computeCrossSection(state), [state]);
  const visibleSlices = step === 3 ? Math.ceil(state.n * progress) : step >= 4 ? state.n : 0;
  const safeSliceX = clamp(state.sliceX, state.a, state.b);
  const zeroPoints = useMemo(() => computed.areaPoints.map((point) => ({ x: point.x, y: 0, valid: point.valid })), [computed.areaPoints]);
  const accumulatedVolume = computed.partialSumAt?.(visibleSlices) ?? NaN;
  const canSetup = freeMode || step >= 1;
  const canSlice = freeMode || step >= 2;
  const canN = freeMode || step >= 3;

  return (
    <div className="csim-module-grid csim-module-grid-wide">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head"><strong>Thiết diện song song</strong><span><KatexSpan tex={String.raw`V=\int_a^b S(x)\,dx`} /></span></div>
          <FormulaInput label="$s(x)$" value={state.base} onChange={(base) => setState({ ...state, base })} disabled={!canSetup} />
          <div className={!canSetup ? 'is-step-locked' : undefined}>
            <PresetButtons presets={CROSS_PRESETS} onApply={(preset) => canSetup && setState((current) => ({ ...current, ...preset.patch }))} />
          </div>
          <BoundsInput a={state.a} b={state.b} disabled={!canSetup} onChange={(patch) => setState((current) => ({ ...current, ...patch, sliceX: clamp(current.sliceX, patch.a ?? current.a, patch.b ?? current.b) }))} />
          <label className={`csim-field${!canSetup ? ' is-step-locked' : ''}`}><span>Dạng thiết diện</span><select disabled={!canSetup} value={state.shape} onChange={(e) => setState({ ...state, shape: e.target.value as Shape })}><option value="square">Hình vuông</option><option value="rectangle">Hình chữ nhật</option><option value="triangle">Tam giác đều</option><option value="circle">Hình tròn</option></select></label>
          {state.shape === 'rectangle' && <SliderInput label={<>Tỉ lệ <KatexSpan tex={String.raw`\frac{h}{s}`} /></>} value={state.ratio} min={0.3} max={3} step={0.1} onChange={(ratio) => setState({ ...state, ratio })} disabled={!canSetup} />}
          <SliderInput label="Số lát cắt" value={state.n} min={4} max={120} step={1} onChange={(n) => setState({ ...state, n })} disabled={!canN} />
          <SliderInput label={<>Vị trí <KatexSpan tex="x" /></>} value={safeSliceX} min={state.a} max={state.b} step={(state.b - state.a) / 200 || 0.01} onChange={(sliceX) => setState({ ...state, sliceX })} disabled={!canSlice} />
        </div>
        <ResultCard title="Thể tích thiết diện" error={computed.error} formula={shapeFormula(state.shape, state.ratio)} highlight={step >= 4} rows={[
          ['Cộng dồn hiện tại', formatNumber(accumulatedVolume)],
          ['S(x) tại lát cắt', formatNumber(computed.sliceArea)],
          ['Tổng xấp xỉ', formatNumber(computed.approx)],
          ['Thể tích V', formatNumber(computed.volume)],
        ]} />
      </aside>
      <section className="csim-visual-stack">
        <div className="csim-split-visuals">
          <CalculusGraph2D primary={computed.areaPoints} secondary={zeroPoints} fillBetween={step >= 4} markerX={step === 2 ? safeSliceX : undefined} title="Đồ thị diện tích thiết diện S(x)" primaryLabel="S(x)" secondaryLabel="" />
          {computed.areaAt && !computed.error ? <CrossSectionThreeView areaAt={computed.areaAt} a={state.a} b={state.b} sliceX={safeSliceX} visibleSlices={visibleSlices} totalSlices={state.n} shape={state.shape} ratio={state.ratio} showSelectedSlice={step === 2} /> : <div className="csim-three-card csim-empty-three">Nhập hàm hợp lệ để xem thiết diện.</div>}
        </div>
        <div className="csim-card csim-step-copy"><strong>{crossStepTitle(step)}</strong><p>{crossStepCopy(step)}</p></div>
      </section>
    </div>
  );
}

function computeCrossSection(state: State) {
  const empty = { areaPoints: [], areaAt: null as ((x: number) => number) | null, partialSumAt: null as ((visibleSlices: number) => number) | null, volume: NaN, approx: NaN, sliceArea: NaN, error: null as string | null };
  const boundsError = validateBounds(state.a, state.b);
  if (boundsError) return { ...empty, error: boundsError };
  try {
    const base = compileExpression(state.base);
    const basePoints = sampleFunction(base, state.a, state.b, 240);
    const domainError = domainWarningFor(basePoints, 's(x)');
    if (domainError) return { ...empty, areaPoints: basePoints, error: domainError };
    const areaAt = (x: number) => sectionArea(Math.max(0, safeEval(base, x)), state.shape, state.ratio);
    const areaPoints = sampleFunction({ source: `S(${base.source})`, evaluate: areaAt }, state.a, state.b, 240);
    const volume = integrate(areaAt, state.a, state.b);
    const dx = (state.b - state.a) / state.n;
    const partials: number[] = [];
    let approx = 0;
    for (let i = 0; i < state.n; i += 1) {
      approx += areaAt(state.a + (i + 0.5) * dx) * dx;
      partials.push(approx);
    }
    const partialSumAt = (visibleSlices: number) => partials[Math.max(0, Math.min(partials.length, visibleSlices)) - 1] ?? 0;
    const sliceArea = areaAt(state.sliceX);
    return { areaPoints, areaAt, partialSumAt, volume, approx, sliceArea, error: null };
  } catch (error) {
    return { ...empty, error: error instanceof Error ? error.message : 'Không đọc được biểu thức.' };
  }
}

function sectionArea(s: number, shape: Shape, ratio: number) {
  if (!Number.isFinite(s)) return NaN;
  if (shape === 'square') return s * s;
  if (shape === 'rectangle') return ratio * s * s;
  if (shape === 'triangle') return (Math.sqrt(3) / 4) * s * s;
  return Math.PI * (s / 2) * (s / 2);
}

function shapeFormula(shape: Shape, ratio: number) {
  if (shape === 'square') return String.raw`S(x)=s(x)^2,\quad V=\int_a^b S(x)\,dx`;
  if (shape === 'rectangle') return String.raw`S(x)=${formatNumber(ratio, 2)}s(x)^2,\quad V=\int_a^b S(x)\,dx`;
  if (shape === 'triangle') return String.raw`S(x)=\frac{\sqrt3}{4}s(x)^2,\quad V=\int_a^b S(x)\,dx`;
  return String.raw`S(x)=\pi\left(\frac{s(x)}{2}\right)^2,\quad V=\int_a^b S(x)\,dx`;
}

function crossStepTitle(step: number) {
  return ['Bước 1 — Đồ thị S(x)', 'Bước 2 — Mặt phẳng cắt', 'Bước 3 — Xếp lát mỏng', 'Bước 4 — Tích phân hóa'][step - 1] ?? 'Mô phỏng';
}

function crossStepCopy(step: number): ReactNode {
  if (step === 1) return <>Trước hết học sinh nhìn <KatexSpan tex="S(x)" /> như một hàm diện tích biến thiên theo vị trí <KatexSpan tex="x" />.</>;
  if (step === 2) return <>Kéo slider <KatexSpan tex="x" /> để thấy mặt phẳng cắt đi dọc khối và diện tích thiết diện tại vị trí đó.</>;
  if (step === 3) return <>Các lát mỏng bề dày <KatexSpan tex={String.raw`\Delta x`} /> xếp chồng lên nhau; tổng <KatexSpan tex={String.raw`\sum_i S(x_i)\Delta x`} /> là xấp xỉ thể tích.</>;
  return <>Khi số lát tăng vô hạn, tổng xấp xỉ trở thành tích phân <KatexSpan tex={String.raw`V=\int_a^b S(x)\,dx`} />.</>;
}
