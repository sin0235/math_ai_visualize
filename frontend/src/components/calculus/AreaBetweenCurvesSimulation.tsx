import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { KatexSpan } from '../KatexSpan';
import { compileExpression } from '../../utils/calculusExpression';
import { domainWarningFor, findIntersections, formatNumber, functionsCoincide, integrate, riemannBetween, sampleFunction, validateBounds, type RiemannRule } from '../../utils/calculusNumerics';
import { formatVerifyTone, verifyAreaBetweenCurves } from '../../simulation/math/verify';
import { CalculusGraph2D } from './CalculusGraph2D';

interface Props {
  step: number;
  progress: number;
}

const RULE_LABELS: Record<RiemannRule, string> = {
  left: 'Trái (left)',
  mid: 'Trung điểm (mid)',
  right: 'Phải (right)',
};

export function AreaBetweenCurvesSimulation({ step, progress }: Props) {
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

  return (
    <div className="csim-module-grid">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head"><strong>Nhập dữ liệu</strong><span>Miền giữa hai đường</span></div>
          <FormulaInput label="f(x)" value={state.f} onChange={(f) => setState({ ...state, f })} />
          <FormulaInput label="g(x)" value={state.g} onChange={(g) => setState({ ...state, g })} />
          <PresetButtons presets={AREA_PRESETS} onApply={(preset) => setState({ ...state, ...preset.patch })} />
          <BoundsInput a={state.a} b={state.b} onChange={(patch) => setState({ ...state, ...patch })} />
          <label className="csim-field">
            <span>Quy tắc Riemann</span>
            <select value={state.rule} onChange={(e) => setState({ ...state, rule: e.target.value as RiemannRule })}>
              {(Object.keys(RULE_LABELS) as RiemannRule[]).map((rule) => (
                <option key={rule} value={rule}>{RULE_LABELS[rule]}</option>
              ))}
            </select>
          </label>
          <SliderInput label={<>Số hình chữ nhật <KatexSpan tex="n" /></>} value={state.n} min={4} max={200} step={1} onChange={(n) => setState({ ...state, n })} />
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
        {!computed.error && (
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
  { label: 'x và x²', patch: { f: 'x', g: 'x^2', a: 0, b: 1, n: 24, rule: 'mid' } },
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
    ['Bước 3 — Tiến tới diện tích đúng', <>Tô miền |f−g|. Khi n→∞ tổng tiến tới <KatexSpan tex={String.raw`S=\int_a^b |f-g|\,dx`} />.</>],
    ['Bước 4 — So left / mid / right', <>Cùng n, ba quy tắc cho sai số khác nhau. Mid thường tốt hơn left/right với hàm trơn. Đổi n và quan sát bảng so sánh.</>],
  ][Math.max(0, Math.min(3, step - 1))];
  return <div className="csim-card csim-step-copy"><strong>{copy[0]}</strong><p>{copy[1]}</p></div>;
}

export function FormulaInput({ label, value, onChange, placeholder = 'vd: sin(x), x^2, sqrt(x), 5' }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string }) {
  const [touched, setTouched] = useState(false);
  const error = touched ? formulaError(value) : null;
  return <label className={`csim-field ${error ? 'has-error' : ''}`}><span><KatexSpan tex={label} /></span><input value={value} onChange={(e) => onChange(e.target.value)} onBlur={() => setTouched(true)} placeholder={placeholder} spellCheck={false} />{error ? <small className="csim-field-error">{error}</small> : <small className="csim-field-hint">Dùng biến <KatexSpan tex="x" />. Ví dụ: <KatexSpan tex="x^2" />, <KatexSpan tex={String.raw`\sin(x)`} />, <KatexSpan tex={String.raw`\sqrt{x}`} />, <KatexSpan tex="5" />.</small>}</label>;
}

export function BoundsInput({ a, b, onChange }: { a: number; b: number; onChange: (patch: { a?: number; b?: number }) => void }) {
  const [rawA, setRawA] = useState(String(a));
  const [rawB, setRawB] = useState(String(b));
  const [touched, setTouched] = useState({ a: false, b: false });
  useEffect(() => setRawA(String(a)), [a]);
  useEffect(() => setRawB(String(b)), [b]);
  const parsedA = parseBound(rawA);
  const parsedB = parseBound(rawB);
  const orderError = parsedA.value !== null && parsedB.value !== null && parsedA.value >= parsedB.value ? 'Cận trái a phải nhỏ hơn cận phải b.' : null;
  const errorA = touched.a ? parsedA.error ?? orderError : null;
  const errorB = touched.b ? parsedB.error ?? orderError : null;
  const update = (key: 'a' | 'b', raw: string) => {
    if (key === 'a') setRawA(raw);
    else setRawB(raw);
    const parsed = parseBound(raw);
    if (parsed.value !== null) onChange({ [key]: parsed.value });
  };
  return <div className="csim-two-cols"><label className={`csim-field ${errorA ? 'has-error' : ''}`}><span>a</span><input type="number" value={rawA} onBlur={() => setTouched((current) => ({ ...current, a: true }))} onChange={(e) => update('a', e.target.value)} />{errorA && <small className="csim-field-error">{errorA}</small>}</label><label className={`csim-field ${errorB ? 'has-error' : ''}`}><span>b</span><input type="number" value={rawB} onBlur={() => setTouched((current) => ({ ...current, b: true }))} onChange={(e) => update('b', e.target.value)} />{errorB && <small className="csim-field-error">{errorB}</small>}</label></div>;
}

export function PresetButtons<T extends object>({ presets, onApply }: { presets: Array<{ label: string; patch: Partial<T> }>; onApply: (preset: { label: string; patch: Partial<T> }) => void }) {
  return <div className="csim-preset-row" aria-label="Ví dụ mẫu">{presets.map((preset) => <button type="button" className="csim-chip" key={preset.label} onClick={() => onApply(preset)}>{preset.label}</button>)}</div>;
}

function formulaError(value: string) {
  if (!value.trim()) return 'Vui lòng nhập biểu thức hàm số.';
  try {
    compileExpression(value);
    return null;
  } catch (error) {
    return error instanceof Error ? error.message : 'Không đọc được biểu thức.';
  }
}

function parseBound(raw: string) {
  if (!raw.trim()) return { value: null, error: 'Vui lòng nhập cận.' };
  const value = Number(raw);
  if (!Number.isFinite(value)) return { value: null, error: 'Cận phải là số hữu hạn.' };
  return { value, error: null };
}

export function SliderInput({ label, value, min, max, step, onChange }: { label: ReactNode; value: number; min: number; max: number; step: number; onChange: (value: number) => void }) {
  return <label className="csim-slider"><span>{label}: <strong>{formatNumber(value, 2)}</strong></span><input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} /></label>;
}

export function ResultCard({ title, error, rows, formula, highlight }: { title: string; error: string | null; rows: Array<[ReactNode, string]>; formula: string; highlight?: boolean }) {
  return <div className={`csim-card csim-result-card ${highlight ? 'is-complete' : ''}`}><div className="csim-card-head"><strong>{title}</strong><span>Kết quả số</span></div>{error ? <div className="sp-error">{error}</div> : <><KatexSpan tex={formula} className="csim-formula" /> <div className="csim-result-grid">{rows.map(([label, value], index) => <div className="csim-result-row" key={index}><span>{label}</span><strong>{value}</strong></div>)}</div></>}</div>;
}
