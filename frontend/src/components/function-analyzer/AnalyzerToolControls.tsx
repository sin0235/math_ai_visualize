import { useEffect, useId, useState } from 'react';
import type { AnalyzeLineMode, AnalyzeTransformType } from '../../api/client';
import { TRANSFORMS } from './constants';

function DraftNumber({
  label,
  value,
  disabled,
  validate = Number.isFinite,
  errorMessage = 'Nhập một số hữu hạn.',
  onCommit,
}: {
  label: string;
  value: number;
  disabled: boolean;
  validate?: (value: number) => boolean;
  errorMessage?: string;
  onCommit: (value: number) => void;
}) {
  const errorId = useId();
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);
  const parsed = Number(draft);
  const invalid = draft.trim() === '' || !Number.isFinite(parsed) || !validate(parsed);

  function commit() {
    if (!invalid) onCommit(parsed);
  }

  return (
    <>
      <input
        className="fa2-mini-input"
        aria-label={label}
        aria-invalid={invalid}
        aria-describedby={invalid ? errorId : undefined}
        inputMode="decimal"
        type="number"
        value={draft}
        disabled={disabled}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => { if (event.key === 'Enter') commit(); }}
      />
      {invalid && <span id={errorId} className="fa2-field-error" role="alert">{errorMessage}</span>}
    </>
  );
}

function SliderNumber({ label, value, min, max, step, disabled, onChange }: { label: string; value: number; min: number; max: number; step: number; disabled: boolean; onChange: (value: number) => void }) {
  const errorId = useId();
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);
  const parsed = Number(draft);
  const invalid = draft.trim() === '' || !Number.isFinite(parsed) || parsed < min || parsed > max;

  function commit() {
    if (!invalid) onChange(parsed);
  }

  return (
    <div className="fa2-slider-row">
      <label>{label} = {formatSliderValue(value)}</label>
      <input aria-label={`${label} slider`} type="range" min={min} max={max} step={step} value={value} disabled={disabled} onChange={(event) => onChange(Number(event.target.value))} />
      <input
        className="fa2-mini-input"
        aria-label={`${label} exact value`}
        aria-invalid={invalid}
        aria-describedby={invalid ? errorId : undefined}
        type="number"
        min={min}
        max={max}
        step="any"
        value={draft}
        disabled={disabled}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => { if (event.key === 'Enter') commit(); }}
      />
      {invalid && <span id={errorId} className="fa2-field-error" role="alert">Nhập số từ {min} đến {max}.</span>}
    </div>
  );
}

export interface AnalyzerToolControlsProps {
  activeTool: 'interval' | 'line' | 'transform' | null;
  intervalA: number;
  intervalB: number;
  intervalOpenA: boolean;
  intervalOpenB: boolean;
  lineK: number;
  lineB: number;
  lineMode: AnalyzeLineMode;
  lineX0: number;
  transformType: AnalyzeTransformType;
  transformValue: number;
  isAnimatingTransform: boolean;
  animationFps: 30 | 60;
  disabled: boolean;
  onSelectTool: (key: 'interval' | 'line' | 'transform' | null) => void;
  onIntervalAChange: (value: number) => void;
  onIntervalBChange: (value: number) => void;
  onIntervalOpenAChange: (value: boolean) => void;
  onIntervalOpenBChange: (value: boolean) => void;
  onLineKChange: (value: number) => void;
  onLineBChange: (value: number) => void;
  onLineModeChange: (value: AnalyzeLineMode) => void;
  onLineX0Change: (value: number) => void;
  onTransformTypeChange: (value: AnalyzeTransformType) => void;
  onTransformValueChange: (value: number) => void;
  onAnimationFpsChange: (value: 30 | 60) => void;
  onToggleAnimation: () => void;
  onResetAnimation: () => void;
}

