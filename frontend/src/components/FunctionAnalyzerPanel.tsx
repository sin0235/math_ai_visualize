import { useInterpretationPreflight } from './nlp/InterpretationPanel';
import { AnalyzerToolControls } from './function-analyzer/AnalyzerToolControls';
import { AnalyzerInput } from './function-analyzer/AnalyzerInput';
import { AnalyzerPersistenceControls } from './function-analyzer/AnalyzerPersistenceControls';
import { AnalyzerLoadingResult, AnalyzerResult, EmptyAnalyzerResult } from './function-analyzer/AnalyzerResult';
import { useFunctionAnalysis } from './function-analyzer/useFunctionAnalysis';

interface FunctionAnalyzerPanelProps {
  initialExpression?: string;
  onOpenGuide?: () => void;
}

export function FunctionAnalyzerPanel({ initialExpression = '', onOpenGuide }: FunctionAnalyzerPanelProps) {
  const analyzer = useFunctionAnalysis(initialExpression);
  const preflight = useInterpretationPreflight();
  const disabled = analyzer.analysisState !== 'current' || analyzer.loading || analyzer.ocrLoading;
  const toolDisabled = disabled || analyzer.toolCooldownSeconds > 0;

  async function requestAnalyze(fromOcr: boolean) {
    const text = analyzer.expression.trim();
    if (!text) return;
    const accepted = await preflight.check({ text, target: 'analyzer', context: {} });
    const expression = accepted ? expressionFromInterpretation(accepted) : text;
    preflight.reset();
    if (!expression) return;
    if (fromOcr) await analyzer.handleConfirmOcr(expression);
    else await analyzer.handleAnalyze(expression);
  }

  function expressionFromInterpretation(confirmed: Awaited<ReturnType<typeof preflight.check>>) {
    if (!confirmed) return '';
    const payloadExpression = confirmed.candidate.canonical_payload?.expression;
    return typeof payloadExpression === 'string'
      ? payloadExpression
      : confirmed.candidate.canonical_text?.trim() || confirmed.response.normalized_text.trim();
  }

  return (
    <div className="fa2-panel">
      <AnalyzerInput
        expression={analyzer.expression}
        loading={analyzer.loading}
        ocrLoading={analyzer.ocrLoading}
        ocrCandidate={analyzer.ocrCandidate}
        ocrPreviewUrl={analyzer.ocrPreviewUrl}
        error={analyzer.error}
        parameterDetected={analyzer.parameterDetected}
        parameterMode={analyzer.parameterMode}
        parameterValue={analyzer.parameterValue}
        onParameterModeChange={analyzer.setParameterMode}
        onParameterValueChange={analyzer.setParameterValue}
        onExpressionChange={(value) => { analyzer.setExpression(value); preflight.reset(); }}
        onAnalyze={() => void requestAnalyze(false)}
        onConfirmOcr={() => void requestAnalyze(true)}
        onDiscardOcr={analyzer.discardOcrCandidate}
        onImageChange={analyzer.handleImageChange}
        onOpenGuide={onOpenGuide}
      />

      <section className="fa2-results-panel" aria-label="Kết quả khảo sát">
        {analyzer.loading ? <AnalyzerLoadingResult /> : analyzer.result ? (
          <AnalyzerResult
            result={analyzer.result}
            warnings={analyzer.warnings}
            toolError={analyzer.toolError}
            toolLoading={analyzer.toolLoading}
            parameterSnapshots={analyzer.parameterSnapshots}
            onSaveParameterSnapshot={analyzer.saveParameterSnapshot}
            onRemoveParameterSnapshot={analyzer.removeParameterSnapshot}
            onClearParameterSnapshots={analyzer.clearParameterSnapshots}
            toolControls={
              <AnalyzerToolControls
                activeTool={analyzer.activeTool}
                intervalA={analyzer.intervalA}
                intervalB={analyzer.intervalB}
                lineK={analyzer.lineK}
                lineB={analyzer.lineB}
                intervalOpenA={analyzer.intervalOpenA}
                intervalOpenB={analyzer.intervalOpenB}
                lineMode={analyzer.lineMode}
                lineX0={analyzer.lineX0}
                transformType={analyzer.transformType}
                transformValue={analyzer.transformValue}
                isAnimatingTransform={analyzer.isAnimatingTransform}
                animationFps={analyzer.animationFps}
                disabled={toolDisabled}
                onSelectTool={analyzer.selectTool}
                onIntervalAChange={(value) => { analyzer.setIntervalA(value); analyzer.scheduleToolAnalyze({ intervalA: value, enableInterval: true }); }}
                onIntervalBChange={(value) => { analyzer.setIntervalB(value); analyzer.scheduleToolAnalyze({ intervalB: value, enableInterval: true }); }}
                onIntervalOpenAChange={(value) => { analyzer.setIntervalOpenA(value); analyzer.scheduleToolAnalyze({ intervalOpenA: value, enableInterval: true }); }}
                onIntervalOpenBChange={(value) => { analyzer.setIntervalOpenB(value); analyzer.scheduleToolAnalyze({ intervalOpenB: value, enableInterval: true }); }}
                onLineKChange={(value) => { analyzer.setLineK(value); analyzer.scheduleToolAnalyze({ lineK: value, enableLine: true }); }}
                onLineBChange={(value) => { analyzer.setLineB(value); analyzer.scheduleToolAnalyze({ lineB: value, enableLine: true }); }}
                onLineModeChange={(value) => { analyzer.setLineMode(value); analyzer.scheduleToolAnalyze({ lineMode: value, enableLine: true }); }}
                onLineX0Change={(value) => { analyzer.setLineX0(value); analyzer.scheduleToolAnalyze({ lineX0: value, enableLine: true }); }}
                onTransformTypeChange={(value) => { analyzer.setTransformType(value); analyzer.scheduleToolAnalyze({ transformType: value, enableTransform: true }); }}
                onTransformValueChange={(value) => { analyzer.setTransformValue(value); analyzer.scheduleToolAnalyze({ transformValue: value, enableTransform: true }); }}
                onAnimationFpsChange={analyzer.setAnimationFps}
                onToggleAnimation={() => analyzer.setIsAnimatingTransform((value) => !value)}
                onResetAnimation={analyzer.resetTransformAnimation}
              />
            }
          />
        ) : <EmptyAnalyzerResult />}
      </section>

      {analyzer.sessionResult && (
        <AnalyzerPersistenceControls
          result={analyzer.sessionResult}
          profile={analyzer.curriculumProfile}
          graphWindow={analyzer.historyWindow}
          tools={analyzer.historyTools}
          disabled={disabled}
          onProfileChange={analyzer.setCurriculumProfile}
          onOpenHistory={analyzer.openHistoryItem}
        />
      )}
    </div>
  );
}