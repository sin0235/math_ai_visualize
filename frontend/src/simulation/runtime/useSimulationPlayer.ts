import { useCallback, useEffect, useRef, useState } from 'react';

export type SimulationPlayer = {
  step: number;
  progress: number;
  playing: boolean;
  speed: number;
  totalSteps: number;
  setSpeed: (speed: number) => void;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  reset: () => void;
  previousStep: () => void;
  nextStep: () => void;
  goToStep: (step: number) => void;
};

export function useSimulationPlayer(totalSteps: number): SimulationPlayer {
  const safeTotal = Math.max(1, totalSteps);
  const [step, setStep] = useState(1);
  const [progress, setProgress] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const rafRef = useRef<number | null>(null);
  const lastTimeRef = useRef<number | null>(null);
  const stepRef = useRef(1);

  useEffect(() => {
    stepRef.current = step;
  }, [step]);

  useEffect(() => {
    stepRef.current = 1;
    setStep(1);
    setProgress(0);
    setPlaying(false);
  }, [safeTotal]);

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
        if (stepRef.current >= safeTotal) {
          setPlaying(false);
          return 1;
        }
        const nextStep = Math.min(safeTotal, stepRef.current + 1);
        stepRef.current = nextStep;
        setStep(nextStep);
        return 0;
      });
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [playing, speed, safeTotal]);

  const previousStep = useCallback(() => {
    setPlaying(false);
    setStep((current) => {
      const next = Math.max(1, current - 1);
      stepRef.current = next;
      return next;
    });
    setProgress(0);
  }, []);

  const nextStep = useCallback(() => {
    setPlaying(false);
    setStep((current) => {
      const next = Math.min(safeTotal, current + 1);
      stepRef.current = next;
      return next;
    });
    setProgress(0);
  }, [safeTotal]);

  const goToStep = useCallback((target: number) => {
    setPlaying(false);
    const next = Math.min(safeTotal, Math.max(1, Math.floor(target)));
    stepRef.current = next;
    setStep(next);
    setProgress(0);
  }, [safeTotal]);

  const reset = useCallback(() => {
    setPlaying(false);
    stepRef.current = 1;
    setStep(1);
    setProgress(0);
  }, []);

  return {
    step,
    progress,
    playing,
    speed,
    totalSteps: safeTotal,
    setSpeed,
    play: () => setPlaying(true),
    pause: () => setPlaying(false),
    toggle: () => setPlaying((value) => !value),
    reset,
    previousStep,
    nextStep,
    goToStep,
  };
}
