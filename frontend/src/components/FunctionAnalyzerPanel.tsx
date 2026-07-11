import { AnalyzerToolControls } from './function-analyzer/AnalyzerToolControls';
import { AnalyzerInput } from './function-analyzer/AnalyzerInput';
import { AnalyzerPersistenceControls } from './function-analyzer/AnalyzerPersistenceControls';
import { AnalyzerLoadingResult, AnalyzerResult, EmptyAnalyzerResult } from './function-analyzer/AnalyzerResult';
import { useFunctionAnalysis } from './function-analyzer/useFunctionAnalysis';

interface FunctionAnalyzerPanelProps {
  initialExpression?: string;
  onOpenGuide?: () => void;
  onWarnings?: (warnings: string[]) => void;
}

export function FunctionAnalyzerPanel({ initialExpression = '', onOpenGuide, onWarnings }: FunctionAnalyzerPanelProps) {
  const analyzer = useFunctionAnalysis(initialExpression, onWarnings);

  return (
    <div className="fa2-panel">
      <AnalyzerPersistenceControls
        result={analyzer.sessionResult}
        profile={analyzer.curriculumProfile}
        graphWindow={analyzer.historyWindow}
        tools={analyzer.historyTools}
        disabled={analyzer.analysisState !== 'current' || analyzer.loading || analyzer.ocrLoading}
        onProfileChange={analyzer.setCurriculumProfile}
        onOpenHistory={analyzer.openHistoryItem}
      />
      <div className="fa2-workspace">
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
          onExpressionChange={analyzer.setExpression}
          onAnalyze={() => void analyzer.handleAnalyze()}
          onConfirmOcr={() => void analyzer.handleConfirmOcr()}
          onDiscardOcr={analyzer.discardOcrCandidate}
          onImageChange={analyzer.handleImageChange}
          onOpenGuide={onOpenGuide}
        />

        <section className="fa2-results-panel">
          {analyzer.loading ? <AnalyzerLoadingResult /> : analyzer.result ? (
            <AnalyzerResult
              result={analyzer.result}
              parameterSnapshots={analyzer.parameterSnapshots}
              onSaveParameterSnapshot={analyzer.saveParameterSnapshot}
              onRemoveParameterSnapshot={analyzer.removeParameterSnapshot}
              onClearParameterSnapshots={analyzer.clearParameterSnapshots}
              toolControls={
                <AnalyzerToolControls
                  enableInterval={analyzer.enableInterval}
                  enableLine={analyzer.enableLine}
                  enableTransform={analyzer.enableTransform}
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
                  disabled={analyzer.analysisState !== 'current' || analyzer.loading || analyzer.ocrLoading}
                  onToggleTool={analyzer.updateToolEnabled}
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
      </div>
    </div>
  );
}
