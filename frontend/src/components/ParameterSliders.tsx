import React from 'react';
import type { Parameter } from '../types/scene';
import { clampParamValue } from '../utils/sceneParameters';

export interface ParameterSlidersProps {
  parameters: Parameter[];
  values: Record<string, number>;
  onChange: (next: Record<string, number>) => void;
  onReset?: () => void;
}

function formatValue(v: number, step: number): string {
  if (!Number.isFinite(v)) return '0';
  // Suy đoán số chữ số sau dấu phẩy theo step
  const decimals = step >= 1 ? 0 : step >= 0.1 ? 1 : 2;
  return v.toFixed(decimals).replace(/\.?0+$/, (m) => (m.startsWith('.') ? '' : m));
}

export function ParameterSliders({ parameters, values, onChange, onReset }: ParameterSlidersProps): JSX.Element | null {
  if (!parameters || parameters.length === 0) return null;

  const handleChange = (param: Parameter, raw: string): void => {
    const num = Number(raw);
    if (!Number.isFinite(num)) return;
    const clamped = clampParamValue(param, num);
    onChange({ ...values, [param.name]: clamped });
  };

  const handleNumberInput = (param: Parameter, raw: string): void => {
    const num = Number(raw);
    if (!Number.isFinite(num)) return;
    onChange({ ...values, [param.name]: clampParamValue(param, num) });
  };

  return (
    <section className="parameter-sliders" aria-label="Tham số động">
      <header className="parameter-sliders-header">
        <strong>Tham số động</strong>
        {onReset && (
          <button type="button" className="parameter-sliders-reset" onClick={onReset}>
            Đặt lại
          </button>
        )}
      </header>
      <div className="parameter-sliders-body">
        {parameters.map((param) => {
          const value = values[param.name] ?? param.default;
          return (
            <div className="parameter-slider-row" key={param.name}>
              <label className="parameter-slider-label" htmlFor={`param-${param.name}`}>
                <span className="parameter-slider-name">{param.label || param.name}</span>
                <span className="parameter-slider-value">{formatValue(value, param.step)}</span>
              </label>
              <div className="parameter-slider-controls">
                <input
                  id={`param-${param.name}`}
                  type="range"
                  min={param.min}
                  max={param.max}
                  step={param.step}
                  value={value}
                  onChange={(event) => handleChange(param, event.target.value)}
                />
                <input
                  className="parameter-slider-number"
                  type="number"
                  min={param.min}
                  max={param.max}
                  step={param.step}
                  value={value}
                  onChange={(event) => handleNumberInput(param, event.target.value)}
                />
              </div>
              <div className="parameter-slider-range">
                <span>{formatValue(param.min, param.step)}</span>
                <span>{formatValue(param.max, param.step)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default ParameterSliders;
