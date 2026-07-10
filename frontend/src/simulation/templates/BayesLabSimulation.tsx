import { useMemo, useState } from 'react';
import { KatexSpan } from '../../components/KatexSpan';
import { SliderInput } from '../../components/calculus/AreaBetweenCurvesSimulation';
import { formatNumber } from '../../utils/calculusNumerics';

type Props = { step: number; progress: number; freeMode?: boolean };

type State = {
  /** P(Bệnh) */
  prior: number;
  /** P(+|Bệnh) độ nhạy */
  sensitivity: number;
  /** P(−|Không bệnh) độ đặc hiệu */
  specificity: number;
  population: number;
  revealFormula: boolean;
};

/**
 * Lab Bayes dày: cây xác suất + bảng 1000 người + công thức + dự đoán.
 * Kịch bản xét nghiệm y khoa cổ điển — lớp 12.
 */
export function BayesLabSimulation({ step, progress, freeMode = false }: Props) {
  const [state, setState] = useState<State>({
    prior: 0.01,
    sensitivity: 0.99,
    specificity: 0.95,
    population: 1000,
    revealFormula: false,
  });
  const [prediction, setPrediction] = useState('');
  const [showAnswer, setShowAnswer] = useState(false);
  /** Soft-lock params after first compare until freeMode or step>=3 */
  const [paramsLocked, setParamsLocked] = useState(false);

  const m = useMemo(() => compute(state), [state]);

  // Animate population fill on step 3
  const shownPop = step === 3 ? Math.round(state.population * Math.min(1, progress + 0.05)) : state.population;
  const scale = shownPop / state.population;
  const canEditParams = freeMode || !paramsLocked || step >= 3;
  const canEditN = freeMode || step >= 3;
  const canFormula = freeMode || step >= 4 || state.revealFormula;

  return (
    <div className="csim-module-grid csim-module-grid-wide sim-deep-grid">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head">
            <strong>Xét nghiệm & Bayes</strong>
            <span>P(Bệnh | +)</span>
          </div>
          <p className="sim-muted">
            Bệnh hiếm, xét nghiệm rất “tốt” — trực giác thường thổi phồng xác suất mắc bệnh khi dương tính.
          </p>
          {!canEditParams && (
            <p className="sim-muted">Tham số tạm khóa sau khi so dự đoán — sang bước 3+ hoặc bật chế độ tự do để chỉnh lại.</p>
          )}
          <SliderInput
            label={<>Tỉ lệ mắc bệnh <KatexSpan tex={String.raw`P(B)`} /></>}
            value={state.prior}
            min={0.001}
            max={0.3}
            step={0.001}
            onChange={(prior) => setState({ ...state, prior })}
            disabled={!canEditParams}
          />
          <SliderInput
            label={<>Độ nhạy <KatexSpan tex={String.raw`P(+|B)`} /></>}
            value={state.sensitivity}
            min={0.5}
            max={1}
            step={0.01}
            onChange={(sensitivity) => setState({ ...state, sensitivity })}
            disabled={!canEditParams}
          />
          <SliderInput
            label={<>Độ đặc hiệu <KatexSpan tex={String.raw`P(-|\bar B)`} /></>}
            value={state.specificity}
            min={0.5}
            max={1}
            step={0.01}
            onChange={(specificity) => setState({ ...state, specificity })}
            disabled={!canEditParams}
          />
          <SliderInput
            label="Quy mô minh họa (người)"
            value={state.population}
            min={200}
            max={10000}
            step={100}
            onChange={(population) => setState({ ...state, population })}
            disabled={!canEditN}
          />
          <div className={`sim-preset-row${!canEditParams ? ' is-step-locked' : ''}`}>
            {[
              { label: 'Bệnh hiếm 1%', prior: 0.01, sensitivity: 0.99, specificity: 0.95 },
              { label: 'Bệnh 10%', prior: 0.1, sensitivity: 0.95, specificity: 0.9 },
              { label: 'Đại dịch 30%', prior: 0.3, sensitivity: 0.9, specificity: 0.85 },
            ].map((p) => (
              <button
                key={p.label}
                type="button"
                className="csim-chip"
                disabled={!canEditParams}
                onClick={() => setState((s) => ({ ...s, prior: p.prior, sensitivity: p.sensitivity, specificity: p.specificity }))}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div className="csim-card">
          <div className="csim-card-head"><strong>Đọc số</strong><span>Trên {state.population} người</span></div>
          <div className="sim-kv-list">
            <div className="sim-kv-row"><span>Mắc bệnh (ước)</span><strong>{fmtInt(m.disease * scale)}</strong></div>
            <div className="sim-kv-row"><span>Khỏe (ước)</span><strong>{fmtInt(m.healthy * scale)}</strong></div>
            <div className="sim-kv-row"><span>Dương tính thật TP</span><strong className="tone-pos">{fmtInt(m.tp * scale)}</strong></div>
            <div className="sim-kv-row"><span>Dương tính giả FP</span><strong className="tone-neg">{fmtInt(m.fp * scale)}</strong></div>
            <div className="sim-kv-row"><span>Âm tính thật TN</span><strong>{fmtInt(m.tn * scale)}</strong></div>
            <div className="sim-kv-row"><span>Âm tính giả FN</span><strong>{fmtInt(m.fn * scale)}</strong></div>
            <div className="sim-kv-row highlight"><span>P(B | +)</span><strong>{formatNumber(m.ppv * 100, 2)}%</strong></div>
            <div className="sim-kv-row"><span>P(B̄ | +)</span><strong>{formatNumber((1 - m.ppv) * 100, 2)}%</strong></div>
            <div className="sim-kv-row"><span>P(B | −) (1−NPV)</span><strong>{formatNumber((1 - m.npv) * 100, 3)}%</strong></div>
          </div>
        </div>
      </aside>

      <section className="csim-visual-stack">
        {step <= 2 && (
          <div className="csim-card sim-bayes-predict">
            <div className="csim-card-head"><strong>Dự đoán trước</strong><span>Bước 1–2</span></div>
            <p>
              Với P(B) = {formatNumber(state.prior * 100, 2)}%, độ nhạy {formatNumber(state.sensitivity * 100, 1)}%,
              độ đặc hiệu {formatNumber(state.specificity * 100, 1)}% — nếu một người <strong>dương tính</strong>,
              bạn đoán xác suất họ thật sự mắc bệnh là bao nhiêu %?
            </p>
            <label className="csim-field">
              <span>Dự đoán của bạn (%)</span>
              <input value={prediction} onChange={(e) => setPrediction(e.target.value)} inputMode="decimal" placeholder="vd: 90" />
            </label>
            <button type="button" className="csim-btn csim-btn-filled" onClick={() => { setShowAnswer(true); if (step <= 2) setParamsLocked(true); }}>So với kết quả Bayes</button>
            {showAnswer && (
              <p className="sim-checkpoint-explain">
                Kết quả đúng theo Bayes: <strong>{formatNumber(m.ppv * 100, 2)}%</strong>
                {prediction.trim() && (
                  <> — bạn đoán {prediction}%. Chênh lệch {formatNumber(Math.abs(Number(prediction.replace(',', '.')) - m.ppv * 100), 1)} điểm %.</>
                )}
                {' '}Trực giác thường cao hơn nhiều khi bệnh hiếm vì bỏ qua dương tính giả.
              </p>
            )}
          </div>
        )}

        <div className="sim-bayes-visuals">
          <div className="csim-card">
            <div className="csim-card-head"><strong>Cây xác suất</strong><span>Hai tầng</span></div>
            <svg viewBox="0 0 520 280" className="sim-tree-svg" role="img" aria-label="Cây xác suất Bayes">
              <TreeNode x={260} y={28} label="Bắt đầu" sub="" />
              <TreeEdge x1={260} y1={48} x2={140} y2={100} label={`P(B)=${pct(state.prior)}`} />
              <TreeEdge x1={260} y1={48} x2={380} y2={100} label={`P(B̄)=${pct(1 - state.prior)}`} />
              <TreeNode x={140} y={120} label="Bệnh B" sub={fmtInt(m.disease)} tone="risk" />
              <TreeNode x={380} y={120} label="Không B̄" sub={fmtInt(m.healthy)} />
              <TreeEdge x1={140} y1={140} x2={70} y2={200} label={`+ ${pct(state.sensitivity)}`} />
              <TreeEdge x1={140} y1={140} x2={200} y2={200} label={`− ${pct(1 - state.sensitivity)}`} />
              <TreeEdge x1={380} y1={140} x2={320} y2={200} label={`+ ${pct(1 - state.specificity)}`} />
              <TreeEdge x1={380} y1={140} x2={450} y2={200} label={`− ${pct(state.specificity)}`} />
              <TreeNode x={70} y={220} label="TP" sub={fmtInt(m.tp * scale)} tone="pos" />
              <TreeNode x={200} y={220} label="FN" sub={fmtInt(m.fn * scale)} tone="warn" />
              <TreeNode x={320} y={220} label="FP" sub={fmtInt(m.fp * scale)} tone="neg" />
              <TreeNode x={450} y={220} label="TN" sub={fmtInt(m.tn * scale)} tone="ok" />
            </svg>
          </div>

          <div className="csim-card">
            <div className="csim-card-head"><strong>Bảng hai chiều</strong><span>Trên {shownPop} người</span></div>
            <table className="sim-contingency">
              <thead>
                <tr>
                  <th />
                  <th>Mắc bệnh B</th>
                  <th>Không B̄</th>
                  <th>Tổng</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th>Dương tính +</th>
                  <td className="tone-pos">{fmtInt(m.tp * scale)}</td>
                  <td className="tone-neg">{fmtInt(m.fp * scale)}</td>
                  <td>{fmtInt((m.tp + m.fp) * scale)}</td>
                </tr>
                <tr>
                  <th>Âm tính −</th>
                  <td>{fmtInt(m.fn * scale)}</td>
                  <td>{fmtInt(m.tn * scale)}</td>
                  <td>{fmtInt((m.fn + m.tn) * scale)}</td>
                </tr>
                <tr>
                  <th>Tổng</th>
                  <td>{fmtInt(m.disease * scale)}</td>
                  <td>{fmtInt(m.healthy * scale)}</td>
                  <td>{fmtInt(shownPop)}</td>
                </tr>
              </tbody>
            </table>
            <p className="sim-muted">
              Trong số người dương tính, chỉ có TP là bệnh thật → P(B|+) ≈ TP / (TP+FP).
            </p>
          </div>
        </div>

        <div className="csim-card">
          <div className="csim-card-head">
            <strong>Công thức Bayes & xác suất toàn phần</strong>
            <button type="button" className="csim-btn csim-btn-ghost" onClick={() => setState({ ...state, revealFormula: !state.revealFormula })}>
              {state.revealFormula || step >= 4 ? 'Đang hiện' : 'Hiện công thức'}
            </button>
          </div>
          {canFormula && (
            <div className="sim-formula-block">
              <KatexSpan tex={String.raw`P(+)=P(+|B)P(B)+P(+|\bar B)P(\bar B)`} />
              <p>= {formatNumber(m.pPos, 6)}</p>
              <KatexSpan tex={String.raw`P(B|+)=\dfrac{P(+|B)P(B)}{P(+)}`} />
              <p className="sim-eq-line">
                = ({formatNumber(state.sensitivity, 3)} × {formatNumber(state.prior, 4)}) / {formatNumber(m.pPos, 6)}
                {' '}= <strong>{formatNumber(m.ppv, 4)}</strong> ({formatNumber(m.ppv * 100, 2)}%)
              </p>
              <KatexSpan tex={String.raw`P(\bar B|+)=1-P(B|+)`} />
              <p>So sánh với trực giác: dương tính ≠ “chắc chắn bệnh”, đặc biệt khi P(B) nhỏ.</p>
            </div>
          )}
          {!canFormula && (
            <p className="sim-muted">Sang bước 4, bật “Hiện công thức”, hoặc chế độ tự do sau khi đã quan sát bảng/cây.</p>
          )}
        </div>

        <div className="csim-card csim-step-copy">
          <strong>{stepTitles[step - 1] ?? stepTitles[0]}</strong>
          <p>{stepCopies[step - 1] ?? stepCopies[0]}</p>
        </div>

        <div className="csim-card">
          <div className="csim-card-head"><strong>Biểu đồ cột TP vs FP</strong><span>Trong nhóm dương tính</span></div>
          <div className="sim-bar-compare" aria-hidden="true">
            <div className="sim-bar tp" style={{ height: `${Math.max(8, m.ppv * 160)}px` }}>
              <span>TP {formatNumber(m.ppv * 100, 1)}%</span>
            </div>
            <div className="sim-bar fp" style={{ height: `${Math.max(8, (1 - m.ppv) * 160)}px` }}>
              <span>FP {formatNumber((1 - m.ppv) * 100, 1)}%</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function compute(state: State) {
  const disease = state.population * state.prior;
  const healthy = state.population - disease;
  const tp = disease * state.sensitivity;
  const fn = disease * (1 - state.sensitivity);
  const tn = healthy * state.specificity;
  const fp = healthy * (1 - state.specificity);
  const pPos = state.sensitivity * state.prior + (1 - state.specificity) * (1 - state.prior);
  const pNeg = 1 - pPos;
  const ppv = pPos > 0 ? (state.sensitivity * state.prior) / pPos : NaN;
  const npv = pNeg > 0 ? (state.specificity * (1 - state.prior)) / pNeg : NaN;
  return { disease, healthy, tp, fn, tn, fp, pPos, pNeg, ppv, npv };
}

function TreeNode({ x, y, label, sub, tone }: { x: number; y: number; label: string; sub: string; tone?: string }) {
  return (
    <g transform={`translate(${x}, ${y})`}>
      <rect x={-46} y={-18} width={92} height={36} rx={10} className={`sim-tree-node ${tone ?? ''}`} />
      <text textAnchor="middle" y={-2} className="sim-tree-label">{label}</text>
      {sub && <text textAnchor="middle" y={12} className="sim-tree-sub">{sub}</text>}
    </g>
  );
}

function TreeEdge({ x1, y1, x2, y2, label }: { x1: number; y1: number; x2: number; y2: number; label: string }) {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  return (
    <g>
      <line x1={x1} y1={y1} x2={x2} y2={y2} className="sim-tree-edge" />
      <text x={mx} y={my - 4} textAnchor="middle" className="sim-tree-edge-label">{label}</text>
    </g>
  );
}

function pct(v: number) {
  return `${formatNumber(v * 100, 1)}%`;
}

function fmtInt(v: number) {
  return formatNumber(Math.round(v), 0);
}

const stepTitles = [
  'Bước 1 — Đặt giả thuyết (prior, độ nhạy, độ đặc hiệu)',
  'Bước 2 — Dự đoán P(B|+) trước khi xem công thức',
  'Bước 3 — Đếm TP/FP trên quần thể minh họa',
  'Bước 4 — Cây xác suất và xác suất toàn phần',
  'Bước 5 — Áp dụng Bayes và đối chiếu trực giác',
];

const stepCopies = [
  'Ba tham số quyết định bài toán: tỉ lệ bệnh nền, khả năng bắt bệnh (độ nhạy), khả năng loại trừ đúng người khỏe (độ đặc hiệu).',
  'Viết dự đoán % trước. Nhiều người đoán ~ độ nhạy (99%) — đó là nhầm P(+|B) với P(B|+).',
  'Nhân tỉ lệ với số người để “nhìn thấy” dương tính giả. FP có thể áp đảo TP khi bệnh hiếm.',
  'Cây: nhánh bệnh/khỏe rồi +/-. P(+) = tổng xác suất các đường dẫn đến +.',
  'Bayes lật điều kiện: từ “+ nếu bệnh” sang “bệnh nếu +”. So sánh cột TP/FP trong nhóm dương tính.',
];
