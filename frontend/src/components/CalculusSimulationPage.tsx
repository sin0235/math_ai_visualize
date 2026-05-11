import { useEffect, useMemo, useRef, useState } from 'react';
import { KatexSpan } from './KatexSpan';
import { AreaBetweenCurvesSimulation } from './calculus/AreaBetweenCurvesSimulation';
import { SolidOfRevolutionSimulation } from './calculus/SolidOfRevolutionSimulation';
import { CrossSectionVolumeSimulation } from './calculus/CrossSectionVolumeSimulation';
import { TrigonometrySimulation } from './trigonometry/TrigonometrySimulation';

type SubjectKey = 'integral' | 'trigonometry';
type ModuleKey = 'area' | 'revolution' | 'cross-section';

type ModuleMeta = {
  key: ModuleKey;
  title: string;
  subtitle: string;
  subtitleTex: string;
  steps: number;
};

const MODULES: ModuleMeta[] = [
  {
    key: 'area',
    title: 'Diện tích hình phẳng',
    subtitle: 'Riemann sum và tích phân |f-g|',
    subtitleTex: String.raw`\text{Riemann sum và tích phân }\int_a^b \lvert f(x)-g(x)\rvert\,dx`,
    steps: 3,
  },
  {
    key: 'revolution',
    title: 'Khối tròn xoay',
    subtitle: 'Disk / Washer với quét 3D quanh Ox',
    subtitleTex: String.raw`\text{Disk / Washer, quét 3D quanh }Ox`,
    steps: 4,
  },
  {
    key: 'cross-section',
    title: 'Thiết diện song song',
    subtitle: 'Stack lát cắt và V = ∫S(x)dx',
    subtitleTex: String.raw`\text{Stack lát cắt,}\quad V=\int_a^b S(x)\,dx`,
    steps: 4,
  },
];

const SUBJECTS: Array<{ key: SubjectKey; title: string; subtitle: string; steps: number }> = [
  { key: 'integral', title: 'Tích phân', subtitle: 'Diện tích, thể tích, tổng Riemann', steps: 4 },
  { key: 'trigonometry', title: 'Lượng giác', subtitle: 'Đường tròn đơn vị, sóng sin/cos, bảng góc', steps: 7 },
];

