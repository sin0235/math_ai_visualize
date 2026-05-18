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
  lineK: number;
  lineB: number;
  transformType: string;
  transformValue: number;
  isAnimatingTransform: boolean;
  disabled: boolean;
  onToggleTool: (key: 'interval' | 'line' | 'transform', enabled: boolean) => void;
  onIntervalAChange: (value: number) => void;
  onIntervalBChange: (value: number) => void;
  onLineKChange: (value: number) => void;
  onLineBChange: (value: number) => void;
  onTransformTypeChange: (value: string) => void;
  onTransformValueChange: (value: number) => void;
  onToggleAnimation: () => void;
}

export function AnalyzerToolControls({
  enableInterval,
  enableLine,
  enableTransform,
  intervalA,
  intervalB,
  lineK,
  lineB,
  transformType,
  transformValue,
  isAnimatingTransform,
  disabled,
  onToggleTool,
  onIntervalAChange,
  onIntervalBChange,
  onLineKChange,
  onLineBChange,
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
            <div className="fa2-tool-row">
              <span className="fa2-tool-label">Đoạn [a,b]</span>
              <input className="fa2-mini-input" type="number" value={intervalA} onChange={(e) => onIntervalAChange(Number(e.target.value))} disabled={disabled} />
              <input className="fa2-mini-input" type="number" value={intervalB} onChange={(e) => onIntervalBChange(Number(e.target.value))} disabled={disabled} />
            </div>
          )}

          {enableLine && (
            <div className="fa2-tool-stack">
              <div className="fa2-tool-label">Đường thẳng y = kx + b</div>
              <SliderNumber label="k" value={lineK} min={-5} max={5} step={0.1} onChange={onLineKChange} />
              <SliderNumber label="b" value={lineB} min={-10} max={10} step={0.1} onChange={onLineBChange} />
            </div>
          )}

          {enableTransform && (
            <div className="fa2-tool-stack">
              <div className="fa2-tool-row">
                <span className="fa2-tool-label">Biến đổi</span>
                <select className="fa2-mini-input" value={transformType} onChange={(e) => onTransformTypeChange(e.target.value)} disabled={disabled}>
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
