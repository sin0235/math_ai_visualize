import { useMemo, useState } from 'react';
import { KatexSpan } from '../../components/KatexSpan';
import { SliderInput } from '../../components/calculus/AreaBetweenCurvesSimulation';
import { formatNumber } from '../../utils/calculusNumerics';

type Props = { step: number; progress: number };

/**
 * Cây xác suất 2 tầng lớp 11: P(A), P(B|A), P(B|Ā) — hợp, giao, độc lập.
 */
export function ProbabilityTreeG11Simulation({ step, progress }: Props) {
  const [pA, setPA] = useState(0.4);
  const [pBgA, setPBgA] = useState(0.7);
  const [pBgAc, setPBgAc] = useState(0.2);
  const [n, setN] = useState(1000);

  const m = useMemo(() => {
    const pAc = 1 - pA;
    const pAandB = pA * pBgA;
    const pAandBc = pA * (1 - pBgA);
    const pAcandB = pAc * pBgAc;
    const pAcandBc = pAc * (1 - pBgAc);
    const pB = pAandB + pAcandB;
    const pBc = 1 - pB;
    const pAgB = pB > 0 ? pAandB / pB : NaN;
    // independence: P(B|A)=P(B)?
    const indep = Math.abs(pBgA - pB) < 0.02;
    const pAorB = pA + pB - pAandB;
    return {
      pAc,
      pAandB,
      pAandBc,
      pAcandB,
      pAcandBc,
      pB,
      pBc,
      pAgB,
      indep,
      pAorB,
      counts: {
        AB: pAandB * n,
        ABc: pAandBc * n,
        AcB: pAcandB * n,
        AcBc: pAcandBc * n,
      },
    };
  }, [pA, pBgA, pBgAc, n]);

  const reveal = step >= 3 ? 1 : step === 2 ? progress : 0.15;

  return (
    <div className="csim-module-grid csim-module-grid-wide sim-deep-grid">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head"><strong>Cây xác suất 2 tầng</strong><span>Lớp 11</span></div>
          <p className="sim-muted">Ví dụ: A = “chọn loại 1”, B = “thành công / đạt”.</p>
          <SliderInput label={<>P(A)</>} value={pA} min={0.05} max={0.95} step={0.01} onChange={setPA} />
          <SliderInput label={<>P(B|A)</>} value={pBgA} min={0.05} max={0.95} step={0.01} onChange={setPBgA} />
          <SliderInput label={<>P(B|Ā)</>} value={pBgAc} min={0.05} max={0.95} step={0.01} onChange={setPBgAc} />
          <SliderInput label="Minh họa trên N đối tượng" value={n} min={100} max={5000} step={100} onChange={setN} />
          <div className="sim-preset-row">
            <button type="button" className="csim-chip" onClick={() => { setPA(0.5); setPBgA(0.5); setPBgAc(0.5); }}>Độc lập mẫu</button>
            <button type="button" className="csim-chip" onClick={() => { setPA(0.3); setPBgA(0.9); setPBgAc(0.2); }}>Phụ thuộc mạnh</button>
            <button type="button" className="csim-chip" onClick={() => { setPA(0.6); setPBgA(0.4); setPBgAc(0.4); }}>P(B|A)=P(B|Ā)</button>
          </div>
        </div>

        <div className="csim-card">
          <div className="csim-card-head"><strong>Công thức</strong><span>nhân · toàn phần · hợp</span></div>
          <div className="sim-kv-list">
            <div className="sim-kv-row"><span>P(A∩B)=P(A)P(B|A)</span><strong>{formatNumber(m.pAandB, 4)}</strong></div>
            <div className="sim-kv-row"><span>P(B) toàn phần</span><strong>{formatNumber(m.pB, 4)}</strong></div>
            <div className="sim-kv-row"><span>P(A∪B)</span><strong>{formatNumber(m.pAorB, 4)}</strong></div>
            <div className="sim-kv-row"><span>P(A|B)</span><strong>{formatNumber(m.pAgB, 4)}</strong></div>
            <div className="sim-kv-row highlight"><span>A,B độc lập?</span><strong>{m.indep ? 'Gần đúng (P(B|A)≈P(B))' : 'Không (có điều kiện khác nhau)'}</strong></div>
          </div>
        </div>
      </aside>

      <section className="csim-visual-stack">
        <div className="csim-card">
          <div className="csim-card-head"><strong>Cây</strong><span>2 tầng</span></div>
          <svg viewBox="0 0 560 300" className="sim-tree-svg">
            <Node x={280} y={30} label="Ω" sub="" />
            <Edge x1={280} y1={50} x2={150} y2={110} label={`P(A)=${pct(pA)}`} opacity={reveal} />
            <Edge x1={280} y1={50} x2={410} y2={110} label={`P(Ā)=${pct(m.pAc)}`} opacity={reveal} />
            <Node x={150} y={130} label="A" sub={pct(pA)} tone="risk" />
            <Node x={410} y={130} label="Ā" sub={pct(m.pAc)} />
            <Edge x1={150} y1={150} x2={80} y2={220} label={`B ${pct(pBgA)}`} opacity={reveal} />
            <Edge x1={150} y1={150} x2={200} y2={220} label={`B̄ ${pct(1 - pBgA)}`} opacity={reveal} />
            <Edge x1={410} y1={150} x2={340} y2={220} label={`B ${pct(pBgAc)}`} opacity={reveal} />
            <Edge x1={410} y1={150} x2={480} y2={220} label={`B̄ ${pct(1 - pBgAc)}`} opacity={reveal} />
            <Node x={80} y={240} label="A∩B" sub={pct(m.pAandB)} tone="pos" />
            <Node x={200} y={240} label="A∩B̄" sub={pct(m.pAandBc)} tone="warn" />
            <Node x={340} y={240} label="Ā∩B" sub={pct(m.pAcandB)} tone="neg" />
            <Node x={480} y={240} label="Ā∩B̄" sub={pct(m.pAcandBc)} tone="ok" />
          </svg>
        </div>

        <div className="sim-bayes-visuals">
          <div className="csim-card">
            <div className="csim-card-head"><strong>Bảng đếm ≈ N={n}</strong></div>
            <table className="sim-contingency">
              <thead>
                <tr><th /><th>B</th><th>B̄</th><th>Tổng</th></tr>
              </thead>
              <tbody>
                <tr>
                  <th>A</th>
                  <td className="tone-pos">{Math.round(m.counts.AB * (step >= 3 ? 1 : reveal))}</td>
                  <td>{Math.round(m.counts.ABc * (step >= 3 ? 1 : reveal))}</td>
                  <td>{Math.round((m.counts.AB + m.counts.ABc) * (step >= 3 ? 1 : reveal))}</td>
                </tr>
                <tr>
                  <th>Ā</th>
                  <td className="tone-neg">{Math.round(m.counts.AcB * (step >= 3 ? 1 : reveal))}</td>
                  <td>{Math.round(m.counts.AcBc * (step >= 3 ? 1 : reveal))}</td>
                  <td>{Math.round((m.counts.AcB + m.counts.AcBc) * (step >= 3 ? 1 : reveal))}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div className="csim-card">
            <div className="csim-card-head"><strong>Venn (tỉ lệ)</strong></div>
            <svg viewBox="0 0 280 160" className="sim-venn">
              <rect x="10" y="10" width="260" height="140" rx="12" className="sim-venn-omega" />
              <circle cx={110} cy={80} r={52} className="sim-venn-a" opacity={0.35 + 0.4 * reveal} />
              <circle cx={170} cy={80} r={52} className="sim-venn-b" opacity={0.35 + 0.4 * reveal} />
              <text x="90" y="78" className="sim-venn-lbl">A</text>
              <text x="175" y="78" className="sim-venn-lbl">B</text>
              <text x="20" y="30" className="sim-venn-lbl">Ω</text>
            </svg>
            <p className="sim-muted">P(A∪B)=P(A)+P(B)−P(A∩B). Giao = nhánh A→B trên cây.</p>
          </div>
        </div>

        <div className="csim-card csim-step-copy">
          <strong>{titles[step - 1] ?? titles[0]}</strong>
          <p>{copies[step - 1] ?? copies[0]}</p>
        </div>
      </section>
    </div>
  );
}

