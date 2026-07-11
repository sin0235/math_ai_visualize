import { useCallback, useEffect, useState } from 'react';
import { consumeAnalyzerLinkFromLocation, type SimulationHandoffPayload } from '../../api/client';
import { AreaBetweenCurvesSimulation } from '../../components/calculus/AreaBetweenCurvesSimulation';
import { SolidOfRevolutionSimulation } from '../../components/calculus/SolidOfRevolutionSimulation';
import { CrossSectionVolumeSimulation } from '../../components/calculus/CrossSectionVolumeSimulation';
import { TrigonometrySimulation } from '../../components/trigonometry/TrigonometrySimulation';
import { getSimulation } from '../catalog';
import { SimulationShell } from '../runtime/SimulationShell';
import { SimulationLibraryPage } from './SimulationLibraryPage';
import { DerivativeSurveySimulation } from '../templates/DerivativeSurveySimulation';
import { AntiderivativeFamilySimulation } from '../templates/AntiderivativeFamilySimulation';
import { SpaceCoordsSimulation } from '../templates/SpaceCoordsSimulation';
import { BayesLabSimulation } from '../templates/BayesLabSimulation';
import { StatisticsLabSimulation } from '../templates/StatisticsLabSimulation';
import { RationalAsymptoteSimulation } from '../templates/RationalAsymptoteSimulation';
import { LimitsContinuitySimulation } from '../templates/LimitsContinuitySimulation';
import { SequencesLabSimulation } from '../templates/SequencesLabSimulation';
import { TrigEquationsSimulation } from '../templates/TrigEquationsSimulation';
import { SpaceRelationsSimulation } from '../templates/SpaceRelationsSimulation';
import { ProbabilityTreeG11Simulation } from '../templates/ProbabilityTreeG11Simulation';

function parseSimulationId(pathname: string): string | null {
  const normalized = pathname.replace(/\/+$/, '') || '/';
  if (normalized === '/simulation') return null;
  if (!normalized.startsWith('/simulation/')) return null;
  const id = decodeURIComponent(normalized.slice('/simulation/'.length));
  return id || null;
}

export function SimulationHubPage() {
  const [simId, setSimId] = useState<string | null>(() => parseSimulationId(window.location.pathname));
  const [analyzerHandoff, setAnalyzerHandoff] = useState<SimulationHandoffPayload | null>(null);
  const [handoffError, setHandoffError] = useState('');

  useEffect(() => {
    void consumeAnalyzerLinkFromLocation<SimulationHandoffPayload>('simulation')
      .then((payload) => {
        if (!payload || payload.version !== 'function-simulation-v1') return;
        setAnalyzerHandoff(payload);
        setSimId(payload.simulation_id);
      })
      .catch((caught) => setHandoffError(caught instanceof Error ? caught.message : 'Không mở được handoff analyzer.'));
  }, []);

  useEffect(() => {
    function syncFromLocation() {
      setSimId(parseSimulationId(window.location.pathname));
    }
    // App.navigateTo uses history.pushState without popstate — patch so in-app nav resyncs.
    const { pushState, replaceState } = window.history;
    window.history.pushState = function patchedPushState(...args: Parameters<History['pushState']>) {
      const result = pushState.apply(this, args);
      window.dispatchEvent(new Event('locationchange'));
      return result;
    };
    window.history.replaceState = function patchedReplaceState(...args: Parameters<History['replaceState']>) {
      const result = replaceState.apply(this, args);
      window.dispatchEvent(new Event('locationchange'));
      return result;
    };
    window.addEventListener('popstate', syncFromLocation);
    window.addEventListener('locationchange', syncFromLocation);
    syncFromLocation();
    return () => {
      window.removeEventListener('popstate', syncFromLocation);
      window.removeEventListener('locationchange', syncFromLocation);
      window.history.pushState = pushState;
      window.history.replaceState = replaceState;
    };
  }, []);

  const openSimulation = useCallback((id: string) => {
    const path = `/simulation/${encodeURIComponent(id)}`;
    window.history.pushState({}, document.title, path);
    setSimId(id);
  }, []);

  const backToLibrary = useCallback(() => {
    window.history.pushState({}, document.title, '/simulation');
    setSimId(null);
  }, []);

  if (!simId) {
    return <SimulationLibraryPage onOpen={openSimulation} />;
  }

  const spec = getSimulation(simId);
  if (!spec) {
    return (
      <section className="csim-page sim-library-page">
        <div className="sim-library-empty">
          <strong>Không tìm thấy mô phỏng</strong>
          <p>Mã <code>{simId}</code> không có trong thư viện.</p>
          <button type="button" className="csim-btn csim-btn-filled" onClick={backToLibrary}>Về thư viện</button>
        </div>
      </section>
    );
  }

  return (
    <>
      {handoffError && <div className="sim-library-empty" role="alert">{handoffError}</div>}
      <SimulationShell spec={spec} onBack={backToLibrary}>
      {({ step, progress, playing, freeMode }) => {
        switch (spec.template) {
          case 'riemann-area':
            return <AreaBetweenCurvesSimulation step={step} progress={progress} freeMode={freeMode} />;
          case 'solid-revolution':
            return <SolidOfRevolutionSimulation step={step} progress={progress} freeMode={freeMode} />;
          case 'cross-section':
            return <CrossSectionVolumeSimulation step={step} progress={progress} freeMode={freeMode} />;
          case 'unit-circle-trig':
            return <TrigonometrySimulation playing={playing} />;
          case 'derivative-survey':
            return <DerivativeSurveySimulation step={step} progress={progress} freeMode={freeMode} initialHandoff={analyzerHandoff} />;
          case 'antiderivative-family':
            return <AntiderivativeFamilySimulation step={step} progress={progress} freeMode={freeMode} />;
          case 'space-coords':
            return <SpaceCoordsSimulation step={step} progress={progress} freeMode={freeMode} />;
          case 'bayes-lab':
            return <BayesLabSimulation step={step} progress={progress} freeMode={freeMode} />;
          case 'statistics-lab':
            return <StatisticsLabSimulation step={step} progress={progress} freeMode={freeMode} />;
          case 'rational-asymptote':
            return <RationalAsymptoteSimulation step={step} progress={progress} freeMode={freeMode} />;
          case 'limits-continuity':
            return <LimitsContinuitySimulation step={step} progress={progress} />;
          case 'sequences-lab':
            return <SequencesLabSimulation step={step} progress={progress} />;
          case 'trig-equations':
            return <TrigEquationsSimulation step={step} progress={progress} />;
          case 'space-relations':
            return <SpaceRelationsSimulation step={step} progress={progress} />;
          case 'probability-tree-g11':
            return <ProbabilityTreeG11Simulation step={step} progress={progress} />;
          default:
            return <div className="sim-library-empty"><strong>Template chưa gắn</strong></div>;
        }
      }}
      </SimulationShell>
    </>
  );
}
