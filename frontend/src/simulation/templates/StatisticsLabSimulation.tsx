import { useMemo, useState } from 'react';
import { KatexSpan } from '../../components/KatexSpan';
import { SliderInput } from '../../components/calculus/AreaBetweenCurvesSimulation';
import { formatNumber } from '../../utils/calculusNumerics';
import {
  computeDescriptive,
  parseDataList,
  removeOutliers,
} from '../math/descriptiveStats';

type Props = { step: number; progress: number; freeMode?: boolean };

const PRESETS: Array<{ label: string; data: string; bin: number }> = [
  { label: 'Điểm kiểm tra', data: '5 6 6 7 7 7 8 8 8 8 9 9 10 4 3 7 8 6 9 8', bin: 1 },
  { label: 'Có ngoại lệ', data: '12 13 14 14 15 15 15 16 16 17 18 35 14 15 16', bin: 2 },
  { label: 'Lương (triệu)', data: '8 9 9 10 10 10 11 11 12 12 13 15 18 22 9 10 11', bin: 2 },
  { label: 'Cân nặng', data: '48 50 51 52 53 53 54 55 55 56 57 58 60 62 65 70', bin: 3 },
];

export function StatisticsLabSimulation({ step, progress, freeMode = false }: Props) {
  const [raw, setRaw] = useState(PRESETS[0].data);
  const [binWidth, setBinWidth] = useState(1);
  const [dropOutliers, setDropOutliers] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const canRaw = freeMode || step >= 1;
  const canDrag = freeMode || step >= 2;
  const canBin = freeMode || step >= 3;
  const canOutlier = freeMode || step >= 5;

  const values = useMemo(() => {
    const list = parseDataList(raw);
    return dropOutliers ? removeOutliers(list) : list;
  }, [raw, dropOutliers]);

  const stats = useMemo(() => computeDescriptive(values, binWidth), [values, binWidth]);

  // step 3 animate histogram bars
  const barScale = step === 3 ? Math.min(1, progress + 0.08) : 1;
  const maxFreq = Math.max(1, ...stats.bins.map((b) => b.frequency));

  function updateValueAt(index: number, next: number) {
    const list = parseDataList(raw);
    if (index < 0 || index >= list.length) return;
    list[index] = Math.round(next * 10) / 10;
    setRaw(list.join(' '));
  }

  return (
    <div className="csim-module-grid csim-module-grid-wide sim-deep-grid">
      <aside className="csim-control-stack">
        <div className="csim-card">
          <div className="csim-card-head"><strong>Thống kê mô tả</strong><span>Mẫu & ghép nhóm</span></div>
          <label className={`csim-field${!canRaw ? ' is-step-locked' : ''}`}>
            <span>Dữ liệu (cách nhau bởi dấu cách / phẩy)</span>
            <textarea
              className="sim-data-input"
              rows={4}
              value={raw}
              disabled={!canRaw}
              onChange={(e) => setRaw(e.target.value)}
              spellCheck={false}
            />
          </label>
          <div className={`sim-preset-row${!canRaw ? ' is-step-locked' : ''}`}>
            {PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                className="csim-chip"
                disabled={!canRaw}
                onClick={() => {
                  setRaw(p.data);
                  setBinWidth(p.bin);
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
          <SliderInput label="Độ rộng nhóm" value={binWidth} min={0.5} max={10} step={0.5} onChange={setBinWidth} disabled={!canBin} />
          <label className={`csim-check${!canOutlier ? ' is-step-locked' : ''}`}>
            <input type="checkbox" disabled={!canOutlier} checked={dropOutliers} onChange={(e) => setDropOutliers(e.target.checked)} />
            Loại ngoại lệ (hàng rào 1.5×IQR) rồi tính lại {!canOutlier && '(bước 5)'}
          </label>
          <p className="sim-muted">n = {stats.n}. Kéo điểm trên trục (bước 2+) để xem mean/median/σ đổi realtime.</p>
        </div>

        <div className="csim-card">
          <div className="csim-card-head"><strong>Đại lượng mẫu</strong><span>không ghép nhóm</span></div>
          <div className="sim-kv-list">
            <div className="sim-kv-row"><span>Trung bình <KatexSpan tex={String.raw`\bar x`} /></span><strong>{formatNumber(stats.mean, 4)}</strong></div>
            <div className="sim-kv-row"><span>Trung vị</span><strong>{formatNumber(stats.median, 4)}</strong></div>
            <div className="sim-kv-row"><span>Mốt</span><strong>{stats.mode.length ? stats.mode.map((m) => formatNumber(m, 2)).join(', ') : '— (không rõ)'}</strong></div>
            <div className="sim-kv-row"><span>Q1 · Q3</span><strong>{formatNumber(stats.q1, 3)} · {formatNumber(stats.q3, 3)}</strong></div>
            <div className="sim-kv-row"><span>IQR</span><strong>{formatNumber(stats.iqr, 3)}</strong></div>
            <div className="sim-kv-row"><span>Khoảng biến thiên</span><strong>{formatNumber(stats.range, 3)}</strong></div>
            <div className="sim-kv-row highlight"><span>Phương sai mẫu s²</span><strong>{formatNumber(stats.variance, 4)}</strong></div>
            <div className="sim-kv-row highlight"><span>Độ lệch chuẩn s</span><strong>{formatNumber(stats.std, 4)}</strong></div>
            <div className="sim-kv-row"><span>Ngoại lệ</span><strong>{stats.outliers.length ? stats.outliers.map((v) => formatNumber(v, 2)).join(', ') : 'không'}</strong></div>
          </div>
        </div>

        <div className="csim-card">
          <div className="csim-card-head"><strong>Ước lượng ghép nhóm</strong><span>dùng giá trị đại diện</span></div>
          <div className="sim-kv-list">
            <div className="sim-kv-row"><span>Trung bình ghép nhóm</span><strong>{formatNumber(stats.groupedMean, 4)}</strong></div>
            <div className="sim-kv-row"><span>s² ghép nhóm</span><strong>{formatNumber(stats.groupedVariance, 4)}</strong></div>
            <div className="sim-kv-row"><span>s ghép nhóm</span><strong>{formatNumber(stats.groupedStd, 4)}</strong></div>
            <div className="sim-kv-row"><span>|mean − mean nhóm|</span><strong>{formatNumber(Math.abs(stats.mean - stats.groupedMean), 4)}</strong></div>
          </div>
        </div>
      </aside>

      <section className="csim-visual-stack">
        <div className="csim-card">
          <div className="csim-card-head"><strong>Histogram tần số</strong><span>bước {step}/5</span></div>
          <div className="sim-hist" role="img" aria-label="Biểu đồ tần số">
            {stats.bins.map((bin) => (
              <div key={`${bin.from}-${bin.to}`} className="sim-hist-col">
                <div
                  className="sim-hist-bar"
                  style={{ height: `${(bin.frequency / maxFreq) * 160 * barScale}px` }}
                  title={`${formatNumber(bin.from, 1)}–${formatNumber(bin.to, 1)}: ${bin.frequency}`}
                />
                <span className="sim-hist-label">{formatNumber(bin.mid, 1)}</span>
                <span className="sim-hist-freq">{bin.frequency}</span>
              </div>
            ))}
          </div>
          {step >= 4 && (
            <div className="sim-stat-markers">
              <span className="mk-mean">mean {formatNumber(stats.mean, 2)}</span>
              <span className="mk-med">median {formatNumber(stats.median, 2)}</span>
              <span className="mk-q">Q1 {formatNumber(stats.q1, 2)} · Q3 {formatNumber(stats.q3, 2)}</span>
            </div>
          )}
        </div>

        <div className="csim-card">
          <div className="csim-card-head"><strong>Trục số — điểm dữ liệu</strong><span>kéo để chỉnh</span></div>
          <DotPlot
            values={values}
            mean={stats.mean}
            median={stats.median}
            q1={stats.q1}
            q3={stats.q3}
            outliers={stats.outliers}
            showGuides={step >= 2 || freeMode}
            activeIndex={dragIndex}
            onActive={canDrag ? setDragIndex : () => undefined}
            onChange={canDrag ? updateValueAt : () => undefined}
          />
        </div>

        {step >= 3 && (
          <div className="csim-card">
            <div className="csim-card-head"><strong>Bảng tần số ghép nhóm</strong><span>giá trị đại diện = trung điểm</span></div>
            <div className="sim-bbt-scroll">
              <table className="sim-bbt-table">
                <thead>
                  <tr>
                    <th>Nhóm</th>
                    <th>Trung điểm</th>
                    <th>Tần số nᵢ</th>
                    <th>nᵢ·xᵢ</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.bins.map((b) => (
                    <tr key={`${b.from}-${b.to}`}>
                      <td>[{formatNumber(b.from, 1)}; {formatNumber(b.to, 1)})</td>
                      <td>{formatNumber(b.mid, 2)}</td>
                      <td>{b.frequency}</td>
                      <td>{formatNumber(b.mid * b.frequency, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="csim-card csim-step-copy">
          <strong>{titles[step - 1] ?? titles[0]}</strong>
          <p>{copies[step - 1] ?? copies[0]}</p>
          <ul className="sim-mono-list">
            <li>s² mẫu chia cho n−1 (không thiên vị).</li>
            <li>Ngoại lệ: ngoài [Q1−1.5·IQR, Q3+1.5·IQR].</li>
            <li>Ghép nhóm: xấp xỉ bằng trung điểm — sai lệch so với mean thô khi phân bố lệch.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

function DotPlot({
  values,
  mean,
  median,
  q1,
  q3,
  outliers,
  showGuides,
  activeIndex,
  onActive,
  onChange,
}: {
  values: number[];
  mean: number;
  median: number;
  q1: number;
  q3: number;
  outliers: number[];
  showGuides: boolean;
  activeIndex: number | null;
  onActive: (i: number | null) => void;
  onChange: (index: number, value: number) => void;
}) {
  const min = values.length ? Math.min(...values) - 1 : 0;
  const max = values.length ? Math.max(...values) + 1 : 10;
  const W = 640;
  const H = 120;
  const pad = 28;
  const scale = (v: number) => pad + ((v - min) / Math.max(max - min, 1e-6)) * (W - pad * 2);
  const outlierSet = new Set(outliers.map((v) => Math.round(v * 1000) / 1000));

  function pointerToValue(clientX: number, rect: DOMRect) {
    const x = clientX - rect.left;
    const t = (x - pad) / (W - pad * 2);
    return min + Math.min(1, Math.max(0, t)) * (max - min);
  }

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="sim-dotplot"
      onPointerMove={(e) => {
        if (activeIndex === null) return;
        const rect = e.currentTarget.getBoundingClientRect();
        onChange(activeIndex, pointerToValue(e.clientX, rect));
      }}
      onPointerUp={() => onActive(null)}
      onPointerLeave={() => onActive(null)}
    >
      <line x1={pad} x2={W - pad} y1={H - 36} y2={H - 36} className="sim-dot-axis" />
      {showGuides && Number.isFinite(mean) && (
        <line x1={scale(mean)} x2={scale(mean)} y1={20} y2={H - 28} className="sim-guide-mean" />
      )}
      {showGuides && Number.isFinite(median) && (
        <line x1={scale(median)} x2={scale(median)} y1={20} y2={H - 28} className="sim-guide-med" />
      )}
      {showGuides && Number.isFinite(q1) && Number.isFinite(q3) && (
        <rect
          x={scale(q1)}
          y={48}
          width={Math.max(2, scale(q3) - scale(q1))}
          height={20}
          className="sim-iqr-box"
        />
      )}
      {values.map((v, i) => {
        const isOut = outlierSet.has(Math.round(v * 1000) / 1000);
        return (
          <circle
            key={`${i}-${v}`}
            cx={scale(v)}
            cy={H - 52 - (i % 5) * 7}
            r={activeIndex === i ? 7 : 5.5}
            className={isOut ? 'sim-dot outlier' : 'sim-dot'}
            onPointerDown={(e) => {
              e.currentTarget.setPointerCapture(e.pointerId);
              onActive(i);
            }}
          />
        );
      })}
      <text x={pad} y={H - 14} className="csim-tick">{formatNumber(min, 1)}</text>
      <text x={W - pad} y={H - 14} textAnchor="end" className="csim-tick">{formatNumber(max, 1)}</text>
    </svg>
  );
}

const titles = [
  'Bước 1 — Nhập / chọn mẫu dữ liệu',
  'Bước 2 — Phân bố trên trục số',
  'Bước 3 — Histogram và bảng tần số ghép nhóm',
  'Bước 4 — Mean, median, tứ phân vị',
  'Bước 5 — Phương sai, σ, ngoại lệ, so ghép nhóm',
];

const copies = [
  'Dán dãy số thực tế (điểm, đo lường). Đổi độ rộng nhóm để xem độ mịn histogram.',
  'Mỗi chấm là một quan sát. Kéo chấm: mean nhạy với ngoại lệ hơn median.',
  'Ghép nhóm mất thông tin chi tiết — trung điểm xᵢ là đại diện. Tần số nᵢ đếm trong [a,b).',
  'IQR = Q3−Q1 đo độ phân tán trung tâm 50%. Box trên trục là [Q1,Q3].',
  's lớn → phân tán mạnh. Bật “loại ngoại lệ” để thấy mean/s thay đổi bao nhiêu.',
];
