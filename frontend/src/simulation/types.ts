/** Schema mô phỏng v1 — chỉ frontend, public, tiếng Việt. */

export type Grade = 10 | 11 | 12;

export type Strand =
  | 'algebra'
  | 'geometry'
  | 'statistics'
  | 'calculus'
  | 'trigonometry'
  | 'probability';

export type SimulationKind =
  | 'visualization'
  | 'interactive-model'
  | 'process-simulation'
  | 'exploration-lab';

export type SimulationDims = '2d' | '3d' | 'hybrid';

export type SimulationStatus = 'draft' | 'published';

export type TemplateKey =
  | 'riemann-area'
  | 'solid-revolution'
  | 'cross-section'
  | 'unit-circle-trig'
  | 'derivative-survey'
  | 'antiderivative-family'
  | 'space-coords'
  | 'bayes-lab'
  | 'statistics-lab'
  | 'rational-asymptote';

export type CheckpointDef = {
  id: string;
  prompt: string;
  /** Đáp án số (so khớp gần đúng) hoặc chuỗi chuẩn hóa */
  kind: 'number' | 'choice';
  answer: number | string;
  tolerance?: number;
  choices?: string[];
  explanation: string;
};

export type SimulationSpec = {
  id: string;
  version: string;
  grade: Grade;
  strand: Strand;
  topicCode: string;
  title: string;
  subtitle: string;
  kind: SimulationKind;
  template: TemplateKey;
  dims: SimulationDims;
  status: SimulationStatus;
  steps: number;
  learningOutcomes: string[];
  prerequisites: string[];
  /** Câu hỏi dự đoán trước khi thao tác */
  predictPrompt: string;
  checkpoints: CheckpointDef[];
  tags: string[];
};

export type CurriculumNode = {
  id: string;
  grade: Grade;
  strand: Strand;
  topicCode: string;
  title: string;
  order: number;
};

export type StrandMeta = {
  key: Strand;
  label: string;
};

export const STRAND_LABELS: Record<Strand, string> = {
  algebra: 'Đại số',
  geometry: 'Hình học',
  statistics: 'Thống kê',
  calculus: 'Giải tích',
  trigonometry: 'Lượng giác',
  probability: 'Xác suất',
};

export const KIND_LABELS: Record<SimulationKind, string> = {
  visualization: 'Trực quan hóa',
  'interactive-model': 'Mô hình tương tác',
  'process-simulation': 'Mô phỏng quá trình',
  'exploration-lab': 'Phòng thí nghiệm',
};

export const STATUS_LABELS: Record<SimulationStatus, string> = {
  draft: 'Nháp',
  published: 'Đã xuất bản',
};
