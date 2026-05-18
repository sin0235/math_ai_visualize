import { KatexSpan } from './KatexSpan';
import type { RenderHistoryItem, UserResponse } from '../api/client';

type GeometryMobileView = 'render' | 'simulation' | 'geogebra-lab';

export function AccessDeniedPage({ user, onHome, onLogin }: { user: UserResponse | null; onHome: () => void; onLogin: () => void }) {
  return (
    <section className="product-page-card">
      <span className="home-eyebrow">Không thể mở trang</span>
      <h2>Bạn không có quyền truy cập khu vực này.</h2>
      <p>{user ? 'Tài khoản hiện tại không có quyền sử dụng trang này.' : 'Vui lòng đăng nhập bằng tài khoản được cấp quyền để tiếp tục.'}</p>
      <div className="home-actions">
        <button type="button" onClick={onHome}>Về trang chủ</button>
        {!user && <button type="button" className="secondary-button" onClick={onLogin}>Đăng nhập</button>}
      </div>
    </section>
  );
}

export function GuidePage({ onOpenAnalyzerGuide }: { onOpenAnalyzerGuide: () => void }) {
  const guideSteps = [
    { title: 'Nhập đề bài', text: 'Gõ đề hình học tiếng Việt, dán dữ liệu tọa độ hoặc kéo thả ảnh đề bài vào khu vực OCR.' },
    { title: 'Chọn cách hiển thị', text: 'Dùng GeoGebra cho Oxy, đồ thị hàm số; dùng Three.js cho hình học không gian hoặc mô hình 3D.' },
    { title: 'Dựng hình', text: 'Hệ thống chuyển đề bài thành hình có cấu trúc để bạn kiểm tra trực quan.' },
    { title: 'Tinh chỉnh', text: 'Kéo điểm, chỉnh scene hoặc dựng lại bằng mô tả rõ hơn khi hình chưa đúng ý.' },
  ];
  const promptTips = [
    'Nêu rõ hệ tọa độ: Oxy, Oxyz hoặc hình học không gian.',
    'Đặt tên điểm, đường, mặt phẳng nhất quán: A(1,2), B(4,5), mặt phẳng (P).',
    'Tách yêu cầu dựng hình và yêu cầu hiển thị nếu đề dài.',
    'Với OCR, kiểm tra lại ký hiệu toán học trước khi bấm dựng hình.',
  ];

  return (
    <section className="guide-page">
      <div className="guide-hero">
        <h2>Bắt đầu dựng hình toán học trong vài bước.</h2>
      </div>

      <div className="guide-grid">
        {guideSteps.map((step, index) => (
          <article className="guide-card" key={step.title}>
            <span>0{index + 1}</span>
            <h3>{step.title}</h3>
            <p>{step.text}</p>
          </article>
        ))}
      </div>

      <div className="guide-columns">
        <section>
          <h3>Thử nhanh với ví dụ này</h3>
          <p>Trong mặt phẳng Oxy, cho A(0,0), B(4,0), C(1,3). Dựng tam giác ABC, vẽ đường cao từ C xuống AB và ghi tên chân đường cao H.</p>
        </section>
        <section>
          <h3>Mẹo viết đề bài</h3>
          <ul>
            {promptTips.map((tip) => <li key={tip}>{tip}</li>)}
          </ul>
        </section>
        <section className="guide-renderer-section">
          <h3>Khi nào dùng renderer nào?</h3>
          <div className="guide-renderer-grid">
            <article>
              <h4>GeoGebra 2D</h4>
              <p>Phù hợp cho bài toán trên mặt phẳng Oxy: đồ thị hàm số, đường thẳng, đường tròn, tam giác, tứ giác và các quan hệ đồng quy - song song - vuông góc.</p>
              <ul>
                <li>Dùng khi đề chỉ có tọa độ 2D hoặc ký hiệu nằm trên mặt phẳng.</li>
                <li>Thích hợp để khảo sát hàm số, xem giao điểm, cực trị và tiệm cận.</li>
                <li>Nên chọn nếu bạn cần hình rõ, nhanh và dễ chỉnh các điểm phẳng.</li>
              </ul>
            </article>
            <article>
              <h4>GeoGebra 3D / Three.js</h4>
              <p>Phù hợp cho bài toán không gian Oxyz: khối đa diện, mặt phẳng, đường thẳng chéo nhau, giao tuyến, khoảng cách và góc trong không gian.</p>
              <ul>
                <li>Dùng khi đề có tọa độ 3D, mặt phẳng (P), đường thẳng d hoặc hình chóp/lăng trụ.</li>
                <li>Hữu ích khi cần xoay góc nhìn để kiểm tra quan hệ hình học khó thấy ở 2D.</li>
                <li>Nên chọn Three.js khi muốn thao tác trực quan mạnh hơn với mô hình 3D.</li>
              </ul>
            </article>
          </div>
          <button type="button" className="guide-analyzer-label" onClick={onOpenAnalyzerGuide}>
            <span>Hướng dẫn khảo sát hàm số</span>
            <span className="guide-analyzer-label-arrow" aria-hidden="true">→</span>
          </button>
        </section>
      </div>
    </section>
  );
}

