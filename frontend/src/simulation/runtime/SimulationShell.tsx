import type { ReactNode } from 'react';
import type { SimulationSpec } from '../types';
import { KIND_LABELS, STRAND_LABELS } from '../types';
import { topicTitle } from '../catalog';
import { PedagogyPanel } from './PedagogyPanel';
import { useSimulationPlayer } from './useSimulationPlayer';

type Props = {
  spec: SimulationSpec;
  onBack: () => void;
  children: (ctx: { step: number; progress: number; playing: boolean }) => ReactNode;
};

export function SimulationShell({ spec, onBack, children }: Props) {
  const player = useSimulationPlayer(spec.steps);
  const showProcessBar = spec.kind === 'process-simulation' || spec.steps > 1;

  return (
    <section className="csim-page sim-workspace-page">
      <header className="sim-workspace-header">
        <button type="button" className="csim-btn csim-btn-ghost sim-back-btn" onClick={onBack}>
          ← Thư viện
        </button>
        <div className="sim-workspace-meta">
          <nav className="sim-breadcrumb" aria-label="Đường dẫn">
            <span>Mô phỏng</span>
            <span aria-hidden="true">/</span>
            <span>Lớp {spec.grade}</span>
            <span aria-hidden="true">/</span>
            <span>{STRAND_LABELS[spec.strand]}</span>
            <span aria-hidden="true">/</span>
            <span>{topicTitle(spec.topicCode)}</span>
          </nav>
          <h1>{spec.title}</h1>
          <p>{spec.subtitle}</p>
          <div className="sim-chip-row" aria-label="Nhãn mô phỏng">
            <span className="sim-chip">Lớp {spec.grade}</span>
            <span className="sim-chip">{KIND_LABELS[spec.kind]}</span>
            <span className="sim-chip">{spec.dims.toUpperCase()}</span>
            <span className="sim-chip sim-chip-status">{spec.status === 'published' ? 'Đã xuất bản' : 'Nháp'}</span>
          </div>
        </div>
      </header>

      <div className="sim-workspace-layout">
        <div className="sim-workspace-main">
          {showProcessBar && (
            <div className="csim-playbar">
              <div className="csim-playbar-title">
                <span>{STRAND_LABELS[spec.strand]}</span>
                <strong>{spec.title}</strong>
              </div>
              <div className="csim-playbar-actions" aria-label="Điều khiển mô phỏng">
                <button type="button" className="csim-btn csim-btn-ghost" onClick={player.previousStep} disabled={player.step <= 1}>← Lùi</button>
                <button type="button" className="csim-btn csim-btn-ghost" onClick={player.nextStep} disabled={player.step >= player.totalSteps}>Bước →</button>
                <button type="button" className="csim-btn csim-btn-filled" onClick={player.toggle}>{player.playing ? 'Tạm dừng' : 'Chạy'}</button>
                <button type="button" className="csim-btn csim-btn-ghost" onClick={player.reset}>Đặt lại</button>
              </div>
              <div className="csim-playbar-status">
                <strong>Bước {player.step}/{player.totalSteps}</strong>
                <ol className="csim-progress-dots" aria-label={`Bước ${player.step} trên ${player.totalSteps}`}>
                  {Array.from({ length: player.totalSteps }, (_, index) => {
                    const currentStep = index + 1;
                    return (
                      <li
                        key={currentStep}
                        className={currentStep <= player.step ? 'active' : ''}
                        aria-current={currentStep === player.step ? 'step' : undefined}
                      >
                        <button
                          type="button"
                          className="sim-step-dot-btn"
                          onClick={() => player.goToStep(currentStep)}
                          aria-label={`Tới bước ${currentStep}`}
                        >
                          <span />
                        </button>
                      </li>
                    );
                  })}
                </ol>
                <div className="csim-progress" aria-hidden="true">
                  <span style={{ width: `${((player.step - 1 + Math.min(player.progress, 1)) / player.totalSteps) * 100}%` }} />
                </div>
                <label className="csim-speed-select">Tốc độ
                  <select value={player.speed} onChange={(event) => player.setSpeed(Number(event.target.value))}>
                    <option value={0.5}>0.5x</option>
                    <option value={1}>1x</option>
                    <option value={1.5}>1.5x</option>
                    <option value={2}>2x</option>
                  </select>
                </label>
              </div>
            </div>
          )}

          {!showProcessBar && (
            <div className="csim-playbar csim-playbar-compact">
              <div className="csim-playbar-title">
                <span>Tương tác</span>
                <strong>{spec.title}</strong>
              </div>
              <div className="csim-playbar-actions" aria-label="Điều khiển mô phỏng">
                <button type="button" className="csim-btn csim-btn-filled" onClick={player.toggle}>{player.playing ? 'Tạm dừng' : 'Chạy'}</button>
                <button type="button" className="csim-btn csim-btn-ghost" onClick={player.reset}>Đặt lại</button>
              </div>
            </div>
          )}

          <div className="sim-template-host">
            {children({ step: player.step, progress: player.progress, playing: player.playing })}
          </div>
        </div>

        <PedagogyPanel spec={spec} />
      </div>
    </section>
  );
}