export function AnalyzerToolControls({
  activeTool,
  intervalA,
  intervalB,
  intervalOpenA,
  intervalOpenB,
  lineK,
  lineB,
  lineMode,
  lineX0,
  transformType,
  transformValue,
  isAnimatingTransform,
  animationFps,
  disabled,
  onSelectTool,
  onIntervalAChange,
  onIntervalBChange,
  onIntervalOpenAChange,
  onIntervalOpenBChange,
  onLineKChange,
  onLineBChange,
  onLineModeChange,
  onLineX0Change,
  onTransformTypeChange,
  onTransformValueChange,
  onAnimationFpsChange,
  onToggleAnimation,
  onResetAnimation,
}: AnalyzerToolControlsProps) {
  const enableInterval = activeTool === 'interval';
  const enableLine = activeTool === 'line';
  const enableTransform = activeTool === 'transform';

  function toggleTool(tool: NonNullable<AnalyzerToolControlsProps['activeTool']>) {
    onSelectTool(activeTool === tool ? null : tool);
  }

  return (
    <div className="fa2-tools-card">
      <div className="fa2-tool-strip" role="group" aria-label="Công cụ khảo sát">
        <button type="button" className={`fa2-tool-pill ${enableInterval ? 'is-active' : ''}`} onClick={() => toggleTool('interval')} disabled={disabled}>GTLN/GTNN</button>
        <button type="button" className={`fa2-tool-pill ${enableLine ? 'is-active' : ''}`} onClick={() => toggleTool('line')} disabled={disabled}>Đường thẳng</button>
        <button type="button" className={`fa2-tool-pill ${enableTransform ? 'is-active' : ''}`} onClick={() => toggleTool('transform')} disabled={disabled}>Biến đổi</button>
      </div>

      {(enableInterval || enableLine || enableTransform) && (
        <div className="fa2-tool-panel">
          {enableInterval && (
            <div className="fa2-tool-stack">
              <div className="fa2-tool-row" style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                <span className="fa2-tool-label" style={{ width: 100, flexShrink: 0, margin: 0 }}>Vùng khảo sát</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1, minWidth: 120 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap', margin: 0, cursor: 'pointer', fontSize: '0.85rem' }} title="Khoảng mở (không lấy dấu bằng)">
                    <input type="checkbox" checked={intervalOpenA} onChange={(e) => onIntervalOpenAChange(e.target.checked)} disabled={disabled} style={{ margin: 0 }} /> Mở
                  </label>
                  <DraftNumber
                    label="Cận trái khoảng khảo sát"
                    value={intervalA}
                    disabled={disabled}
                    validate={(value) => value < intervalB}
                    errorMessage="Cận trái phải nhỏ hơn cận phải."
                    onCommit={onIntervalAChange}
                  />
                </div>
                <span style={{ whiteSpace: 'nowrap', fontSize: '0.85rem' }}>đến</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1, minWidth: 120 }}>
                  <DraftNumber
                    label="Cận phải khoảng khảo sát"
                    value={intervalB}
                    disabled={disabled}
                    validate={(value) => value > intervalA}
                    errorMessage="Cận phải phải lớn hơn cận trái."
                    onCommit={onIntervalBChange}
                  />
                  <label style={{ display: 'flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap', margin: 0, cursor: 'pointer', fontSize: '0.85rem' }} title="Khoảng mở (không lấy dấu bằng)">
                    <input type="checkbox" checked={intervalOpenB} onChange={(e) => onIntervalOpenBChange(e.target.checked)} disabled={disabled} style={{ margin: 0 }} /> Mở
                  </label>
                </div>
              </div>
            </div>
          )}

          {enableLine && (
            <div className="fa2-tool-stack">
              <div className="fa2-tool-row">
                <span className="fa2-tool-label">Chế độ</span>
                <select className="fa2-mini-input" value={lineMode} onChange={(e) => onLineModeChange(e.target.value as AnalyzeLineMode)} disabled={disabled} style={{ flex: 1 }}>
                  <option value="intersect">Tương giao y = kx + b</option>
                  <option value="tangent_at">Tiếp tuyến tại x0</option>
                  <option value="tangent_at_point">Tiếp tuyến tại điểm P thuộc đồ thị</option>
                  <option value="normal_at">Pháp tuyến tại x0</option>
                  <option value="tangent_parallel">Tiếp tuyến song song đường có hệ số k</option>
                  <option value="tangent_perpendicular">Tiếp tuyến vuông góc đường có hệ số k</option>
                  <option value="tangent_through_point">Tiếp tuyến đi qua điểm P</option>
                </select>
              </div>
              {lineMode === 'intersect' ? (
                <>
                  <SliderNumber label="k" value={lineK} min={-5} max={5} step={0.1} disabled={disabled} onChange={onLineKChange} />
                  <SliderNumber label="b" value={lineB} min={-10} max={10} step={0.1} disabled={disabled} onChange={onLineBChange} />
                </>
              ) : lineMode === 'tangent_at' || lineMode === 'normal_at' ? (
                <SliderNumber label="x0" value={lineX0} min={-5} max={5} step={0.1} disabled={disabled} onChange={onLineX0Change} />
              ) : lineMode === 'tangent_through_point' || lineMode === 'tangent_at_point' ? (
                <>
                  <SliderNumber label="xP" value={lineX0} min={-10} max={10} step={0.1} disabled={disabled} onChange={onLineX0Change} />
                  <SliderNumber label="yP" value={lineB} min={-10} max={10} step={0.1} disabled={disabled} onChange={onLineBChange} />
                </>
              ) : (
                <SliderNumber label="k tham chiếu" value={lineK} min={-5} max={5} step={0.1} disabled={disabled} onChange={onLineKChange} />
              )}
            </div>
          )}

          {enableTransform && (
            <div className="fa2-tool-stack">
              <div className="fa2-tool-row">
                <span className="fa2-tool-label">Biến đổi</span>
                <select className="fa2-mini-input" value={transformType} onChange={(e) => onTransformTypeChange(e.target.value as AnalyzeTransformType)} disabled={disabled}>
                  {TRANSFORMS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
                {requiresTransformValue(transformType) && (
                  <>
                    <select
                      className="fa2-mini-input"
                      aria-label="Tốc độ animation"
                      value={animationFps}
                      onChange={(event) => onAnimationFpsChange(Number(event.target.value) as 30 | 60)}
                      disabled={disabled || isAnimatingTransform}
                    >
                      <option value={30}>30 FPS</option>
                      <option value={60}>60 FPS</option>
                    </select>
                    <button type="button" className="sp-btn-secondary" onClick={onToggleAnimation} disabled={disabled}>{isAnimatingTransform ? 'Tạm dừng' : 'Chạy'}</button>
                    <button type="button" className="sp-btn-secondary" onClick={onResetAnimation} disabled={disabled}>Đặt lại</button>
                  </>
                )}
              </div>
              {requiresTransformValue(transformType) && (
                <SliderNumber label="a" value={transformValue} min={-3} max={3} step={0.1} disabled={disabled} onChange={onTransformValueChange} />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function requiresTransformValue(type: AnalyzeTransformType) {
  return ['vertical_shift', 'horizontal_shift', 'vertical_scale', 'horizontal_scale'].includes(type);
}

function formatSliderValue(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
}
