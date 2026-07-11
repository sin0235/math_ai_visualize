import { useMemo, useState } from 'react';
import { KatexSpan } from '../KatexSpan';
import { compileExpression } from '../../utils/calculusExpression';
import { domainWarningFor, findIntersections, formatNumber, functionsCoincide, integrate, riemannBetween, sampleFunction, validateBounds, type RiemannRule } from '../../utils/calculusNumerics';
import { formatVerifyTone, verifyAreaBetweenCurves } from '../../simulation/math/verify';
import { BoundsInput, FormulaInput, PresetButtons, ResultCard, SliderInput } from '../../simulation/runtime/SimulationPrimitives';
import { CalculusGraph2D } from './CalculusGraph2D';

interface Props {
  step: number;
  progress: number;
  freeMode?: boolean;
}

const RULE_LABELS: Record<RiemannRule, string> = {
  left: 'Trái (left)',
  mid: 'Trung điểm (mid)',
  right: 'Phải (right)',
};

export function AreaBetweenCurvesSimulation({ step, progress, freeMode = false }: Props) {
  const [state, setState] = useAreaState();
  const computed = useMemo(() => computeArea(state), [state]);
  const verify = useMemo(
    () => (computed.error ? null : verifyAreaBetweenCurves(state)),
    [state, computed.error],
  );
  const visibleRectangles =
    step < 2 ? 0 : step === 2 ? Math.ceil(computed.rectangles.length * progress) : computed.rectangles.length;
  const accumulatedArea = computed.rectangles.slice(0, visibleRectangles).reduce((sum, rect) => sum + rect.area, 0);
  const absError = Number.isFinite(computed.approx) && Number.isFinite(computed.exact)
    ? Math.abs(computed.approx - computed.exact)
    : NaN;
  const canEditF = freeMode || step >= 1;
  const canEditN = freeMode || step >= 2;
  const canEditRule = freeMode || step >= 4;
  const showCompare = freeMode || step >= 4;

  return (
    <div className="csim-module-grid">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head"><strong>Nhập dữ liệu</strong><span>Miền giữa hai đường</span></div>
          <FormulaInput label="$f(x)$" value={state.f} onChange={(f) => setState({ ...state, f })} disabled={!canEditF} />
          <FormulaInput label="$g(x)$" value={state.g} onChange={(g) => setState({ ...state, g })} disabled={!canEditF} />
          <div className={!canEditF ? 'is-step-locked' : undefined}>
            <PresetButtons presets={AREA_PRESETS} onApply={(preset) => canEditF && setState({ ...state, ...preset.patch })} />
          </div>
          <BoundsInput a={state.a} b={state.b} onChange={(patch) => setState({ ...state, ...patch })} disabled={!canEditF} />
          <label className={`csim-field${!canEditRule ? ' is-step-locked' : ''}`}>
            <span>Quy tắc Riemann {canEditRule ? '' : '(mở bước 4)'}</span>
            <select value={state.rule} disabled={!canEditRule} onChange={(e) => setState({ ...state, rule: e.target.value as RiemannRule })}>
              {(Object.keys(RULE_LABELS) as RiemannRule[]).map((rule) => (
                <option key={rule} value={rule}>{RULE_LABELS[rule]}</option>
              ))}
            </select>
          </label>
          <SliderInput label={<>Số hình chữ nhật <KatexSpan tex="n" /></>} value={state.n} min={4} max={200} step={1} onChange={(n) => setState({ ...state, n })} disabled={!canEditN} />
        </div>
        <ResultCard title="Diện tích" error={computed.error} rows={[
          ['Cộng dồn hiện tại', formatNumber(accumulatedArea)],
          ['Xấp xỉ Riemann', formatNumber(computed.approx)],
          ['Giá trị tích phân', formatNumber(computed.exact)],
          ['Sai số |xấp xỉ − chính xác|', formatNumber(absError)],
          ['Số giao điểm', computed.identical ? 'Vô số (hai đường trùng nhau)' : String(computed.intersections.length)],
        ]} formula={String.raw`S=\int_a^b |f(x)-g(x)|\,dx`} highlight={step >= 3} />
        {verify && !computed.error && (
          <div className={`sim-verify-banner sim-verify-${verify.severity}`} role="status">
            <strong>{formatVerifyTone(verify.severity)}</strong>
            <span>{verify.message}</span>
          </div>
        )}
        {showCompare && !computed.error && (
          <div className="csim-card">
            <div className="csim-card-head"><strong>So sánh 3 quy tắc</strong><span>Cùng n = {state.n}</span></div>
            <div className="sim-kv-list">
              {computed.ruleCompare.map((row) => (
                <div key={row.rule} className={`sim-kv-row${row.rule === state.rule ? ' highlight' : ''}`}>
                  <span>{RULE_LABELS[row.rule]}</span>
                  <strong>{formatNumber(row.approx)} · sai {formatNumber(row.err)}</strong>
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>
      <section className="csim-visual-stack">
        <CalculusGraph2D
          primary={computed.fPoints}
          secondary={computed.gPoints}
          fillBetween={step >= 3}
          rectangles={computed.rectangles}
          visibleRectangles={visibleRectangles}
          intersections={computed.intersections}
          title="Diện tích miền kẹp"
        />
        <StepExplanation step={step} rule={state.rule} />
      </section>
    </div>
  );
}

function useAreaState() {
  return useState<AreaState>({ f: 'x', g: 'x^2', a: 0, b: 1, n: 24, rule: 'mid' });
}

type AreaState = { f: string; g: string; a: number; b: number; n: number; rule: RiemannRule };

const AREA_PRESETS: Array<{ label: string; patch: Partial<AreaState> }> = [
  { label: '$x$ và $x^2$', patch: { f: 'x', g: 'x^2', a: 0, b: 1, n: 24, rule: 'mid' } },
  { label: 'Hằng số', patch: { f: '5', g: '0', a: -5, b: 5, n: 20, rule: 'mid' } },
  { label: 'sqrt(x)', patch: { f: 'sqrt(x)', g: '0', a: 0, b: 4, n: 32, rule: 'mid' } },
];

function computeArea(state: AreaState) {
  const empty = {
    fPoints: [],
    gPoints: [],
    rectangles: [],
    intersections: [],
    approx: NaN,
    exact: NaN,
    identical: false,
    error: null as string | null,
    ruleCompare: [] as Array<{ rule: RiemannRule; approx: number; err: number }>,
  };
  const boundsError = validateBounds(state.a, state.b);
  if (boundsError) return { ...empty, error: boundsError };
  try {
    const f = compileExpression(state.f);
    const g = compileExpression(state.g);
    const fPoints = sampleFunction(f, state.a, state.b, 260);
    const gPoints = sampleFunction(g, state.a, state.b, 260);
    const domainError = domainWarningFor(fPoints, 'f(x)') ?? domainWarningFor(gPoints, 'g(x)');
    if (domainError) return { ...empty, fPoints, gPoints, error: domainError };
    const identical = functionsCoincide(f, g, state.a, state.b) || functionsAreIdentical(fPoints, gPoints);
    const exact = integrate((x) => Math.abs(f.evaluate(x) - g.evaluate(x)), state.a, state.b);
    const rules: RiemannRule[] = ['left', 'mid', 'right'];
    const ruleCompare = identical
      ? []
      : rules.map((rule) => {
          const rects = riemannBetween(f, g, state.a, state.b, state.n, rule);
          const approx = rects.reduce((sum, rect) => sum + rect.area, 0);
          return { rule, approx, err: Math.abs(approx - exact) };
        });
    const rectangles = identical ? [] : riemannBetween(f, g, state.a, state.b, state.n, state.rule);
    if (rectangles.some((rect) => !Number.isFinite(rect.area))) return { ...empty, fPoints, gPoints, error: 'Một phần đoạn [a,b] nằm ngoài miền xác định của hàm, nên không thể xấp xỉ Riemann chính xác.' };
    const approx = rectangles.reduce((sum, rect) => sum + rect.area, 0);
    const intersections = identical ? [] : findIntersections(f, g, state.a, state.b);
    return { fPoints, gPoints, rectangles, intersections, approx, exact, identical, error: null, ruleCompare };
  } catch (error) {
    return { ...empty, error: error instanceof Error ? error.message : 'Không đọc được biểu thức.' };
  }
}

function functionsAreIdentical(fPoints: Array<{ y: number; valid: boolean }>, gPoints: Array<{ y: number; valid: boolean }>) {
  const validPairs = fPoints.map((point, index) => [point, gPoints[index]] as const).filter(([fPoint, gPoint]) => fPoint.valid && gPoint?.valid);
  if (validPairs.length < Math.min(fPoints.length, gPoints.length) * 0.95) return false;
  return validPairs.every(([fPoint, gPoint]) => Math.abs(fPoint.y - gPoint.y) < 1e-7);
}

function StepExplanation({ step, rule }: { step: number; rule: RiemannRule }) {
  const copy = [
    ['Bước 1 — Hai đường cong & giao điểm', <>Vẽ <KatexSpan tex="f" />, <KatexSpan tex="g" />; giao điểm gợi ý các khoảng tích phân tự nhiên.</>],
    ['Bước 2 — Dựng tổng Riemann', <>Hình chữ nhật theo quy tắc {RULE_LABELS[rule]}: <KatexSpan tex={String.raw`\sum |f(x_i^*)-g(x_i^*)|\Delta x`} />.</>],
    ['Bước 3 — Tiến tới diện tích đúng', <>Tô miền giữa hai đồ thị. Khi <KatexSpan tex="n\\to\\infty" />, tổng tiến tới <KatexSpan tex={String.raw`S=\int_a^b |f-g|\,dx`} />.</>],
    ['Bước 4 — So left / mid / right', <>Cùng n, ba quy tắc cho sai số khác nhau. Mid thường tốt hơn left/right với hàm trơn. Đổi n và quan sát bảng so sánh.</>],
  ][Math.max(0, Math.min(3, step - 1))];
  return <div className="csim-card csim-step-copy"><strong>{copy[0]}</strong><p>{copy[1]}</p></div>;
}