export function CalculusSimulationPage() {
  const [subjectKey, setSubjectKey] = useState<SubjectKey>('integral');
  const [moduleKey, setModuleKey] = useState<ModuleKey>('area');
  const [step, setStep] = useState(1);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [menuCollapsed, setMenuCollapsed] = useState(false);
  const rafRef = useRef<number | null>(null);
  const lastTimeRef = useRef<number | null>(null);
  const module = useMemo(() => MODULES.find((item) => item.key === moduleKey) ?? MODULES[0], [moduleKey]);
  const subject = useMemo(() => SUBJECTS.find((item) => item.key === subjectKey) ?? SUBJECTS[0], [subjectKey]);
  const totalSteps = subjectKey === 'integral' ? module.steps : subject.steps;

  useEffect(() => {
    setStep(1);
    setProgress(0);
    setPlaying(false);
  }, [moduleKey, subjectKey]);

  useEffect(() => {
    const pauseWhenHidden = () => {
      if (document.hidden) setPlaying(false);
    };
    document.addEventListener('visibilitychange', pauseWhenHidden);
    return () => document.removeEventListener('visibilitychange', pauseWhenHidden);
  }, []);

  useEffect(() => {
    if (!playing) {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      lastTimeRef.current = null;
      return;
    }
    const tick = (time: number) => {
      const last = lastTimeRef.current ?? time;
      const delta = (time - last) / 1000;
      lastTimeRef.current = time;
      setProgress((current) => {
        const next = current + delta * 0.38 * speed;
        if (next < 1) return next;
        let reachedFinalStep = false;
        setStep((currentStep) => {
          if (currentStep >= totalSteps) {
            reachedFinalStep = true;
            return 1;
          }
          return currentStep + 1;
        });
        return 0;
      });
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [playing, speed, totalSteps]);

  function previousStep() {
    setPlaying(false);
    setStep((current) => Math.max(1, current - 1));
    setProgress(0);
  }

  function nextStep() {
    setPlaying(false);
    setStep((current) => Math.min(totalSteps, current + 1));
    setProgress(0);
  }

  function switchSubject(nextSubject: SubjectKey) {
    setPlaying(false);
    setSubjectKey(nextSubject);
  }

  function switchModule(nextModule: ModuleKey) {
    setPlaying(false);
    setModuleKey(nextModule);
  }

  function reset() {
    setPlaying(false);
    setStep(1);
    setProgress(0);
  }

  return (
    <section className="csim-page">
      <div className={`csim-workbench${menuCollapsed ? ' is-menu-collapsed' : ''}`}>
        <aside className="csim-menu-panel" aria-label="Menu mô phỏng">
          <button type="button" className="csim-menu-toggle" onClick={() => setMenuCollapsed((value) => !value)} aria-expanded={!menuCollapsed} aria-label={menuCollapsed ? 'Bung menu mô phỏng' : 'Thu menu mô phỏng'}>
            <span>{menuCollapsed ? '›' : '‹'}</span>
            <strong>Menu</strong>
          </button>

          <div className="csim-menu-content">
            <div className="csim-menu-group">
              <button type="button" className={`csim-menu-group-button${subjectKey === 'integral' ? ' active' : ''}`} aria-expanded={subjectKey === 'integral'} onClick={() => switchSubject('integral')}>
                <span>Tích phân</span>
              </button>
              {subjectKey === 'integral' && (
                <div className="csim-menu-children" role="tablist" aria-label="Chọn module tích phân">
                  {MODULES.map((item) => (
                    <button key={item.key} type="button" role="tab" aria-selected={moduleKey === item.key} className={moduleKey === item.key ? 'active' : ''} onClick={() => switchModule(item.key)} aria-label={`${item.title}. ${item.subtitle}`}>
                      <strong>{item.title}</strong>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="csim-menu-group">
              <button type="button" className={`csim-menu-group-button${subjectKey === 'trigonometry' ? ' active' : ''}`} aria-expanded={subjectKey === 'trigonometry'} onClick={() => switchSubject('trigonometry')}>
                <span>Lượng giác</span>
              </button>
            </div>
          </div>
        </aside>

        <div className="csim-workspace">
          <div className="csim-playbar">
            <div className="csim-playbar-title">
              <span>{subject.title}</span>
              <strong>{subjectKey === 'integral' ? module.title : subject.subtitle}</strong>
            </div>
            <div className="csim-playbar-actions" aria-label="Điều khiển mô phỏng">
              <button type="button" className="csim-btn csim-btn-ghost" onClick={previousStep} disabled={step <= 1}>← Lùi</button>
              <button type="button" className="csim-btn csim-btn-ghost" onClick={nextStep} disabled={step >= totalSteps}>Bước →</button>
              <button type="button" className="csim-btn csim-btn-filled" onClick={() => setPlaying((value) => !value)}>{playing ? 'Tạm dừng' : 'Chạy'}</button>
              <button type="button" className="csim-btn csim-btn-ghost" onClick={reset}>Đặt lại</button>
            </div>
            <div className="csim-playbar-status">
              <strong>Bước {step}/{totalSteps}</strong>
              <ol className="csim-progress-dots" aria-label={`Bước ${step} trên ${totalSteps}`}>
                {Array.from({ length: totalSteps }, (_, index) => {
                  const currentStep = index + 1;
                  return <li key={currentStep} className={currentStep <= step ? 'active' : ''} aria-current={currentStep === step ? 'step' : undefined}><span /></li>;
                })}
              </ol>
              <div className="csim-progress" aria-hidden="true">
                <span style={{ width: `${((step - 1 + Math.min(progress, 1)) / totalSteps) * 100}%` }} />
              </div>
              <label className="csim-speed-select">Tốc độ
                <select value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>
                  <option value={0.5}>0.5x</option>
                  <option value={1}>1x</option>
                  <option value={1.5}>1.5x</option>
                  <option value={2}>2x</option>
                </select>
              </label>
            </div>
          </div>

          {subjectKey === 'integral' && moduleKey === 'area' && <AreaBetweenCurvesSimulation step={step} progress={progress} />}
          {subjectKey === 'integral' && moduleKey === 'revolution' && <SolidOfRevolutionSimulation step={step} progress={progress} />}
          {subjectKey === 'integral' && moduleKey === 'cross-section' && <CrossSectionVolumeSimulation step={step} progress={progress} />}
          {subjectKey === 'trigonometry' && <TrigonometrySimulation playing={playing} />}
        </div>
      </div>
    </section>
  );
}
