import { useEffect, useRef, useState } from 'react';
import { MathfieldElement } from 'mathlive';

import { getKeyboardLayouts, type MathKeyboardKind } from './keyboardLayouts';

export type MathOutputFormat = 'latex' | 'ascii-math';

interface MathFormulaFieldProps {
  value: string;
  onChange: (value: string) => void;
  keyboard: MathKeyboardKind;
  supportedActions?: ReadonlySet<string>;
  outputFormat?: MathOutputFormat;
  disabled?: boolean;
  ariaLabel: string;
  onSubmit?: () => void;
}

export function MathFormulaField({
  value,
  onChange,
  keyboard,
  supportedActions,
  outputFormat = 'latex',
  disabled = false,
  ariaLabel,
  onSubmit,
}: MathFormulaFieldProps) {
  const [keyboardVisible, setKeyboardVisible] = useState(false);
  const hostRef = useRef<HTMLDivElement>(null);
  const fieldRef = useRef<MathfieldElement | null>(null);
  const onChangeRef = useRef(onChange);
  const onSubmitRef = useRef(onSubmit);
  const formatRef = useRef(outputFormat);
  const keyboardRef = useRef(keyboard);
  const supportedActionsRef = useRef(supportedActions);

  onChangeRef.current = onChange;
  onSubmitRef.current = onSubmit;
  formatRef.current = outputFormat;
  keyboardRef.current = keyboard;
  supportedActionsRef.current = supportedActions;

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const field = new MathfieldElement();
    field.className = 'math-formula-field';
    field.setAttribute('aria-label', ariaLabel);
    field.mathVirtualKeyboardPolicy = 'manual';
    field.smartFence = true;
    field.smartMode = false;
    field.setValue(value, { silenceNotifications: true });

    const handleInput = () => onChangeRef.current(field.getValue(formatRef.current));
    const handleKeyboardToggle = () => setKeyboardVisible(window.mathVirtualKeyboard.visible);
    const handleFocus = () => {
      window.mathVirtualKeyboard.layouts = getKeyboardLayouts(keyboardRef.current, supportedActionsRef.current);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Enter' || event.shiftKey || !onSubmitRef.current) return;
      event.preventDefault();
      onSubmitRef.current();
    };

    field.addEventListener('input', handleInput);
    field.addEventListener('focus', handleFocus);
    field.addEventListener('keydown', handleKeyDown);
    window.mathVirtualKeyboard.addEventListener('virtual-keyboard-toggle', handleKeyboardToggle);
    host.append(field);
    fieldRef.current = field;

    return () => {
      field.removeEventListener('input', handleInput);
      field.removeEventListener('focus', handleFocus);
      field.removeEventListener('keydown', handleKeyDown);
      window.mathVirtualKeyboard.removeEventListener('virtual-keyboard-toggle', handleKeyboardToggle);
      field.remove();
      fieldRef.current = null;
    };
  }, [ariaLabel]);

  useEffect(() => {
    const field = fieldRef.current;
    if (!field || field.getValue(outputFormat) === value) return;
    field.setValue(value, { silenceNotifications: true });
  }, [outputFormat, value]);

  useEffect(() => {
    if (fieldRef.current) fieldRef.current.disabled = disabled;
  }, [disabled]);

  function toggleKeyboard() {
    const field = fieldRef.current;
    if (!field || disabled) return;
    field.focus();
    window.mathVirtualKeyboard.layouts = getKeyboardLayouts(keyboardRef.current, supportedActionsRef.current);
    if (window.mathVirtualKeyboard.visible) window.mathVirtualKeyboard.hide();
    else window.mathVirtualKeyboard.show();
  }

  return (
    <div className="math-formula-control">
      <div ref={hostRef} className="math-formula-host" />
      <button
        type="button"
        className="math-formula-keyboard-toggle"
        onClick={toggleKeyboard}
        disabled={disabled}
        aria-pressed={keyboardVisible}
        aria-label={keyboardVisible ? 'Ẩn bàn phím công thức' : 'Mở bàn phím công thức'}
      >
        {keyboardVisible ? 'Ẩn bàn phím' : 'Bàn phím công thức'}
      </button>
    </div>
  );
}