export function AnalyzerGuidePage({ onOpenGeneralGuide }: { onOpenGeneralGuide: () => void }) {
  const formulaGroups = [
    {
      title: 'Toán tử cơ bản',
      rows: [
        { raw: '2*x, x*(x-1)', tex: '2x,\\; x(x-1)', note: 'Dùng * để nhân tường minh.' },
        { raw: '(x^2-1)/(x-2)', tex: '\\frac{x^2-1}{x-2}' },
        { raw: 'x^3 - 3*x + 2', tex: 'x^3-3x+2', note: 'Lũy thừa dùng dấu ^.' },
        { raw: 'pi, E', tex: '\\pi,\\; e' },
      ],
    },
    {
      title: 'Hàm thường gặp',
      rows: [
        { raw: 'sqrt(x^2+1), abs(x)', tex: '\\sqrt{x^2+1},\\; |x|' },
        { raw: 'exp(x), ln(x), log(x)', tex: 'e^x,\\; \\ln(x),\\; \\ln(x)' },
        { raw: 'log(x,2), log(x,10)', tex: '\\log_2(x),\\; \\log_{10}(x)', note: 'Log cơ số bất kỳ: log(x,a).' },
        { raw: 'sin(x), cos(x), tan(x)', tex: '\\sin(x),\\; \\cos(x),\\; \\tan(x)' },
        { raw: 'asin(x), acos(x), atan(x)', tex: '\\arcsin(x),\\; \\arccos(x),\\; \\arctan(x)' },
        { raw: 'sinh(x), cosh(x), tanh(x)', tex: '\\sinh(x),\\; \\cosh(x),\\; \\tanh(x)' },
      ],
    },
    {
      title: 'Hàm hỗ trợ',
      rows: [
        { raw: 'floor(x), ceil(x)', tex: '\\lfloor x \\rfloor,\\; \\lceil x \\rceil' },
        { raw: 'sign(x), Min(a,b), Max(a,b)', tex: '\\operatorname{sign}(x),\\; \\min(a,b),\\; \\max(a,b)' },
        { raw: 'Piecewise((x^2, x<0), (x, x>=0))', tex: '\\begin{cases}x^2,&x<0\\\\x,&x\\ge 0\\end{cases}' },
      ],
    },
  ];

  return (
    <section className="analyzer-guide-page">
      <div className="analyzer-guide-hero">
        <div className="analyzer-guide-hero-head">
          <h2>Hướng dẫn chi tiết cách nhập công thức và dùng OCR</h2>
          <button type="button" className="analyzer-guide-label" onClick={onOpenGeneralGuide}>
            <span>Hướng dẫn vẽ hình</span>
            <span className="analyzer-guide-label-arrow" aria-hidden="true">→</span>
          </button>
        </div>
      </div>

      <div className="analyzer-guide-grid">
        {formulaGroups.map((group) => (
          <article key={group.title} className="analyzer-guide-card">
            <h3>{group.title}</h3>
            <div className="analyzer-guide-table">
              {group.rows.map((row) => (
                <div key={row.raw} className="analyzer-guide-row">
                  <code>{row.raw}</code>
                  <KatexSpan tex={row.tex} className="analyzer-guide-katex" />
                  {row.note && <p>{row.note}</p>}
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>

      <div className="analyzer-guide-ocr">
        <article>
          <h3>OCR từ clipboard (dán ảnh)</h3>
          <ol>
            <li>Chụp/copy ảnh đề vào clipboard.</li>
            <li>Tại ô nhập hàm, bấm chuột phải để kích hoạt đọc ảnh từ clipboard.</li>
            <li>Nếu không có ảnh trong clipboard, hệ thống tự mở hộp chọn tệp ảnh.</li>
          </ol>
        </article>
        <article>
          <h3>OCR từ tệp ảnh</h3>
          <ol>
            <li>Bấm nút đính kèm ảnh (icon kẹp giấy) cạnh ô nhập.</li>
            <li>Chọn ảnh từ máy hoặc camera điện thoại.</li>
            <li>Kiểm tra lại biểu thức sau OCR rồi bấm “Phân tích”.</li>
          </ol>
        </article>
      </div>
    </section>
  );
}


export function AboutPage({ onStart, onGuide }: { onStart: () => void; onGuide: () => void }) {
  const features = [
    { title: 'Kiến trúc Phân tích & Suy luận', text: 'Quy trình xử lý đa tầng: Hệ thống phân tích giả thiết (Reasoning) trước khi thực thi lệnh vẽ, giúp tối ưu hóa độ chính xác và giảm thiểu sai sót hình học.' },
    { title: 'Tương tác Đồ họa Đa nền tảng', text: 'Kết hợp sức mạnh của GeoGebra cho toán học phẳng và Three.js cho mô phỏng không gian 3D, mang lại trải nghiệm tương tác mượt mà và trực quan.' },
    { title: 'Cấu trúc Scene JSON Linh hoạt', text: 'Hình vẽ không chỉ là ảnh tĩnh mà là một thực thể có cấu trúc (Scene-as-Code), cho phép người dùng can thiệp, kéo thả và tinh chỉnh từng đối tượng.' },
  ];

  return (
    <section className="about-page">
      <div className="about-hero">
        <span className="home-eyebrow">Về dự án</span>
        <h2>Số hóa hình học với độ chính xác tuyệt đối.</h2>
        <p>AI Math Renderer là một nền tảng tiên phong kết hợp giữa Trí tuệ nhân tạo và các công cụ tính toán hình học (CAS). Chúng tôi hướng tới việc đơn giản hóa quy trình xây dựng học liệu toán học, giúp giáo viên và học sinh tiết kiệm hàng giờ làm việc thủ công.</p>
        <div className="home-actions">
          <button type="button" onClick={onStart}>Truy cập Workspace</button>
          <button type="button" className="secondary-button" onClick={onGuide}>Tài liệu hướng dẫn</button>
        </div>
      </div>

      <div className="about-grid">
        {features.map((feature) => (
          <article key={feature.title}>
            <h3>{feature.title}</h3>
            <p>{feature.text}</p>
          </article>
        ))}
      </div>

      <section className="about-section">
        <div>
          <span>Triết lý phát triển</span>
          <h3>Trợ lý kỹ thuật đắc lực, không chỉ là công cụ vẽ hình.</h3>
        </div>
        <p>Áp dụng tư duy <strong>"Infrastructure as Code"</strong> vào toán học, chúng tôi biến các đề bài trừu tượng thành dữ liệu có cấu trúc. AI đóng vai trò là một cộng tác viên thông minh, giúp bạn hiện thực hóa các ý tưởng hình học, khảo sát đồ thị phức tạp và kiểm chứng các giả thiết toán học một cách khoa học nhất.</p>
      </section>
    </section>
  );
}


export function HistoryPage({ user, items, loading, openingId, onOpen, onDelete, onLogin, onWorkspace }: { user: UserResponse | null; items: RenderHistoryItem[]; loading: boolean; openingId: string | null; onOpen: (id: string) => void; onDelete: (id: string) => void; onLogin: () => void; onWorkspace: () => void }) {
  if (!user) {
    return (
      <section className="product-page-card">
        <span className="home-eyebrow">Lịch sử cá nhân</span>
        <h2>Đăng nhập để lưu và mở lại các lần dựng hình.</h2>
        <p>Lịch sử render chỉ được lưu cho tài khoản đã đăng nhập, giúp bạn tiếp tục chỉnh hình ở các phiên sau.</p>
        <button type="button" onClick={onLogin}>Đăng nhập</button>
      </section>
    );
  }

  return (
    <section className="product-page-card">
      <div className="page-title-row">
        <div>
          <span className="home-eyebrow">Lịch sử workspace</span>
          <h2>Lịch sử dựng hình của bạn</h2>
          <p>Mở lại đề bài, scene và renderer đã lưu từ các lần render trước.</p>
        </div>
        <button type="button" onClick={onWorkspace}>Dựng hình mới</button>
      </div>
      <HistoryPanel items={items} loading={loading} openingId={openingId} onOpen={onOpen} onDelete={onDelete} />
    </section>
  );
}


export function MetricCard({ label, value, suffix = '' }: { label: string; value: number; suffix?: string }) {
  return (
    <article className="admin-metric-card">
      <span>{label}</span>
      <strong>{value.toLocaleString('vi-VN')}{suffix}</strong>
    </article>
  );
}

export function HistoryPanel({ items, loading, openingId, onOpen, onDelete }: { items: RenderHistoryItem[]; loading: boolean; openingId: string | null; onOpen: (id: string) => void; onDelete: (id: string) => void }) {
  return (
    <section className="history-panel">
      <div className="history-panel-header">
        <strong>Lịch sử dựng hình</strong>
        <span>{loading ? 'Đang tải...' : `${items.length} mục`}</span>
      </div>
      {items.length === 0 ? (
        <p>Các lượt render mới sau khi đăng nhập sẽ được lưu vào hệ thống.</p>
      ) : (
        <div className="history-list">
          {items.map((item) => {
            const opening = openingId === item.id;
            return (
              <article className={`history-item${opening ? ' opening' : ''}`} key={item.id}>
                <button type="button" onClick={() => onOpen(item.id)} disabled={opening} aria-busy={opening}>
                  <span className="history-item-copy">
                    <strong>{item.problem_text}</strong>
                    <span>{formatHistoryDate(item.created_at)} · {historySourceLabel(item.source_type)}{item.renderer ? ` · ${item.renderer}` : ''}{item.model ? ` · ${item.model}` : ''}</span>
                  </span>
                  {opening && <span className="history-opening-indicator" aria-hidden="true"><span className="sp-spinner" /></span>}
                </button>
                <button type="button" className="history-delete" onClick={() => onDelete(item.id)} disabled={opening} aria-label="Xoá lịch sử">×</button>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

function formatHistoryDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' });
}

function historySourceLabel(sourceType: string) {
  if (sourceType === 'scene_edit') return 'chỉnh hình';
  if (sourceType === 'ocr') return 'OCR';
  return 'đề bài';
}

export function MobileRendererWarning({ dismissed, onDismiss }: { dismissed: boolean; onDismiss: () => void }) {
  if (dismissed) return null;
  return (
    <aside className="mobile-renderer-warning" role="dialog" aria-modal="true" aria-labelledby="mobile-renderer-warning-title">
      <section className="mobile-renderer-warning-card">
        <h2 id="mobile-renderer-warning-title">Xoay ngang để thao tác dễ hơn</h2>
        <p>Trên điện thoại, các công cụ dựng hình và vùng vẽ cần nhiều chiều ngang để chạm chính xác hơn.</p>
        <p>Bạn vẫn có thể tiếp tục dùng màn hình dọc nếu chỉ muốn xem nhanh kết quả.</p>
        <button type="button" className="primary-button" onClick={onDismiss}>Tiếp tục dùng dọc</button>
      </section>
    </aside>
  );
}


export function isGeometryMobileWarningView(view: string): view is GeometryMobileView {
  return view === 'render' || view === 'simulation' || view === 'geogebra-lab';
}
