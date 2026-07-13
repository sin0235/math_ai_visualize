import type { VirtualKeyboardLayout, VirtualKeyboardName } from 'mathlive';

export type MathKeyboardKind = 'algebra' | 'geometry';
export type MathKeyboardLayouts = readonly (VirtualKeyboardName | VirtualKeyboardLayout)[];

interface CapabilityKey {
  latex: string;
  action?: string;
}

const ALGEBRA_ROWS: CapabilityKey[][] = [
  [
    { latex: 'x' }, { latex: 'y' }, { latex: 'a' }, { latex: 'b' },
    { latex: '7' }, { latex: '8' }, { latex: '9' },
    { latex: '+', action: 'plus' }, { latex: '-', action: 'minus' },
  ],
  [
    { latex: '\\frac{#0}{#?}', action: 'frac' },
    { latex: '\\sqrt{#0}', action: 'nthRoot' },
    { latex: '#0^{#?}', action: 'power' },
    { latex: '4' }, { latex: '5' }, { latex: '6' },
    { latex: '\\times', action: 'times' }, { latex: '\\div', action: 'divide' },
  ],
  [
    { latex: '\\sin', action: 'sin' }, { latex: '\\cos', action: 'cos' },
    { latex: '\\tan', action: 'tan' }, { latex: '\\log_{#?}', action: 'log' },
    { latex: '1' }, { latex: '2' }, { latex: '3' },
    { latex: '=', action: 'eq' }, { latex: '\\ne', action: 'ne' },
  ],
  [
    { latex: '\\left(#0\\right)' }, { latex: '\\left|#0\\right|', action: 'abs' },
    { latex: '\\pi', action: 'pi' }, { latex: '\\infty', action: 'infty' },
    { latex: '0' }, { latex: '.' },
    { latex: '\\le', action: 'le' }, { latex: '\\ge', action: 'ge' }, { latex: '[backspace]' },
  ],
];

const CALCULUS_ROWS: CapabilityKey[][] = [
  [
    { latex: '\\frac{d}{dx}\\left(#0\\right)', action: 'derivative' },
    { latex: '\\int_{#?}^{#?}#0\\,dx', action: 'integral' },
    { latex: '\\lim_{x\\to#?}#0', action: 'limit' },
  ],
  [
    { latex: 'x' }, { latex: 'e', action: 'e' }, { latex: '\\ln', action: 'ln' },
    { latex: '\\sin', action: 'sin' }, { latex: '\\cos', action: 'cos' },
    { latex: '\\tan', action: 'tan' }, { latex: '\\pi', action: 'pi' },
    { latex: '\\infty', action: 'infty' },
  ],
  [
    { latex: '[left]' }, { latex: '[right]' }, { latex: '[undo]' }, { latex: '[redo]' },
    { latex: '[backspace]' }, { latex: '[hide-keyboard]' },
  ],
];

const GEOMETRY_LAYOUT: VirtualKeyboardLayout = {
  id: 'solver-geometry',
  label: 'Hình học',
  rows: [
    ['d\\left(A,B\\right)', 'd\\left(A,BC\\right)', 'd\\left(A,\\left(BCD\\right)\\right)'],
    ['S\\left(ABC\\right)', 'V\\left(S.ABCD\\right)', '\\angle\\left(AB,CD\\right)'],
    ['A', 'B', 'C', 'D', 'S', 'O', '\\perp', '\\parallel'],
    ['[left]', '[right]', '[undo]', '[redo]', '[backspace]', '[hide-keyboard]'],
  ],
};

export function getKeyboardLayouts(
  kind: MathKeyboardKind,
  supportedActions?: ReadonlySet<string>,
): MathKeyboardLayouts {
  if (kind === 'geometry') return [GEOMETRY_LAYOUT, 'numeric'];
  const algebra = buildLayout('solver-algebra', 'Đại số', ALGEBRA_ROWS, supportedActions);
  const calculus = buildLayout('solver-calculus', 'Giải tích', CALCULUS_ROWS, supportedActions);
  return [algebra, calculus];
}

function buildLayout(
  id: string,
  label: string,
  rows: CapabilityKey[][],
  supportedActions?: ReadonlySet<string>,
): VirtualKeyboardLayout {
  return {
    id,
    label,
    rows: rows
      .map((row) => row.filter((key) => !key.action || supportedActions?.has(key.action)).map((key) => key.latex))
      .filter((row) => row.length > 0),
  };
}