function Node({ x, y, label, sub, tone }: { x: number; y: number; label: string; sub: string; tone?: string }) {
  return (
    <g transform={`translate(${x},${y})`}>
      <rect x={-48} y={-18} width={96} height={36} rx={10} className={`sim-tree-node ${tone ?? ''}`} />
      <text textAnchor="middle" y={-2} className="sim-tree-label">{label}</text>
      {sub && <text textAnchor="middle" y={12} className="sim-tree-sub">{sub}</text>}
    </g>
  );
}

function Edge({ x1, y1, x2, y2, label, opacity = 1 }: { x1: number; y1: number; x2: number; y2: number; label: string; opacity?: number }) {
  return (
    <g opacity={opacity}>
      <line x1={x1} y1={y1} x2={x2} y2={y2} className="sim-tree-edge" />
      <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 4} textAnchor="middle" className="sim-tree-edge-label">{label}</text>
    </g>
  );
}

function pct(v: number) {
  return `${formatNumber(v * 100, 1)}%`;
}

const titles = [
  'Bước 1 — Đặt P(A), P(B|A), P(B|Ā)',
  'Bước 2 — Vẽ nhánh cây và xác suất nhánh',
  'Bước 3 — Nhân dọc nhánh: P(A∩B),…',
  'Bước 4 — Xác suất toàn phần P(B)',
  'Bước 5 — Hợp, giao, độc lập, P(A|B)',
];

const copies = [
  'Tầng 1: phân hoạch A và Ā. Tầng 2: B hoặc B̄ phụ thuộc nhánh.',
  'Nhãn trên cạnh là xác suất có điều kiện theo nút cha.',
  'Xác suất lá = tích các cạnh trên đường đi.',
  'P(B)=P(B|A)P(A)+P(B|Ā)P(Ā).',
  'Độc lập ⇔ P(B|A)=P(B). Bayes sơ cấp: P(A|B)=P(A∩B)/P(B).',
];
