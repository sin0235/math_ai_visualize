import { useEffect, useRef } from 'react';
import { MathfieldElement } from 'mathlive';

import { KEYBOARD_LAYOUTS, type MathKeyboardKind } from './keyboardLayouts';

export type MathOutputFormat = 'latex' | 'ascii-math';

interface MathFormulaFieldProps {
  value: string;
  onChange: (value: string) => void;
  keyboard: MathKeyboardKind;
  outputFormat?: MathOutputFormat;
  disabled?: boolean;
  ariaLabel: string;
  onSubmit?: () => void;
}

export function MathFormulaField({
  value,
  onChange,
  keyboard,
  outputFormat = 'latex',
  disabled = false,
  ariaLabel,
  onSubmit,
}: MathFormulaFieldProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const fieldRef = useRef<MathfieldElement | null>(null);
  const onChangeRef = useRef(onChange);
  const onSubmitRef = useRef(onSubmit);
  const formatRef = useRef(outputFormat);
  const keyboardRef = useRef(keyboard);

  onChangeRef.current = onChange;
  onSubmitRef.current = onSubmit;
  formatRef.current = outputFormat;
  keyboardRef.current = keyboard;

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const field = new MathfieldElement();
    field.className = 'math-formula-field';
    field.setAttribute('aria-label', ariaLabel);
    field.mathVirtualKeyboardPolicy = 'auto';
    field.smartFence = true;
    field.smartMode = false;
    field.setValue(value, { silenceNotifications: true });

    const handleInput = () => onChangeRef.current(field.getValue(formatRef.current));
    const handleFocus = () => {
      window.mathVirtualKeyboard.layouts = KEYBOARD_LAYOUTS[keyboardRef.current];
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Enter' || event.shiftKey || !onSubmitRef.current) return;
      event.preventDefault();
      onSubmitRef.current();
    };

    field.addEventListener('input', handleInput);
    field.addEventListener('focus', handleFocus);
    field.addEventListener('keydown', handleKeyDown);
    host.append(field);
    fieldRef.current = field;

    return () => {
      field.removeEventListener('input', handleInput);
      field.removeEventListener('focus', handleFocus);
      field.removeEventListener('keydown', handleKeyDown);
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

  return <div ref={hostRef} className="math-formula-host" />;
}