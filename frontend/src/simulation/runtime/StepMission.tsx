import type { StepMissionDef } from '../types';

type Props = {
  step: number;
  totalSteps: number;
  mission?: StepMissionDef | null;
  freeMode: boolean;
  onToggleFreeMode: () => void;
};

export function StepMission({ step, totalSteps, mission, freeMode, onToggleFreeMode }: Props) {
  const title = mission?.title ?? `Bước ${step} / ${totalSteps}`;
  const instruction = mission?.instruction
    ?? 'Thao tác các điều khiển được mở ở bước này và quan sát số liệu / hình vẽ đổi theo thời gian thực.';

  return (
    <div className={`sim-step-mission${freeMode ? ' is-free' : ''}`} role="status" aria-live="polite">
      <div className="sim-step-mission-main">
        <span className="sim-step-mission-kicker">
          {freeMode ? 'Chế độ tự do' : `Nhiệm vụ · Bước ${step}/${totalSteps}`}
        </span>
        <strong>{freeMode ? 'Mọi điều khiển đã mở — khám phá tự do' : title}</strong>
        <p>{freeMode ? 'Tắt chế độ tự do để quay lại hành trình từng bước (tool-trip).' : instruction}</p>
      </div>
      <label className="sim-free-mode-toggle">
        <input type="checkbox" checked={freeMode} onChange={onToggleFreeMode} />
        <span>Chế độ tự do</span>
      </label>
    </div>
  );
}
