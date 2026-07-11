import { useEffect, useState, type ReactNode } from 'react';
import { KatexSpan, MixedTextRenderer } from '../../components/KatexSpan';
import { compileExpression } from '../../utils/calculusExpression';
import { formatNumber } from '../../utils/calculusNumerics';

export function FormulaInput({
  label,
  value,
  onChange,
  placeholder = 'vd: sin(x), x^2, sqrt(x), 5',
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  const [touched, setTouched] = useState(false);
  const error = touched && !disabled ? formulaError(value) : null;

  return (
    <label className={`csim-field ${error ? 'has-error' : ''}${disabled ? ' is-step-locked' : ''}`}>
      <span><MixedTextRenderer text={label} /></span>
      <input
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        onBlur={() => setTouched(true)}
        placeholder={placeholder}
        spellCheck={false}
      />
      {error ? (
        <small className="csim-field-error">{error}</small>
      ) : (
        <small className="csim-field-hint">
          Dùng biến <KatexSpan tex="x" />. Ví dụ: <KatexSpan tex="x^2" />,{' '}
          <KatexSpan tex={String.raw`\sin(x)`} />, <KatexSpan tex={String.raw`\sqrt{x}`} />, <KatexSpan tex="5" />.
        </small>
      )}
    </label>
  );
}

export function BoundsInput({
  a,
  b,
  onChange,
  disabled = false,
}: {
  a: number;
  b: number;
  onChange: (patch: { a?: number; b?: number }) => void;
  disabled?: boolean;
}) {
  const [rawA, setRawA] = useState(String(a));
  const [rawB, setRawB] = useState(String(b));
  const [touched, setTouched] = useState({ a: false, b: false });

  useEffect(() => setRawA(String(a)), [a]);
  useEffect(() => setRawB(String(b)), [b]);

  const parsedA = parseBound(rawA);
  const parsedB = parseBound(rawB);
  const orderError = parsedA.value !== null && parsedB.value !== null && parsedA.value >= parsedB.value
    ? 'Cận trái a phải nhỏ hơn cận phải b.'
    : null;
  const errorA = touched.a ? parsedA.error ?? orderError : null;
  const errorB = touched.b ? parsedB.error ?? orderError : null;

  function update(key: 'a' | 'b', raw: string) {
    if (key === 'a') setRawA(raw);
    else setRawB(raw);
    const parsed = parseBound(raw);
    if (parsed.value !== null) onChange({ [key]: parsed.value });
  }

  return (
    <div className={`csim-two-cols${disabled ? ' is-step-locked' : ''}`}>
      <label className={`csim-field ${errorA ? 'has-error' : ''}`}>
        <span><KatexSpan tex="a" /></span>
        <input
          type="number"
          disabled={disabled}
          value={rawA}
          onBlur={() => setTouched((current) => ({ ...current, a: true }))}
          onChange={(event) => update('a', event.target.value)}
        />
        {errorA && <small className="csim-field-error">{errorA}</small>}
      </label>
      <label className={`csim-field ${errorB ? 'has-error' : ''}`}>
        <span><KatexSpan tex="b" /></span>
        <input
          type="number"
          disabled={disabled}
          value={rawB}
          onBlur={() => setTouched((current) => ({ ...current, b: true }))}
          onChange={(event) => update('b', event.target.value)}
        />
        {errorB && <small className="csim-field-error">{errorB}</small>}
      </label>
    </div>
  );
}

export function PresetButtons<T extends object>({
  presets,
  onApply,
}: {
  presets: Array<{ label: string; patch: Partial<T> }>;
  onApply: (preset: { label: string; patch: Partial<T> }) => void;
}) {
  return (
    <div className="csim-preset-row" aria-label="Ví dụ mẫu">
      {presets.map((preset) => (
        <button type="button" className="csim-chip" key={preset.label} onClick={() => onApply(preset)}>
          <MixedTextRenderer text={preset.label} />
        </button>
      ))}
    </div>
  );
}

export function SliderInput({
  label,
  value,
  min,
  max,
  step,
  onChange,
  disabled = false,
}: {
  label: ReactNode;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}) {
  return (
    <label className={`csim-slider${disabled ? ' is-step-locked' : ''}`}>
      <span>
        {typeof label === 'string' ? <MixedTextRenderer text={label} /> : label}: <strong>{formatNumber(value, 2)}</strong>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}

export function ResultCard({
  title,
  error,
  rows,
  formula,
  highlight,
}: {
  title: string;
  error: string | null;
  rows: Array<[ReactNode, string]>;
  formula: string;
  highlight?: boolean;
}) {
  return (
    <div className={`csim-card csim-result-card ${highlight ? 'is-complete' : ''}`}>
      <div className="csim-card-head">
        <strong><MixedTextRenderer text={title} /></strong>
        <span>Kết quả số</span>
      </div>
      {error ? (
        <div className="sp-error">{error}</div>
      ) : (
        <>
          <KatexSpan tex={formula} className="csim-formula" />
          <div className="csim-result-grid">
            {rows.map(([rowLabel, rowValue], index) => (
              <div className="csim-result-row" key={index}>
                <span>{typeof rowLabel === 'string' ? <MixedTextRenderer text={rowLabel} /> : rowLabel}</span>
                <strong><MixedTextRenderer text={rowValue} /></strong>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
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