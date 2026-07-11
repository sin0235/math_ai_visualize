import type { AnalyzeTransformType } from '../../api/client';

export const EXAMPLE_GROUPS = [
  {
    label: 'Đa thức',
    items: [
      { label: 'Bậc 2', value: 'x^2 - 4*x + 3' },
      { label: 'Bậc 3', value: 'x^3 - 3*x + 2' },
      { label: 'Bậc 4', value: 'x^4 - 8*x^2' },
    ],
  },
  {
    label: 'Hàm đặc biệt',
    items: [
      { label: 'Phân thức', value: '(x^2 - 1)/(x - 2)' },
      { label: 'Căn', value: 'sqrt(x^2 + 1)' },
      { label: 'Mũ', value: 'exp(x)' },
      { label: 'Logarit', value: 'log(x)' },
    ],
  },
];

export const TRANSFORMS = [
  { value: 'vertical_shift', label: 'f(x) + a' },
  { value: 'horizontal_shift', label: 'f(x + a)' },
  { value: 'vertical_scale', label: 'a·f(x)' },
  { value: 'horizontal_scale', label: 'f(a·x)' },
  { value: 'reflect_x', label: '-f(x)' },
  { value: 'reflect_y', label: 'f(-x)' },
  { value: 'absolute_all', label: '|f(x)|' },
  { value: 'absolute_x', label: 'f(|x|)' },
] satisfies ReadonlyArray<{ value: AnalyzeTransformType; label: string }>;

export const TRANSFORM_LABEL_TEX: Record<string, string> = {
  vertical_shift: 'g(x)=f(x)+a',
  horizontal_shift: 'g(x)=f(x+a)',
  vertical_scale: 'g(x)=a f(x)',
  horizontal_scale: 'g(x)=f(a x)',
  reflect_x: 'g(x)=-f(x)',
  reflect_y: 'g(x)=f(-x)',
  absolute_all: 'g(x)=|f(x)|',
  absolute_x: 'g(x)=f(|x|)',
};
