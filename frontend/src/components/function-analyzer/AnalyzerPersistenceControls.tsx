import { useEffect, useRef, useState } from 'react';
import {
  createAnalyzerHandoff,
  exportAnalyzer,
  listAnalyzerHistory,
  reanalyzeAnalyzerHistory,
  saveAnalyzerHistory,
  type AnalyzerHandoffTarget,
  type AnalyzerHistoryItem,
  type AnalyzerSessionResponse,
  type AnalyzeOptions,
  type CurriculumProfile,
} from '../../api/client';

interface AnalyzerPersistenceControlsProps {
  result: AnalyzerSessionResponse;
  profile: CurriculumProfile;
  graphWindow?: { x_min: number; x_max: number };
  tools: AnalyzeOptions;
  disabled: boolean;
  onProfileChange: (profile: CurriculumProfile) => void;
  onOpenHistory: (id: string) => Promise<void>;
}

const CHAPTERS: Record<CurriculumProfile['grade'], string> = {
  10: 'Hàm số và đồ thị',
  11: 'Giới hạn và hàm số lượng giác',
  12: 'Khảo sát hàm số',
};

export function AnalyzerPersistenceControls({
  result,
  profile,
  graphWindow,
  tools,
  disabled,
  onProfileChange,
  onOpenHistory,
}: AnalyzerPersistenceControlsProps) {
  const [openMenu, setOpenMenu] = useState<'history' | 'export' | 'handoff' | 'options' | null>(null);
  const historyOpen = openMenu === 'history';
  const [history, setHistory] = useState<AnalyzerHistoryItem[]>([]);
  const [query, setQuery] = useState('');
  const [tags, setTags] = useState('');
  const [pinned, setPinned] = useState(false);
  const [handoffTarget, setHandoffTarget] = useState<AnalyzerHandoffTarget>('algebra_solver');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const sectionRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!historyOpen) return;
    const timeout = window.setTimeout(() => void refreshHistory(), 250);
    return () => window.clearTimeout(timeout);
  }, [historyOpen, query]);

  useEffect(() => {
    if (!openMenu) return;
    function closeOnOutsideClick(event: PointerEvent) {
      if (!sectionRef.current?.contains(event.target as Node)) setOpenMenu(null);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpenMenu(null);
    }
    document.addEventListener('pointerdown', closeOnOutsideClick);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideClick);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [openMenu]);

  async function refreshHistory() {
    try {
      setHistory(await listAnalyzerHistory({ q: query }));
      setMessage(null);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Không tải được lịch sử phân tích.');
    }
  }

  async function saveCurrent() {
    setBusy(true);
    try {
      await saveAnalyzerHistory(result.analysis_id, profile, {
        tags: tags.split(',').map((tag) => tag.trim()).filter(Boolean),
        pinned,
        window: graphWindow,
        tools,
      });
      setMessage('Đã lưu kết quả.');
      if (historyOpen) await refreshHistory();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Không lưu được kết quả.');
    } finally {
      setBusy(false);
    }
  }

  async function runExport(format: 'markdown' | 'json' | 'latex' | 'pdf', template: 'full' | 'teacher_report' | 'student_worksheet' = 'full') {
    setBusy(true);
    try {
      await exportAnalyzer({ analysis_id: result.analysis_id }, format, template, profile);
      setMessage('Đã tạo file xuất.');
      setOpenMenu(null);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Không xuất được kết quả.');
    } finally {
      setBusy(false);
    }
  }

  async function openHandoff() {
    setBusy(true);
    try {
      const link = await createAnalyzerHandoff(result.analysis_id, handoffTarget);
      setOpenMenu(null);
      window.location.assign(link.url);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Không mở được công cụ đích.');
      setBusy(false);
    }
  }

  async function reanalyze(item: AnalyzerHistoryItem) {
    setBusy(true);
    try {
      const detail = await reanalyzeAnalyzerHistory(item.id, profile);
      await onOpenHistory(detail.id);
      setOpenMenu(null);
      setMessage('Đã phân tích lại bằng engine hiện tại.');
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Không phân tích lại được lịch sử.');
    } finally {
      setBusy(false);
    }
  }

  function changeGrade(grade: CurriculumProfile['grade']) {
    onProfileChange({ ...profile, grade, chapter: CHAPTERS[grade] });
  }

  function syncMenu(key: NonNullable<typeof openMenu>, open: boolean) {
    setOpenMenu((current) => open ? key : current === key ? null : current);
  }

  return (
    <section ref={sectionRef} className="fa2-actions" aria-label="Lưu và chia sẻ kết quả">
      <details className="fa2-actions-disclosure">
        <summary>
          <span>Lưu và chia sẻ</span>
          <small>Lịch sử, xuất file và công cụ khác</small>
        </summary>
        <div className="fa2-action-bar">
          <button type="button" className="sp-btn-secondary" onClick={() => void saveCurrent()} disabled={disabled || busy}>Lưu</button>
          <button type="button" className="sp-btn-secondary" onClick={() => window.print()}>In</button>

        <details className="fa2-action-menu" open={openMenu === 'history'} onToggle={(event) => syncMenu('history', event.currentTarget.open)}>
          <summary>Lịch sử</summary>
          <div className="fa2-action-popover fa2-history-popover">
            <label>
              <span>Tìm kết quả đã lưu</span>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Biểu thức hoặc chương" maxLength={256} />
            </label>
            {history.length === 0 ? <p>Chưa có kết quả phù hợp.</p> : (
              <ul>
                {history.map((item) => (
                  <li key={item.id} className="fa2-history-item">
                    <button type="button" onClick={() => void onOpenHistory(item.id)}>
                      <code>{item.original_expression}</code>
                      <span>{item.pinned ? 'Đã ghim · ' : ''}Lớp {item.grade ?? '?'} · {item.chapter ?? 'Chưa phân chương'}</span>
                    </button>
                    <button type="button" className="sp-btn-secondary" onClick={() => void reanalyze(item)} disabled={busy}>Phân tích lại</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </details>

        <details className="fa2-action-menu" open={openMenu === 'export'} onToggle={(event) => syncMenu('export', event.currentTarget.open)}>
          <summary>Xuất</summary>
          <div className="fa2-action-popover fa2-action-list">
            <button type="button" onClick={() => void runExport('pdf', 'teacher_report')} disabled={busy}>PDF giáo viên</button>
            <button type="button" onClick={() => void runExport('markdown')} disabled={busy}>Markdown</button>
            <button type="button" onClick={() => void runExport('latex', 'student_worksheet')} disabled={busy}>LaTeX bài tập</button>
            <button type="button" onClick={() => void runExport('json')} disabled={busy}>JSON</button>
          </div>
        </details>

        <details className="fa2-action-menu" open={openMenu === 'handoff'} onToggle={(event) => syncMenu('handoff', event.currentTarget.open)}>
          <summary>Mở bằng</summary>
          <div className="fa2-action-popover fa2-action-form">
            <label>
              <span>Công cụ</span>
              <select value={handoffTarget} onChange={(event) => setHandoffTarget(event.target.value as AnalyzerHandoffTarget)} disabled={busy}>
                <option value="algebra_solver">Algebra Solver</option>
                <option value="simulation">Mô phỏng khảo sát hàm</option>
                <option value="geogebra_lab">GeoGebra Lab</option>
                <option value="render">Render đồ thị</option>
                <option value="practice">Tạo đề luyện tập</option>
              </select>
            </label>
            <button type="button" className="sp-btn-primary" onClick={() => void openHandoff()} disabled={busy}>Mở công cụ</button>
          </div>
        </details>

        <details className="fa2-action-menu fa2-action-menu-end" open={openMenu === 'options'} onToggle={(event) => syncMenu('options', event.currentTarget.open)}>
          <summary>Tùy chọn bài giải</summary>
          <div className="fa2-action-popover fa2-action-form">
            <label>
              <span>Lớp</span>
              <select value={profile.grade} onChange={(event) => changeGrade(Number(event.target.value) as CurriculumProfile['grade'])} disabled={busy}>
                <option value={10}>10</option>
                <option value={11}>11</option>
                <option value={12}>12</option>
              </select>
            </label>
            <label>
              <span>Mức giải thích</span>
              <select value={profile.explanation_level} onChange={(event) => onProfileChange({ ...profile, explanation_level: event.target.value as CurriculumProfile['explanation_level'] })} disabled={busy}>
                <option value="concise">Ngắn gọn</option>
                <option value="standard">Chuẩn</option>
                <option value="detailed">Chi tiết</option>
              </select>
            </label>
            <label>
              <span>Thẻ</span>
              <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="đạo hàm, ôn thi" maxLength={160} />
            </label>
            <label className="fa2-pin-toggle"><input type="checkbox" checked={pinned} onChange={(event) => setPinned(event.target.checked)} /> Ghim khi lưu</label>
          </div>
        </details>
        </div>
      </details>
      {message && <div className="fa2-action-message" role="status">{message}</div>}
    </section>
  );
}