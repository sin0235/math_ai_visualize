import { useMemo, useState } from 'react';
import { listSimulations } from '../catalog';
import { KIND_LABELS, STATUS_LABELS, STRAND_LABELS, type Grade, type Strand } from '../types';

type Props = {
  onOpen: (id: string) => void;
};

const GRADES: Array<Grade | 'all'> = ['all', 10, 11, 12];

export function SimulationLibraryPage({ onOpen }: Props) {
  const [grade, setGrade] = useState<Grade | 'all'>('all');
  const [strand, setStrand] = useState<Strand | 'all'>('all');
  const [query, setQuery] = useState('');

  const items = useMemo(
    () => listSimulations({ grade, strand, query, status: 'all' }),
    [grade, strand, query],
  );

  const strandOptions = useMemo(() => {
    const keys = new Set(listSimulations().map((item) => item.strand));
    return Array.from(keys) as Strand[];
  }, []);

  return (
    <section className="csim-page sim-library-page">
      <header className="sim-library-hero">
        <div>
          <p className="sim-kicker">Thư viện mô phỏng Toán THPT <span className="sim-beta-badge">Beta</span></p>
          <h1>Mô phỏng tương tác</h1>
          <p className="sim-library-lead">
            Khám phá kiến thức bằng đồ thị, animation và câu hỏi kiểm tra nhanh.
            Nội dung công khai, chạy hoàn toàn trên trình duyệt — không cần đăng nhập.
          </p>
        </div>
        <div className="sim-library-stats" aria-label="Thống kê thư viện">
          <div><strong>{listSimulations().length}</strong><span>mô phỏng</span></div>
          <div><strong>{listSimulations({ status: 'published' }).length}</strong><span>đã xuất bản</span></div>
          <div><strong>10–12</strong><span>lớp</span></div>
        </div>
      </header>

      <div className="sim-library-filters" role="search">
        <div className="sim-grade-tabs" role="tablist" aria-label="Lọc theo lớp">
          {GRADES.map((value) => (
            <button
              key={String(value)}
              type="button"
              role="tab"
              aria-selected={grade === value}
              className={grade === value ? 'active' : ''}
              onClick={() => setGrade(value)}
            >
              {value === 'all' ? 'Tất cả lớp' : `Lớp ${value}`}
            </button>
          ))}
        </div>

        <label className="sim-filter-field">
          <span>Mạch kiến thức</span>
          <select value={strand} onChange={(e) => setStrand(e.target.value as Strand | 'all')}>
            <option value="all">Tất cả mạch</option>
            {strandOptions.map((key) => (
              <option key={key} value={key}>{STRAND_LABELS[key]}</option>
            ))}
          </select>
        </label>

        <label className="sim-filter-field sim-filter-search">
          <span>Tìm kiếm</span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Riemann, lượng giác, khối tròn xoay…"
          />
        </label>
      </div>

      {items.length === 0 ? (
        <div className="sim-library-empty">
          <strong>Không có mô phỏng phù hợp</strong>
          <p>Thử đổi lớp, mạch kiến thức hoặc từ khóa tìm kiếm.</p>
        </div>
      ) : (
        <div className="sim-card-grid">
          {items.map((item) => (
            <article key={item.id} className="sim-card">
              <div className="sim-card-top">
                <span className="sim-chip">Lớp {item.grade}</span>
                <span className="sim-chip">{STRAND_LABELS[item.strand]}</span>
                <span className="sim-chip">{item.dims.toUpperCase()}</span>
                <span className={`sim-chip sim-chip-status ${item.status}`}>{STATUS_LABELS[item.status]}</span>
                {item.toolTripReady && <span className="sim-chip sim-chip-trip">Tool-trip</span>}
              </div>
              <h2>{item.title}</h2>
              <p>{item.subtitle}</p>
              <div className="sim-card-meta">
                <span>{KIND_LABELS[item.kind]}</span>
                <span>{item.steps > 1 ? `${item.steps} bước` : 'Tương tác tự do'}</span>
              </div>
              <ul className="sim-card-outcomes">
                {item.learningOutcomes.slice(0, 2).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              <button type="button" className="csim-btn csim-btn-filled sim-card-open" onClick={() => onOpen(item.id)}>
                Mở mô phỏng
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
