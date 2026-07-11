import type { AnalyzeLineMode, AnalyzeTransformType } from '../../api/client';
import { TRANSFORMS } from './constants';

function SliderNumber({ label, value, min, max, step, onChange }: { label: string; value: number; min: number; max: number; step: number; onChange: (value: number) => void }) {
  return (
    <div className="fa2-slider-row">
      <span>{label} = {formatSliderValue(value)}</span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <input className="fa2-mini-input" type="number" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}

export interface AnalyzerToolControlsProps {
  enableInterval: boolean;
  enableLine: boolean;
  enableTransform: boolean;
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
  disabled: boolean;
  onToggleTool: (key: 'interval' | 'line' | 'transform', enabled: boolean) => void;
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
  onToggleAnimation: () => void;
}

export function AnalyzerToolControls({
  enableInterval,
  enableLine,
  enableTransform,
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
  disabled,
  onToggleTool,
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
  onToggleAnimation,
}: AnalyzerToolControlsProps) {
  return (
    <div className="fa2-tools-card">
      <div className="fa2-tool-strip" role="group" aria-label="Công cụ khảo sát">
        <button type="button" className={`fa2-tool-pill ${enableInterval ? 'is-active' : ''}`} onClick={() => onToggleTool('interval', !enableInterval)} disabled={disabled}>GTLN/GTNN</button>
        <button type="button" className={`fa2-tool-pill ${enableLine ? 'is-active' : ''}`} onClick={() => onToggleTool('line', !enableLine)} disabled={disabled}>Đường thẳng</button>
        <button type="button" className={`fa2-tool-pill ${enableTransform ? 'is-active' : ''}`} onClick={() => onToggleTool('transform', !enableTransform)} disabled={disabled}>Biến đổi</button>
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
                  <input className="fa2-mini-input" type="number" value={intervalA} onChange={(e) => onIntervalAChange(Number(e.target.value))} disabled={disabled} />
                </div>
                <span style={{ whiteSpace: 'nowrap', fontSize: '0.85rem' }}>đến</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1, minWidth: 120 }}>
                  <input className="fa2-mini-input" type="number" value={intervalB} onChange={(e) => onIntervalBChange(Number(e.target.value))} disabled={disabled} />
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
                  <option value="tangent_at">Tiếp tuyến tại điểm x0</option>
                </select>
              </div>
              {lineMode === 'tangent_at' ? (
                <SliderNumber label="x0" value={lineX0} min={-5} max={5} step={0.1} onChange={onLineX0Change} />
              ) : (
                <>
                  <SliderNumber label="k" value={lineK} min={-5} max={5} step={0.1} onChange={onLineKChange} />
                  <SliderNumber label="b" value={lineB} min={-10} max={10} step={0.1} onChange={onLineBChange} />
                </>
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
                <button type="button" className="sp-btn-secondary" onClick={onToggleAnimation} disabled={disabled}>{isAnimatingTransform ? 'Dừng' : 'Animation'}</button>
              </div>
              <SliderNumber label="a" value={transformValue} min={-3} max={3} step={0.1} onChange={onTransformValueChange} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function formatSliderValue(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
}
