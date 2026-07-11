import { useEffect, useState } from 'react';
import {
  createAnalyzerHandoff,
  createAnalyzerShare,
  exportAnalyzer,
  listAnalyzerHistory,
  reanalyzeAnalyzerHistory,
  revokeAnalyzerLink,
  saveAnalyzerHistory,
  type AnalyzerHandoffTarget,
  type AnalyzerHistoryItem,
  type AnalyzerSessionResponse,
  type AnalyzeOptions,
  type CurriculumProfile,
} from '../../api/client';

interface AnalyzerPersistenceControlsProps {
  result: AnalyzerSessionResponse | null;
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
  const [historyOpen, setHistoryOpen] = useState(false);
  const [history, setHistory] = useState<AnalyzerHistoryItem[]>([]);
  const [query, setQuery] = useState('');
  const [tags, setTags] = useState('');
  const [pinned, setPinned] = useState(false);
  const [handoffTarget, setHandoffTarget] = useState<AnalyzerHandoffTarget>('algebra_solver');
  const [shareVisibility, setShareVisibility] = useState<'user' | 'public'>('user');
  const [shareExpiryMinutes, setShareExpiryMinutes] = useState(1440);
  const [lastShare, setLastShare] = useState<{ shortId: string; url: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!historyOpen) return;
    const timeout = window.setTimeout(() => void refreshHistory(), 250);
    return () => window.clearTimeout(timeout);
  }, [historyOpen, query]);

  async function refreshHistory() {
    try {
      setHistory(await listAnalyzerHistory({ q: query }));
      setMessage(null);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Không tải được lịch sử analyzer.');
    }
  }

  async function saveCurrent() {
    if (!result) return;
    setBusy(true);
    try {
      await saveAnalyzerHistory(result.analysis_id, profile, {
        tags: tags.split(',').map((tag) => tag.trim()).filter(Boolean),
        pinned,
        window: graphWindow,
        tools,
      });
      setMessage('Đã lưu lịch sử analyzer.');
      if (historyOpen) await refreshHistory();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Không lưu được lịch sử analyzer.');
    } finally {
      setBusy(false);
    }
  }

  async function runExport(format: 'markdown' | 'json' | 'latex' | 'pdf', template: 'full' | 'teacher_report' | 'student_worksheet' = 'full') {
    if (!result) return;
    setBusy(true);
    try {
      await exportAnalyzer({ analysis_id: result.analysis_id }, format, template, profile);
      setMessage(null);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Không xuất được kết quả analyzer.');
    } finally {
      setBusy(false);
    }
  }

  async function openHandoff() {
    if (!result) return;
    setBusy(true);
    try {
      const link = await createAnalyzerHandoff(result.analysis_id, handoffTarget);
      window.location.assign(link.url);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Không mở được công cụ đích.');
      setBusy(false);
    }
  }

  async function createShare() {
    if (!result) return;
    setBusy(true);
    try {
      const link = await createAnalyzerShare(result.analysis_id, handoffTarget, {
        visibility: shareVisibility,
        expires_in_minutes: shareExpiryMinutes,
        scopes: ['open'],
        max_uses: shareVisibility === 'public' ? 100 : 20,
      });
      setLastShare({ shortId: link.short_id, url: link.url });
      try {
        await navigator.clipboard.writeText(link.url);
        setMessage('Đã sao chép link chia sẻ. URL chỉ chứa short ID.');
      } catch {
        setMessage('Đã tạo link chia sẻ. Hãy sao chép URL hiển thị bên dưới.');
      }
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Không tạo được link chia sẻ.');
    } finally {
      setBusy(false);
    }
  }

  async function revokeLastShare() {
    if (!lastShare) return;
    setBusy(true);
    try {
      await revokeAnalyzerLink(lastShare.shortId);
      setLastShare(null);
      setMessage('Đã thu hồi link chia sẻ.');
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Không thu hồi được link chia sẻ.');
    } finally {
      setBusy(false);
    }
  }

  async function reanalyze(item: AnalyzerHistoryItem) {
    setBusy(true);
    try {
      const detail = await reanalyzeAnalyzerHistory(item.id, profile);
      const diff = detail.version_diff;
      setMessage(diff
        ? `Đã phân tích lại. Engine: ${diff.engine_changed ? 'đã đổi' : 'không đổi'}; kiểm chứng: ${diff.verification_changed ? 'đã đổi' : 'không đổi'}.`
        : 'Đã phân tích lại bằng engine hiện tại.');
      await onOpenHistory(detail.id);
      await refreshHistory();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Không phân tích lại được lịch sử analyzer.');
    } finally {
      setBusy(false);
    }
  }

  function changeGrade(grade: CurriculumProfile['grade']) {
    onProfileChange({ ...profile, grade, chapter: CHAPTERS[grade] });
  }

  return (
    <section className="fa2-persistence" aria-label="Lịch sử, xuất file và chương trình học">
      <div className="fa2-persistence-row">
        <label>
          Lớp
          <select value={profile.grade} onChange={(event) => changeGrade(Number(event.target.value) as CurriculumProfile['grade'])} disabled={busy}>
            <option value={10}>10</option>
            <option value={11}>11</option>
            <option value={12}>12</option>
          </select>
        </label>
        <label>
          Mức giải thích
          <select
            value={profile.explanation_level}
            onChange={(event) => onProfileChange({ ...profile, explanation_level: event.target.value as CurriculumProfile['explanation_level'] })}
            disabled={busy}
          >
            <option value="concise">Ngắn gọn</option>
            <option value="standard">Chuẩn</option>
            <option value="detailed">Chi tiết</option>
          </select>
        </label>
        <span className="fa2-curriculum-chapter">{profile.chapter}</span>
      </div>

      <div className="fa2-persistence-row">
        <label className="fa2-tags-input">
          Thẻ
          <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="đạo hàm, ôn thi" maxLength={160} />
        </label>
        <label className="fa2-pin-toggle">
          <input type="checkbox" checked={pinned} onChange={(event) => setPinned(event.target.checked)} /> Ghim
        </label>
        <button type="button" className="sp-btn-secondary" onClick={() => void saveCurrent()} disabled={disabled || busy || !result}>Lưu</button>
        <button type="button" className="sp-btn-secondary" onClick={() => setHistoryOpen((value) => !value)} aria-expanded={historyOpen}>Lịch sử</button>
        <button type="button" className="sp-btn-secondary" onClick={() => void runExport('markdown')} disabled={disabled || busy || !result}>Markdown</button>
        <button type="button" className="sp-btn-secondary" onClick={() => void runExport('pdf', 'teacher_report')} disabled={disabled || busy || !result}>PDF giáo viên</button>
        <button type="button" className="sp-btn-secondary" onClick={() => void runExport('latex', 'student_worksheet')} disabled={disabled || busy || !result}>LaTeX bài tập</button>
        <button type="button" className="sp-btn-secondary" onClick={() => void runExport('json')} disabled={disabled || busy || !result}>JSON</button>
      </div>

      <div className="fa2-persistence-row fa2-ecosystem-row">
        <label>
          Công cụ đích
          <select value={handoffTarget} onChange={(event) => setHandoffTarget(event.target.value as AnalyzerHandoffTarget)} disabled={busy}>
            <option value="algebra_solver">Algebra Solver: giải f&apos;(x)=0</option>
            <option value="simulation">Mô phỏng khảo sát hàm</option>
            <option value="geogebra_lab">GeoGebra Lab</option>
            <option value="render">Render đồ thị</option>
            <option value="practice">Tạo đề luyện tập</option>
          </select>
        </label>
        <button type="button" className="sp-btn-secondary" onClick={() => void openHandoff()} disabled={disabled || busy || !result}>Mở công cụ</button>
        <label>
          Phạm vi share
          <select value={shareVisibility} onChange={(event) => setShareVisibility(event.target.value as 'user' | 'public')} disabled={busy}>
            <option value="user">Chỉ tài khoản này</option>
            <option value="public">Công khai</option>
          </select>
        </label>
        <label>
          Hết hạn
          <select value={shareExpiryMinutes} onChange={(event) => setShareExpiryMinutes(Number(event.target.value))} disabled={busy}>
            <option value={60}>1 giờ</option>
            <option value={1440}>1 ngày</option>
            <option value={10080}>7 ngày</option>
          </select>
        </label>
        <button type="button" className="sp-btn-secondary" onClick={() => void createShare()} disabled={disabled || busy || !result}>Tạo link</button>
        {lastShare && <button type="button" className="sp-btn-secondary" onClick={() => void revokeLastShare()} disabled={busy}>Thu hồi link</button>}
      </div>

      {lastShare && <output className="fa2-share-output" aria-label="Link chia sẻ vừa tạo">{lastShare.url}</output>}
      {message && <div className="fa2-persistence-message" role="status">{message}</div>}
      {historyOpen && (
        <div className="fa2-history-drawer">
          <label>
            Tìm lịch sử
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Biểu thức hoặc chương" maxLength={256} />
          </label>
          {history.length === 0 ? <p>Chưa có lịch sử phù hợp.</p> : (
            <ul>
              {history.map((item) => (
                <li key={item.id}>
                  <div className="fa2-history-item">
                    <button type="button" onClick={() => void onOpenHistory(item.id)}>
                      <code>{item.original_expression}</code>
                      <span>{item.pinned ? 'Đã ghim · ' : ''}Lớp {item.grade ?? '?'} · {item.chapter ?? 'Chưa phân chương'} · {item.engine_version}</span>
                    </button>
                    <button type="button" className="sp-btn-secondary" onClick={() => void reanalyze(item)} disabled={busy}>Phân tích lại</button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}