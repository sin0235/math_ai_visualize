import { useRef } from 'react';

import { MathFormulaField, type MathOutputFormat } from './MathFormulaField';
import type { MathKeyboardKind } from './keyboardLayouts';

export type MathInputMode = 'natural' | 'math';

interface MathInputComposerProps {
  value: string;
  mode: MathInputMode;
  onChange: (value: string) => void;
  onModeChange: (mode: MathInputMode) => void;
  keyboard: MathKeyboardKind;
  disabled?: boolean;
  label: string;
  naturalPlaceholder: string;
  mathOutputFormat?: MathOutputFormat;
  maxLength?: number;
  onSubmit?: () => void;
}

export function MathInputComposer({
  value,
  mode,
  onChange,
  onModeChange,
  keyboard,
  disabled = false,
  label,
  naturalPlaceholder,
  mathOutputFormat = 'latex',
  maxLength = 2000,
  onSubmit,
}: MathInputComposerProps) {
  const draftsRef = useRef<Record<MathInputMode, string>>({ natural: '', math: '' });
  draftsRef.current[mode] = value;

  function selectMode(nextMode: MathInputMode) {
    if (nextMode === mode) return;
    draftsRef.current[mode] = value;
    onModeChange(nextMode);
    onChange(draftsRef.current[nextMode]);
  }

  return (
    <div className="math-input-composer">
      <div className="math-input-composer__head">
        <span className="math-input-composer__label">{label}</span>
        <div className="math-input-composer__tabs" role="tablist" aria-label="Chế độ nhập đề">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'natural'}
            className={mode === 'natural' ? 'active' : ''}
            onClick={() => selectMode('natural')}
            disabled={disabled}
          >
            Tiếng Việt
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'math'}
            className={mode === 'math' ? 'active' : ''}
            onClick={() => selectMode('math')}
            disabled={disabled}
          >
            Công thức
          </button>
        </div>
      </div>

      {mode === 'natural' ? (
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && (event.ctrlKey || event.metaKey) && onSubmit) onSubmit();
          }}
          placeholder={naturalPlaceholder}
          rows={5}
          maxLength={maxLength}
          disabled={disabled}
          aria-label={label}
        />
      ) : (
        <MathFormulaField
          value={value}
          onChange={onChange}
          keyboard={keyboard}
          outputFormat={mathOutputFormat}
          disabled={disabled}
          ariaLabel={label}
          onSubmit={onSubmit}
        />
      )}

      <div className="math-input-composer__footer">
        <span>{mode === 'natural' ? 'Ctrl + Enter để gửi' : 'Dùng Tab hoặc phím mũi tên để đi qua ô trống'}</span>
        <span aria-live="polite">{value.length}/{maxLength}</span>
      </div>
    </div>
  );
}