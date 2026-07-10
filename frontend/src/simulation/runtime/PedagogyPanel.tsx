import { useMemo, useState } from 'react';
import type { CheckpointDef, SimulationSpec } from '../types';

type Props = {
  spec: SimulationSpec;
  step?: number;
  freeMode?: boolean;
};

type AnswerState = Record<string, { choice?: string; number?: string; checked: boolean; correct?: boolean }>;

export function PedagogyPanel({ spec, step = 1, freeMode = false }: Props) {
  const [predictOpen, setPredictOpen] = useState(true);
  const [predictNote, setPredictNote] = useState('');
  const [answers, setAnswers] = useState<AnswerState>({});

  const outcomes = useMemo(() => spec.learningOutcomes, [spec.learningOutcomes]);

  const visibleCheckpoints = useMemo(() => {
    if (freeMode) return spec.checkpoints;
    return spec.checkpoints.filter((item) => (item.unlockAtStep ?? 1) <= step);
  }, [spec.checkpoints, step, freeMode]);

  const lockedCount = spec.checkpoints.length - visibleCheckpoints.length;

  function checkCheckpoint(item: CheckpointDef) {
    setAnswers((current) => {
      const entry = current[item.id] ?? { checked: false };
      let correct = false;
      if (item.kind === 'choice') {
        correct = (entry.choice ?? '') === String(item.answer);
      } else {
        const raw = Number(String(entry.number ?? '').replace(',', '.'));
        const expected = Number(item.answer);
        const tol = item.tolerance ?? 1e-2;
        correct = Number.isFinite(raw) && Math.abs(raw - expected) <= tol;
      }
      return { ...current, [item.id]: { ...entry, checked: true, correct } };
    });
  }

  return (
    <aside className="sim-pedagogy" aria-label="Hoạt động học tập">
      <div className="sim-pedagogy-card">
        <div className="sim-pedagogy-head">
          <strong>Mục tiêu cần đạt</strong>
          <span>Lớp {spec.grade}</span>
        </div>
        <ul className="sim-pedagogy-list">
          {outcomes.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        {spec.prerequisites.length > 0 && (
          <p className="sim-pedagogy-prereq">
            <strong>Tiên quyết:</strong> {spec.prerequisites.join(' · ')}
          </p>
        )}
      </div>

      <div className="sim-pedagogy-card">
        <button type="button" className="sim-pedagogy-toggle" onClick={() => setPredictOpen((v) => !v)} aria-expanded={predictOpen}>
          <strong>Dự đoán trước khi thao tác</strong>
          <span>{predictOpen ? 'Thu gọn' : 'Mở'}</span>
        </button>
        {predictOpen && (
          <div className="sim-pedagogy-body">
            <p>{spec.predictPrompt}</p>
            <label className="sim-pedagogy-field">
              <span>Ghi chú dự đoán (chỉ trên máy bạn, không gửi đi)</span>
              <textarea
                value={predictNote}
                onChange={(e) => setPredictNote(e.target.value)}
                rows={3}
                placeholder="Viết giả thuyết của bạn…"
              />
            </label>
          </div>
        )}
      </div>

      <div className="sim-pedagogy-card">
        <div className="sim-pedagogy-head">
          <strong>Kiểm tra nhanh</strong>
          <span>
            {visibleCheckpoints.length}/{spec.checkpoints.length} câu
            {lockedCount > 0 && !freeMode ? ` · ${lockedCount} khóa` : ''}
          </span>
        </div>
        {visibleCheckpoints.length === 0 ? (
          <p className="sim-muted">Sang bước sau để mở câu hỏi kiểm tra.</p>
        ) : (
          <div className="sim-pedagogy-checks">
            {visibleCheckpoints.map((item, index) => {
              const state = answers[item.id];
              return (
                <article key={item.id} className="sim-checkpoint">
                  <p>
                    <span className="sim-checkpoint-index">Câu {index + 1}</span>
                    {item.prompt}
                    {(item.unlockAtStep ?? 1) > 1 && (
                      <em className="sim-checkpoint-unlock"> · từ bước {item.unlockAtStep}</em>
                    )}
                  </p>
                  {item.kind === 'choice' && item.choices ? (
                    <div className="sim-checkpoint-choices" role="radiogroup" aria-label={`Đáp án câu ${index + 1}`}>
                      {item.choices.map((choice) => (
                        <label key={choice} className="sim-checkpoint-choice">
                          <input
                            type="radio"
                            name={item.id}
                            checked={state?.choice === choice}
                            onChange={() => setAnswers((current) => ({
                              ...current,
                              [item.id]: { ...current[item.id], choice, checked: false },
                            }))}
                          />
                          <span>{choice}</span>
                        </label>
                      ))}
                    </div>
                  ) : (
                    <label className="sim-pedagogy-field">
                      <span>Nhập số</span>
                      <input
                        type="text"
                        inputMode="decimal"
                        value={state?.number ?? ''}
                        onChange={(e) => setAnswers((current) => ({
                          ...current,
                          [item.id]: { ...current[item.id], number: e.target.value, checked: false },
                        }))}
                      />
                    </label>
                  )}
                  <div className="sim-checkpoint-actions">
                    <button type="button" className="csim-btn csim-btn-filled" onClick={() => checkCheckpoint(item)}>
                      Kiểm tra
                    </button>
                    {state?.checked && (
                      <span className={state.correct ? 'sim-check-ok' : 'sim-check-bad'}>
                        {state.correct ? 'Đúng' : 'Chưa đúng'}
                      </span>
                    )}
                  </div>
                  {state?.checked && (
                    <p className="sim-checkpoint-explain">{item.explanation}</p>
                  )}
                </article>
              );
            })}
          </div>
        )}
        {lockedCount > 0 && !freeMode && (
          <p className="sim-muted sim-checkpoint-hint">Tiến bước (hoặc bật chế độ tự do) để mở thêm câu hỏi.</p>
        )}
      </div>
    </aside>
  );
}
