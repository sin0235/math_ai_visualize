import { lazy, Suspense } from 'react';
import { KatexSpan } from './KatexSpan';
import type { RenderHistoryItem, RenderHistoryPatchRequest, UserResponse } from '../api/client';

const HomeTetrahedronShowcase = lazy(() => import('./HomeTetrahedronShowcase').then((module) => ({ default: module.HomeTetrahedronShowcase })));

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
    { title: 'Dựng hình thông minh', text: 'Chỉ cần mô tả đề bài bằng lời, hệ thống tự nhận diện các đối tượng và quan hệ hình học rồi dựng hình chính xác ngay trên màn hình. Bạn không phải vẽ tay từng bước hay căn chỉnh thủ công, mà có thể tập trung vào việc hiểu cấu trúc và logic của bài toán.' },
    { title: 'Khám phá hàm số', text: 'Khảo sát biến thiên, cực trị, tiệm cận và lập bảng giá trị trong một luồng làm việc liền mạch, đi kèm đồ thị tương tác. Mọi thông tin được trình bày có hệ thống để bạn đọc hiểu hành vi của hàm số một cách trọn vẹn thay vì chỉ nhìn vào kết quả rời rạc.' },
    { title: 'Mô phỏng sinh động', text: 'Điều chỉnh tham số và xoay góc nhìn để quan sát hình cùng đồ thị thay đổi theo thời gian thực. Cách tiếp cận trực quan này biến những khái niệm trừu tượng thành trải nghiệm có thể nhìn thấy và chạm tới, giúp trực giác toán học hình thành tự nhiên.' },
    { title: 'Không gian thực hành', text: 'Lưu lại, mở lại và thử nhiều giả thiết khác nhau trong workspace cá nhân của bạn. Mỗi bài toán trở thành một phòng thí nghiệm nhỏ, nơi bạn tự do đặt câu hỏi, kiểm chứng ý tưởng và theo dõi quá trình tư duy của chính mình qua từng lần thử.' },
  ];

  const steps = [
    { title: 'Mô tả bài toán bằng ngôn ngữ tự nhiên', text: 'Gõ đề bài, dán biểu thức hoặc đính kèm ảnh chụp đề. Bạn không cần học một cú pháp riêng nào: chỉ cần diễn đạt bài toán theo cách quen thuộc, hệ thống sẽ tự đọc hiểu nội dung và xác định những gì cần dựng.' },
    { title: 'Để hệ thống dựng hình và phân tích', text: 'Công cụ tự nhận diện quan hệ hình học, vẽ đồ thị và thực hiện các bước khảo sát cần thiết. Kết quả được trình bày dưới dạng hình ảnh, đồ thị và bảng giá trị có cấu trúc rõ ràng, sẵn sàng để bạn đọc hiểu và kiểm tra.' },
    { title: 'Tương tác, kiểm chứng và lưu lại', text: 'Xoay góc nhìn, thay đổi tham số và thử các giả thiết ngay trên màn hình để hiểu sâu hơn. Khi đã hài lòng, mỗi lần dựng hình đều có thể lưu vào workspace, giúp bạn quay lại và tiếp tục ở những phiên làm việc sau.' },
  ];

  const capabilities = [
    { title: 'Dựng hình từ ngôn ngữ', text: 'Chuyển mô tả hình học bằng lời thành mô hình 2D và 3D chính xác, giữ đúng quan hệ giữa các đối tượng được nêu trong đề bài, từ điểm, đường thẳng đến mặt phẳng và khối không gian.' },
    { title: 'Khảo sát hàm số đầy đủ', text: 'Vẽ đồ thị, xác định tập xác định, biến thiên, cực trị, tiệm cận và lập bảng giá trị trong cùng một luồng làm việc, mang lại bức tranh hoàn chỉnh về hàm số.' },
    { title: 'Mô phỏng tương tác thời gian thực', text: 'Kéo xoay, phóng to và thay đổi tham số để quan sát hình cùng đồ thị biến đổi ngay lập tức, một cách trực quan và mượt mà trên mọi thiết bị.' },
    { title: 'Đọc đề từ ảnh bằng OCR', text: 'Nhận diện biểu thức và đề bài từ ảnh chụp hoặc nội dung trong clipboard, giúp rút ngắn đáng kể thời gian nhập liệu và hạn chế sai sót khi gõ tay.' },
    { title: 'Số hóa tài liệu PDF sang Word', text: 'Chuyển tệp bài tập từ định dạng PDF sang Word để bạn dễ dàng biên soạn, chỉnh sửa, tái sử dụng và quản lý kho học liệu của riêng mình.' },
    { title: 'Workspace và lịch sử cá nhân', text: 'Lưu lại đề bài, scene và renderer của từng lần dựng hình. Toàn bộ lịch sử được giữ an toàn trong tài khoản, sẵn sàng để bạn mở lại và tiếp tục công việc bất cứ lúc nào.' },
  ];

  const audiences = [
    { title: 'Học sinh và sinh viên', text: 'Hình dung những bài toán trừu tượng thành hình ảnh cụ thể, tự kiểm chứng lời giải và từng bước xây dựng trực giác toán học vững vàng. Việc ôn tập và tự học trở nên chủ động và hiệu quả hơn.' },
    { title: 'Giáo viên và gia sư', text: 'Chuẩn bị minh họa trực quan cho bài giảng, số hóa tài liệu và trình bày những khái niệm khó theo cách sinh động, dễ tiếp thu, tiết kiệm thời gian soạn bài mà vẫn giữ được sự chính xác.' },
    { title: 'Người yêu thích toán học', text: 'Tự do thử nghiệm ý tưởng và khám phá hành vi của hàm số, hình học như đang làm việc trong một phòng thí nghiệm nhỏ của riêng mình, nơi mọi giả thuyết đều có thể được kiểm chứng ngay.' },
  ];

  return (
    <section className="about-page animate-in">
      <div className="about-hero-row">
        <div className="about-hero">
          <span className="home-eyebrow">Câu chuyện của chúng mình</span>
          <h2>Một không gian toán học để quan sát và tương tác</h2>
          <p>Chúng mình xây dựng nơi này để giúp bạn biến ý tưởng toán học thành hình ảnh trực quan, từ việc dựng hình bằng lời nói cho đến những mô phỏng sinh động có thể tương tác trực tiếp. Toán học vốn giàu hình ảnh, và mục tiêu của chúng mình là làm cho vẻ đẹp đó hiện ra rõ ràng ngay trước mắt bạn.</p>
          <p>Thay vì dừng lại ở những con số và ký hiệu tĩnh, sản phẩm kết hợp trí tuệ nhân tạo với các công cụ tính toán hiện đại để bạn vừa nhìn thấy, vừa chạm vào và vừa thử nghiệm với từng bài toán.</p>
          <p>Mọi công cụ ở đây đều hướng tới một mục tiêu: giúp bạn hiểu bản chất bài toán nhanh hơn, kiểm chứng lập luận chắc chắn hơn và học toán theo cách tự nhiên nhất.</p>
          <div className="home-actions">
            <button type="button" onClick={onStart}>Khám phá ngay</button>
            <button type="button" className="secondary-button" onClick={onGuide}>Xem hướng dẫn</button>
          </div>
        </div>

        <div className="home-visual-card home-visual-card--3d" role="region" aria-label="Minh họa tứ diện đều SABC, kéo để xoay góc nhìn.">
          <Suspense fallback={<div className="home-visual-placeholder" aria-hidden="true" />}>
            <HomeTetrahedronShowcase hideHelpers={true} />
          </Suspense>
        </div>
      </div>

      <div className="about-grid">
        {features.map((feature, index) => (
          <article key={feature.title} style={{ '--index': index } as React.CSSProperties}>
            <h3>{feature.title}</h3>
            <p>{feature.text}</p>
          </article>
        ))}
      </div>

      <section className="about-block about-steps-section">
        <div className="about-block-head">
          <span>Cách hoạt động</span>
          <h3>Từ đề bài đến hình ảnh chỉ trong ba bước</h3>
          <p>Quy trình được thiết kế gọn gàng để bạn tập trung vào tư duy toán học, còn phần dựng hình và tính toán hãy để hệ thống đảm nhận. Không cài đặt phức tạp, không cú pháp khó nhớ, chỉ là một mạch làm việc liền lạc từ ý tưởng đến kết quả.</p>
        </div>
        <ol className="about-steps">
          {steps.map((step, index) => (
            <li key={step.title}>
              <span className="about-step-index">{String(index + 1).padStart(2, '0')}</span>
              <h4>{step.title}</h4>
              <p>{step.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="about-block about-capabilities-section">
        <div className="about-block-head">
          <span>Năng lực sản phẩm</span>
          <h3>Một bộ công cụ toán học toàn diện</h3>
          <p>Các tính năng được kết nối trong cùng một không gian làm việc, giúp bạn chuyển liền mạch giữa dựng hình, khảo sát hàm số và biên soạn tài liệu mà không phải rời khỏi luồng tư duy. Mỗi công cụ đều được xây dựng để vừa mạnh mẽ vừa dễ tiếp cận.</p>
        </div>
        <div className="about-capabilities">
          {capabilities.map((item) => (
            <article key={item.title}>
              <h4>{item.title}</h4>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="about-block about-audience-section">
        <div className="about-block-head">
          <span>Dành cho ai</span>
          <h3>Phù hợp với mọi người làm việc cùng toán học</h3>
          <p>Dù bạn đang học, đang dạy hay đơn giản là tò mò với toán học, không gian này được xây dựng để đồng hành cùng cách bạn khám phá và biến những giờ làm việc với toán trở nên nhẹ nhàng hơn.</p>
        </div>
        <div className="about-audience">
          {audiences.map((item) => (
            <article key={item.title}>
              <h4>{item.title}</h4>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="about-section">
        <div>
          <span>Tầm nhìn</span>
          <h3>Toán học không chỉ là những con số</h3>
        </div>
        <p>Chúng mình tin rằng toán học sẽ trở nên gần gũi hơn rất nhiều khi được quan sát và tương tác trực tiếp, để mỗi người có thể tự do khám phá tri thức theo cách tự nhiên nhất. Đằng sau mỗi công thức là một hình ảnh, một chuyển động hay một mối quan hệ chờ được nhìn thấy, và chúng mình muốn đưa những điều đó ra ánh sáng.</p>
        <p>Mục tiêu của chúng mình là tạo ra một trải nghiệm học toán vừa trực quan vừa chính xác, nơi bất kỳ ai cũng có thể kiểm chứng, đặt câu hỏi và mở rộng hiểu biết của mình. Đây là một hành trình dài, và chúng mình sẽ tiếp tục hoàn thiện sản phẩm cùng với những người sử dụng nó mỗi ngày.</p>
      </section>

      <div className="about-cta">
        <h3>Sẵn sàng nhìn thấy bài toán của bạn</h3>
        <p>Bắt đầu với một đề bài bất kỳ và để không gian toán học này giúp bạn quan sát, kiểm chứng và hiểu sâu hơn từng ngày. Không cần chuẩn bị gì nhiều, chỉ cần một câu hỏi bạn đang muốn giải đáp.</p>
        <div className="home-actions">
          <button type="button" onClick={onStart}>Khám phá ngay</button>
          <button type="button" className="secondary-button" onClick={onGuide}>Xem hướng dẫn</button>
        </div>
      </div>
    </section>
  );
}


type HistoryPatchHandler = (id: string, patch: RenderHistoryPatchRequest) => void | Promise<void>;

export function HistoryPage({ user, items, loading, openingId, onOpen, onDelete, onPatch, onLogin, onWorkspace }: { user: UserResponse | null; items: RenderHistoryItem[]; loading: boolean; openingId: string | null; onOpen: (id: string) => void; onDelete: (id: string) => void; onPatch?: HistoryPatchHandler; onLogin: () => void; onWorkspace: () => void }) {
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
      <HistoryPanel items={items} loading={loading} openingId={openingId} onOpen={onOpen} onDelete={onDelete} onPatch={onPatch} />
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

export function HistoryPanel({ items, loading, openingId, onOpen, onDelete, onPatch }: { items: RenderHistoryItem[]; loading: boolean; openingId: string | null; onOpen: (id: string) => void; onDelete: (id: string) => void; onPatch?: HistoryPatchHandler }) {
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
            const title = historyTitle(item);
            const preview = compactHistoryText(item.problem_preview && item.problem_preview !== title ? item.problem_preview : item.problem_text, 120);
            return (
              <article className={`history-item${item.archived_at ? ' archived' : ''}`} key={item.id}>
                <button type="button" className="history-open-button" onClick={() => onOpen(item.id)} disabled={opening} aria-busy={opening}>
                  <span className="history-item-copy">
                    <strong>{title}</strong>
                    <span>{preview}</span>
                    <small>{historyMetaLine(item)}</small>
                    <span className="history-badge-row">
                      {item.is_favorite && <em>Yêu thích</em>}
                      {item.archived_at && <em>Lưu trữ</em>}
                      {item.topic && <em>{item.topic}</em>}
                      {item.grade && <em>Lớp {item.grade}</em>}
                      {item.tier && <em>{item.tier}</em>}
                      {item.tags?.map((tag) => <em key={tag}>{tag}</em>)}
                    </span>
                  </span>
                </button>
                <div className="history-item-actions">
                  {onPatch && (
                    <>
                      <button type="button" className="secondary-button" onClick={() => void onPatch(item.id, { is_favorite: !item.is_favorite })} disabled={opening}>
                        {item.is_favorite ? 'Bỏ thích' : 'Yêu thích'}
                      </button>
                      <button type="button" className="secondary-button" onClick={() => void onPatch(item.id, { archived: !item.archived_at })} disabled={opening}>
                        {item.archived_at ? 'Bỏ lưu trữ' : 'Lưu trữ'}
                      </button>
                    </>
                  )}
                  <button type="button" className="history-delete" onClick={() => onDelete(item.id)} disabled={opening} aria-label="Xoá lịch sử">×</button>
                </div>
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

function historyTitle(item: RenderHistoryItem) {
  return compactHistoryText(item.title?.trim() || item.problem_preview?.trim() || item.problem_text, 72);
}

function compactHistoryText(value: string, limit: number) {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (normalized.length <= limit) return normalized;
  return `${normalized.slice(0, limit).trimEnd()}…`;
}

function historyMetaLine(item: RenderHistoryItem) {
  return [
    formatHistoryDate(item.created_at),
    historySourceLabel(item.source_type),
    item.renderer,
    item.provider,
    item.model,
  ].filter(Boolean).join(' · ') + historyMetadataLabel(item);
}

function historySourceLabel(sourceType: string) {
  if (sourceType === 'scene_edit') return 'chỉnh hình';
  if (sourceType === 'ocr') return 'OCR';
  return 'đề bài';
}

function historyMetadataLabel(item: RenderHistoryItem) {
  const labels: string[] = [];
  if (item.ai_source === 'byok') labels.push('BYOK');
  if (item.fallback_source === 'mock') labels.push('mock fallback');
  else if (item.fallback_source === 'provider_fallback') labels.push('provider fallback');
  else if (item.degraded) labels.push('degraded');
  return labels.length ? ` · ${labels.join(' · ')}` : '';
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
