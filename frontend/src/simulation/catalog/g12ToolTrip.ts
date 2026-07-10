import type { CheckpointDef, SimulationSpec, StepMissionDef } from '../types';

type TripMeta = {
  toolTripReady: boolean;
  stepMissions: StepMissionDef[];
  /** checkpoint id → unlockAtStep */
  unlock: Record<string, number>;
};

const G12_TRIP: Record<string, TripMeta> = {
  'g12.calc.derivative-survey': {
    toolTripReady: true,
    stepMissions: [
      { step: 1, title: 'Chọn hàm và điểm x₀', instruction: 'Chọn preset hoặc nhập f(x), kéo x₀. Quan sát đồ thị và giá trị f(x₀).', focusControls: ['f', 'x0'] },
      { step: 2, title: 'Cát tuyến và cho h → 0', instruction: 'Kéo h (hoặc bấm Chạy). Đọc hệ số góc cát tuyến và so với khi h nhỏ.', focusControls: ['h'] },
      { step: 3, title: 'Tiếp tuyến và f′(x₀)', instruction: 'Quan sát tiếp tuyến đỏ và |m_cát − m_tiếp|. Đọc phương trình tiếp tuyến.', focusControls: ['x0'] },
      { step: 4, title: 'Đồ thị f và f′, điểm tới hạn', instruction: 'Bật f′. Đọc các cực trị tìm được trên [a,b].', focusControls: ['showFPrime'] },
      { step: 5, title: 'Khoảng đồng / nghịch biến', instruction: 'Đọc dải màu trên đồ thị và danh sách khoảng biến thiên.', focusControls: ['a', 'b'] },
      { step: 6, title: 'Bảng biến thiên & GTLN/GTNN', instruction: 'Đối chiếu BBT với GTLN/GTNN trên đoạn. Thử đổi preset.', focusControls: ['f'] },
    ],
    unlock: { 'deriv-def': 3, 'deriv-sign': 5, 'deriv-extrema': 4 },
  },
  'g12.calc.antiderivative-family': {
    toolTripReady: true,
    stepMissions: [
      { step: 1, title: 'Nhìn hàm f dưới dấu tích phân', instruction: 'Chọn f (preset). Đây là tốc độ biến thiên của nguyên hàm.', focusControls: ['f'] },
      { step: 2, title: 'Dựng một nguyên hàm F từ mốc x*', instruction: 'Chọn mốc x*. F(x)=∫_{x*}^x f + C với C=0 ban đầu.', focusControls: ['xAnchor'] },
      { step: 3, title: 'Đổi hằng số C — tịnh tiến họ', instruction: 'Kéo C (hoặc Chạy). Họ đường chỉ dịch theo Oy.', focusControls: ['c'] },
      { step: 4, title: 'Kiểm chứng F′ ≈ f', instruction: 'Bật nhiều đường trong họ. Đọc sai số đạo hàm số max.', focusControls: ['nCompare', 'showFamily'] },
    ],
    unlock: { 'anti-c': 3, 'anti-shift': 3 },
  },
  'g12.integral.riemann-area': {
    toolTripReady: true,
    stepMissions: [
      { step: 1, title: 'Hai đường cong và giao điểm', instruction: 'Nhập/preset f, g và cận [a,b]. Quan sát giao điểm.', focusControls: ['f', 'g', 'bounds'] },
      { step: 2, title: 'Dựng tổng Riemann', instruction: 'Tăng n, bấm Chạy để xếp hình chữ nhật. Đọc xấp xỉ.', focusControls: ['n'] },
      { step: 3, title: 'Tiến tới diện tích đúng', instruction: 'So xấp xỉ Riemann với tích phân |f−g| và sai số.', focusControls: ['n'] },
      { step: 4, title: 'So left / mid / right', instruction: 'Đổi quy tắc Riemann. Bảng so sánh ba quy tắc cùng n — quan sát sai số.', focusControls: ['rule'] },
    ],
    unlock: { 'riemann-n-effect': 3, 'riemann-abs': 3, 'riemann-rule': 4 },
  },
  'g12.integral.solid-revolution': {
    toolTripReady: true,
    stepMissions: [
      { step: 1, title: 'Miền phẳng và trục quay', instruction: 'Chọn f (và g nếu washer/shell miền kẹp), trục Ox hoặc Oy, cận [a,b].', focusControls: ['f', 'axis'] },
      { step: 2, title: 'Quét khối 3D', instruction: 'Bấm Chạy để quét quanh trục. Xoay góc nhìn 3D.', focusControls: ['axis'] },
      { step: 3, title: 'Lát đĩa / vỏ tại x', instruction: 'Kéo vị trí x. Đọc bán kính / chiều cao và A(x) hoặc 2π|x|h.', focusControls: ['sliceX'] },
      { step: 4, title: 'Cộng dồn lát / vỏ', instruction: 'Tăng n, xem stack Riemann thể tích.', focusControls: ['n'] },
      { step: 5, title: 'Sai số và so sánh phương pháp', instruction: 'Đọc |Riemann−V|. Thử preset Ox disk vs Oy shell cùng miền nếu có.', focusControls: ['axis', 'n'] },
    ],
    unlock: { 'disk-formula': 3, 'shell-formula': 3, 'washer-vs-disk': 3, 'solid-scale': 5 },
  },
  'g12.integral.cross-section': {
    toolTripReady: true,
    stepMissions: [
      { step: 1, title: 'Hàm diện tích S(x)', instruction: 'Nhập s(x) và dạng lát cắt. Quan sát đồ thị S.', focusControls: ['base', 'shape'] },
      { step: 2, title: 'Một lát tại x', instruction: 'Kéo x, đọc S(x) và hình lát 3D.', focusControls: ['sliceX'] },
      { step: 3, title: 'Xếp chồng lát mỏng', instruction: 'Bấm Chạy để cộng dồn n lát.', focusControls: ['n'] },
      { step: 4, title: 'Đối chiếu với ∫S', instruction: 'So tổng xấp xỉ với thể tích tích phân.', focusControls: ['n'] },
    ],
    unlock: { 'cross-square': 1, 'cross-circle': 2 },
  },
  'g12.calc.rational-asymptote': {
    toolTripReady: true,
    stepMissions: [
      { step: 1, title: 'Nhập P, Q', instruction: 'Chọn preset hữu tỉ. Đặt cửa sổ [a,b] và x₀.', focusControls: ['num', 'den'] },
      { step: 2, title: 'TC đứng và hố', instruction: 'Đọc nghiệm mẫu: TC đứng vs hố (gián đoạn khử).', focusControls: ['num', 'den'] },
      { step: 3, title: 'Hành vi vô cùng', instruction: 'Đọc TC ngang / xiên (ước lượng số). Bật hiện xiên nếu có.', focusControls: ['showOblique'] },
      { step: 4, title: 'Đọc đồ thị gần tiệm cận', instruction: 'Kéo x₀, quan sát nhánh hai phía cực.', focusControls: ['x0'] },
      { step: 5, title: 'Dấu f′ và cực trị', instruction: 'Bật tô đồng/nghịch biến. Đọc cực trị số.', focusControls: ['showFPrimeSign'] },
      { step: 6, title: 'Tổng hợp khảo sát', instruction: 'Checklist: TXĐ, TC, cực trị — thử preset khác.', focusControls: ['num'] },
    ],
    unlock: { 'rat-vert': 2, 'rat-hole': 2, 'rat-oblique': 3 },
  },
  'g12.stat.descriptive': {
    toolTripReady: true,
    stepMissions: [
      { step: 1, title: 'Nạp dữ liệu', instruction: 'Chọn preset hoặc dán dãy số. Đọc n.', focusControls: ['raw'] },
      { step: 2, title: 'Phân bố trên trục', instruction: 'Kéo một điểm trên trục. Quan sát mean vs median đổi.', focusControls: ['dots'] },
      { step: 3, title: 'Histogram và ghép nhóm', instruction: 'Đổi độ rộng nhóm. Đọc bảng tần số.', focusControls: ['binWidth'] },
      { step: 4, title: 'Tứ phân vị và IQR', instruction: 'Đọc Q1, Q3, IQR và box trên trục.', focusControls: ['dots'] },
      { step: 5, title: 'Phương sai, σ, ngoại lệ', instruction: 'Bật loại ngoại lệ 1.5×IQR — so s trước/sau.', focusControls: ['dropOutliers'] },
    ],
    unlock: { 'stat-mean-med': 2, 'stat-var': 5, 'stat-outlier': 5 },
  },
  'g12.geom.space-coords': {
    toolTripReady: true,
    stepMissions: [
      { step: 1, title: 'Điểm A trong Oxyz', instruction: 'Chỉnh tọa độ A. Xoay khung 3D.', focusControls: ['A'] },
      { step: 2, title: 'Đường thẳng A + t u', instruction: 'Đổi vectơ u. Đọc PT tham số đường.', focusControls: ['u'] },
      { step: 3, title: 'Mặt phẳng qua P, pháp n', instruction: 'Đặt P và n. Đọc PT mp và d(A, mp).', focusControls: ['P', 'n'] },
      { step: 4, title: 'Mặt cầu tâm I, bán kính R', instruction: 'Đặt I, R. Đọc quan hệ A với cầu.', focusControls: ['I', 'R'] },
      { step: 5, title: 'Mp ∩ cầu', instruction: 'So d(I,mp) với R — không giao / tiếp / cắt (đường tròn).', focusControls: ['R', 'n'] },
      { step: 6, title: 'Góc đường–mp', instruction: 'Đọc góc Δ–mp và tổng hợp bảng số.', focusControls: ['u', 'n'] },
    ],
    unlock: { 'space-plane': 3, 'space-sphere-cut': 5, 'space-angle': 6 },
  },
  'g12.prob.bayes': {
    toolTripReady: true,
    stepMissions: [
      { step: 1, title: 'Đặt prior, độ nhạy, độ đặc hiệu', instruction: 'Chọn preset bệnh hiếm hoặc kéo slider. Viết dự đoán % trước.', focusControls: ['prior'] },
      { step: 2, title: 'Dự đoán P(B|+)', instruction: 'Nhập dự đoán và so với Bayes (chưa mở hết bảng lớn).', focusControls: ['predict'] },
      { step: 3, title: 'Đếm TP/FP trên N người', instruction: 'Tăng N, đọc TP vs FP trong nhóm dương tính.', focusControls: ['population'] },
      { step: 4, title: 'Cây và xác suất toàn phần', instruction: 'Đọc cây hai tầng và P(+).', focusControls: ['prior'] },
      { step: 5, title: 'Bayes và đối chiếu trực giác', instruction: 'Mở công thức. So P(B|+) với độ nhạy — tránh nhầm hai điều kiện.', focusControls: ['sensitivity'] },
    ],
    unlock: { 'bayes-swap': 2, 'bayes-ppv': 3, 'bayes-rare': 5 },
  },
};

export function applyG12ToolTrip(spec: SimulationSpec): SimulationSpec {
  const meta = G12_TRIP[spec.id];
  if (!meta) return spec;
  const checkpoints: CheckpointDef[] = spec.checkpoints.map((c) => ({
    ...c,
    unlockAtStep: meta.unlock[c.id] ?? c.unlockAtStep ?? 1,
  }));
  return {
    ...spec,
    checkpoints,
    stepMissions: meta.stepMissions,
    toolTripReady: meta.toolTripReady,
  };
}
