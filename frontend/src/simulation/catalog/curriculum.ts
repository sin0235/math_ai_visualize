import type { CurriculumNode, Grade, Strand } from '../types';

/** Cây chương trình tối thiểu (mã nội bộ) — đủ filter thư viện Phase 1–3. */
export const CURRICULUM_NODES: CurriculumNode[] = [
  // Lớp 10
  { id: 'g10-alg-ineq', grade: 10, strand: 'algebra', topicCode: 'g10.algebra.inequalities', title: 'Bất phương trình', order: 10 },
  { id: 'g10-alg-quad', grade: 10, strand: 'algebra', topicCode: 'g10.algebra.quadratic', title: 'Hàm số bậc hai', order: 20 },
  { id: 'g10-geo-triangle', grade: 10, strand: 'geometry', topicCode: 'g10.geometry.triangle', title: 'Hệ thức lượng trong tam giác', order: 30 },
  { id: 'g10-geo-vector', grade: 10, strand: 'geometry', topicCode: 'g10.geometry.vectors', title: 'Vectơ', order: 40 },
  { id: 'g10-stat', grade: 10, strand: 'statistics', topicCode: 'g10.statistics.descriptive', title: 'Thống kê mô tả', order: 50 },

  // Lớp 11
  { id: 'g11-trig-unit', grade: 11, strand: 'trigonometry', topicCode: 'g11.trig.unit-circle', title: 'Đường tròn lượng giác', order: 10 },
  { id: 'g11-trig-eq', grade: 11, strand: 'trigonometry', topicCode: 'g11.trig.equations', title: 'Phương trình lượng giác', order: 20 },
  { id: 'g11-calc-limit', grade: 11, strand: 'calculus', topicCode: 'g11.calc.limits', title: 'Giới hạn và liên tục', order: 30 },
  { id: 'g11-calc-deriv', grade: 11, strand: 'calculus', topicCode: 'g11.calc.derivative', title: 'Đạo hàm', order: 40 },
  { id: 'g11-geo-space', grade: 11, strand: 'geometry', topicCode: 'g11.geometry.space', title: 'Hình học không gian', order: 50 },
  { id: 'g11-prob', grade: 11, strand: 'probability', topicCode: 'g11.probability.rules', title: 'Xác suất', order: 60 },

  // Lớp 12
  { id: 'g12-calc-survey', grade: 12, strand: 'calculus', topicCode: 'g12.calc.function-survey', title: 'Khảo sát hàm số', order: 10 },
  { id: 'g12-calc-integral', grade: 12, strand: 'calculus', topicCode: 'g12.calc.integral', title: 'Nguyên hàm và tích phân', order: 20 },
  { id: 'g12-calc-solid', grade: 12, strand: 'calculus', topicCode: 'g12.calc.solid-revolution', title: 'Khối tròn xoay', order: 30 },
  { id: 'g12-geo-coords', grade: 12, strand: 'geometry', topicCode: 'g12.geometry.space-coords', title: 'Tọa độ trong không gian', order: 40 },
  { id: 'g12-prob-bayes', grade: 12, strand: 'probability', topicCode: 'g12.probability.bayes', title: 'Xác suất có điều kiện', order: 50 },
];

export function topicsForGrade(grade: Grade | 'all'): CurriculumNode[] {
  if (grade === 'all') return [...CURRICULUM_NODES].sort((a, b) => a.grade - b.grade || a.order - b.order);
  return CURRICULUM_NODES.filter((node) => node.grade === grade).sort((a, b) => a.order - b.order);
}

export function topicTitle(topicCode: string): string {
  return CURRICULUM_NODES.find((node) => node.topicCode === topicCode)?.title ?? topicCode;
}

export function strandsInCatalog(nodes: CurriculumNode[] = CURRICULUM_NODES): Strand[] {
  return Array.from(new Set(nodes.map((node) => node.strand)));
}
