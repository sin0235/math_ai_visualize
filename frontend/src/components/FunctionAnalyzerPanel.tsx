import { AnalyzerToolControls } from './function-analyzer/AnalyzerToolControls';
import { AnalyzerInput } from './function-analyzer/AnalyzerInput';
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
      <div className="fa2-workspace">
        <AnalyzerInput
          expression={analyzer.expression}
          loading={analyzer.loading}
          ocrLoading={analyzer.ocrLoading}
          error={analyzer.error}
          onExpressionChange={analyzer.setExpression}
          onAnalyze={() => void analyzer.handleAnalyze()}
          onImageChange={analyzer.handleImageChange}
          onOpenGuide={onOpenGuide}
        />

        <section className="fa2-results-panel">
          {analyzer.loading ? <AnalyzerLoadingResult /> : analyzer.result ? (
            <AnalyzerResult
              result={analyzer.result}
              toolControls={
                <AnalyzerToolControls
                  enableInterval={analyzer.enableInterval}
                  enableLine={analyzer.enableLine}
                  enableTransform={analyzer.enableTransform}
                  intervalA={analyzer.intervalA}
                  intervalB={analyzer.intervalB}
                  lineK={analyzer.lineK}
                  lineB={analyzer.lineB}
                  transformType={analyzer.transformType}
                  transformValue={analyzer.transformValue}
                  isAnimatingTransform={analyzer.isAnimatingTransform}
                  disabled={analyzer.loading || analyzer.ocrLoading}
                  onToggleTool={analyzer.updateToolEnabled}
                  onIntervalAChange={(value) => { analyzer.setIntervalA(value); analyzer.scheduleToolAnalyze({ intervalA: value, enableInterval: true }); }}
                  onIntervalBChange={(value) => { analyzer.setIntervalB(value); analyzer.scheduleToolAnalyze({ intervalB: value, enableInterval: true }); }}
                  onLineKChange={(value) => { analyzer.setLineK(value); analyzer.scheduleToolAnalyze({ lineK: value, enableLine: true }); }}
                  onLineBChange={(value) => { analyzer.setLineB(value); analyzer.scheduleToolAnalyze({ lineB: value, enableLine: true }); }}
                  onTransformTypeChange={(value) => { analyzer.setTransformType(value); analyzer.scheduleToolAnalyze({ transformType: value, enableTransform: true }); }}
                  onTransformValueChange={(value) => { analyzer.setTransformValue(value); analyzer.scheduleToolAnalyze({ transformValue: value, enableTransform: true }); }}
                  onToggleAnimation={() => analyzer.setIsAnimatingTransform((value) => !value)}
                />
              }
            />
          ) : <EmptyAnalyzerResult />}
        </section>
      </div>
    </div>
  );
}
