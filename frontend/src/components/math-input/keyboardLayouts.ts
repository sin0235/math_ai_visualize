import type { VirtualKeyboardLayout, VirtualKeyboardName } from 'mathlive';

export type MathKeyboardKind = 'algebra' | 'geometry';
export type MathKeyboardLayouts = readonly (VirtualKeyboardName | VirtualKeyboardLayout)[];

const ALGEBRA_LAYOUT: VirtualKeyboardLayout = {
  id: 'solver-algebra',
  label: 'Đại số',
  rows: [
    ['x', 'y', 'a', 'b', '7', '8', '9', '+', '-'],
    ['\\frac{#0}{#?}', '\\sqrt{#0}', '#0^{#?}', '4', '5', '6', '\\times', '\\div'],
    ['\\sin', '\\cos', '\\tan', '\\log_{#?}', '1', '2', '3', '=', '\\ne'],
    ['\\left(#0\\right)', '\\left|#0\\right|', '\\pi', '\\infty', '0', '.', '\\le', '\\ge', '[backspace]'],
  ],
};

const CALCULUS_LAYOUT: VirtualKeyboardLayout = {
  id: 'solver-calculus',
  label: 'Giải tích',
  rows: [
    ['\\frac{d}{dx}\\left(#0\\right)', '\\int_{#?}^{#?}#0\\,dx', '\\lim_{x\\to#?}#0'],
    ['x', 'e', '\\ln', '\\sin', '\\cos', '\\tan', '\\pi', '\\infty'],
    ['[left]', '[right]', '[undo]', '[redo]', '[backspace]', '[hide-keyboard]'],
  ],
};

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

export const KEYBOARD_LAYOUTS: Record<MathKeyboardKind, MathKeyboardLayouts> = {
  algebra: [ALGEBRA_LAYOUT, CALCULUS_LAYOUT],
  geometry: [GEOMETRY_LAYOUT, 'numeric'],
};