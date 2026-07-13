import { useState, type ReactNode } from 'react';
import type { AnalyzeResponse, ExactApproxValue } from '../../api/client';
import { KatexSpan, MixedTextRenderer, sympyToLatex } from '../KatexSpan';
import { TRANSFORM_LABEL_TEX } from './constants';
import { FunctionGraph } from './FunctionGraph';
import { SvgIcon, type IconName } from './icons';
import { VariationTable } from './VariationTable';
import type { ParameterSnapshot } from './useFunctionAnalysis';
import { MathCapabilitySummary } from '../MathCapabilitySummary';
import {
  analyzerCriticalPointLabel,
  analyzerLineKindLabel,
  analyzerMethodLabel,
  analyzerStatusLabel,
  mathListTex,
  mathTex,
  mathUnionTex,
  pointTex,
} from './analyzerPresentation';

export function EmptyAnalyzerResult() {
  return (
    <div className="fa2-empty-result">
      <div className="fa2-empty-icon" aria-hidden="true"><SvgIcon name="graph" /></div>
      <strong>Đồ thị và kết quả sẽ hiện ở đây</strong>
      <span>Nhập công thức phía trên rồi bấm Phân tích để xem đồ thị, bảng biến thiên và các điểm đặc biệt.</span>
    </div>
  );
}

export function AnalyzerLoadingResult() {
  return (
    <div className="fa2-loading-result" aria-live="polite" aria-busy="true">
      <div className="fa2-skeleton fa2-skeleton-graph" />
      <div className="fa2-skeleton-stack">
        <div className="fa2-skeleton fa2-skeleton-card" />
        <div className="fa2-skeleton fa2-skeleton-card" />
        <div className="fa2-skeleton fa2-skeleton-card" />
      </div>
    </div>
  );
}

export function AnalyzerResult({
  result,
  toolControls,
  warnings = [],
  toolError = null,
  toolLoading = false,
  parameterSnapshots = [],
  onSaveParameterSnapshot = () => undefined,
  onRemoveParameterSnapshot = () => undefined,
  onClearParameterSnapshots = () => undefined,
}: {
  result: AnalyzeResponse;
  toolControls: ReactNode;
  warnings?: string[];
  toolError?: string | null;
  toolLoading?: boolean;
  parameterSnapshots?: ParameterSnapshot[];
  onSaveParameterSnapshot?: () => void;
  onRemoveParameterSnapshot?: (value: string) => void;
  onClearParameterSnapshots?: () => void;
}) {
  const hasShapeDetails = result.concave_up_intervals.length > 0 || result.concave_down_intervals.length > 0 || result.horizontal_asymptotes.length > 0 || result.vertical_asymptotes.length > 0 || !!result.oblique_asymptote;
  const [variationBbtOpen, setVariationBbtOpen] = useState(false);
  const hasVariationTable = !!result.variation_table_v2?.nodes.length || (!!result.variation_table && result.variation_table.length > 0);

  return (
    <div className="fa2-result">
      <div className="fa2-result-shell">
        <div className="fa2-graph-column">
          <Section title="Đồ thị hàm số" icon="graph" className="fa2-graph-section">
            <FunctionGraph result={result} />
          </Section>
        </div>

        <div className="fa2-analysis-column">
          <div className="fa2-quick-workbench">
            <QuickSummary result={result} />
            <MathCapabilitySummary solution={result.solution_ir} />
            {warnings.length > 0 && <WarningSummary warnings={warnings} />}

            {(result.derivative_latex || result.derivative) && (
              <Section
                title="Đạo hàm và biến thiên"
                icon="derivative"
                headTrailing={
                  hasVariationTable ? (
                    <button type="button" className="bbt-zoom-btn bbt-zoom-btn-borderless" onClick={() => setVariationBbtOpen(true)} aria-label="Phóng to bảng biến thiên">
                      <span aria-hidden="true"><SvgIcon name="magnify" /></span>
                    </button>
                  ) : null
                }
              >
                <div className="fa2-formula-row"><KatexSpan tex="f'(x)=" className="fa2-label-mono fa2-label-katex" /><KatexSpan tex={result.derivative_latex || sympyToLatex(result.derivative || '')} className="fa2-katex" /></div>
                {result.second_derivative && <div className="fa2-formula-row"><KatexSpan tex="f''(x)=" className="fa2-label-mono fa2-label-katex" /><KatexSpan tex={result.second_derivative_latex || sympyToLatex(result.second_derivative)} className="fa2-katex" /></div>}
                <VariationTable rows={result.variation_table} tableV2={result.variation_table_v2 ?? null} expanded={variationBbtOpen} onExpandedChange={setVariationBbtOpen} hideZoomButton />
              </Section>
            )}

            {hasShapeDetails && (
              <Section title="Lồi lõm và tiệm cận" icon="asymptote">
                <div className="fa2-compact-list">
                  {result.concave_up_intervals.length > 0 && <IntervalLine label="Lồi" value={mathUnionTex(result.concave_up_intervals)} valueIsLatex className="fa2-mono-inc" />}
                  {result.concave_down_intervals.length > 0 && <IntervalLine label="Lõm" value={mathUnionTex(result.concave_down_intervals)} valueIsLatex className="fa2-mono-dec" />}
                  {result.horizontal_asymptotes.map((ha, i) => <Asymptote key={`ha-${i}`} label="Ngang" tex={`y = ${sympyToLatex(ha.value)}`} />)}
                  {result.vertical_asymptotes.map((va, i) => <Asymptote key={`va-${i}`} label="Đứng" tex={`x = ${sympyToLatex(va.x)}`} />)}
                  {result.oblique_asymptote && <Asymptote label="Xiên" tex={sympyToLatex(result.oblique_asymptote)} />}
                </div>
              </Section>
            )}

            {(result.parameter_mode === 'substitute' || parameterSnapshots.length > 0) && (
              <details className="fa2-result-disclosure">
                <summary>So sánh tham số</summary>
                <ParameterSnapshotComparison
                  current={result}
                  snapshots={parameterSnapshots}
                  onSave={onSaveParameterSnapshot}
                  onRemove={onRemoveParameterSnapshot}
                  onClear={onClearParameterSnapshots}
                />
              </details>
            )}
            {!!result.analysis_steps?.length && (
              <details className="fa2-result-disclosure">
                <summary>Các bước khảo sát</summary>
                <AnalysisSteps steps={result.analysis_steps} />
              </details>
            )}
          </div>

          <details className="fa2-tools-disclosure" open>
            <summary>
              <span>Công cụ khảo sát</span>
              <small>GTLN, tương giao và biến đổi</small>
            </summary>
            <div className="fa2-tools-workbench">
              {toolControls}
              {toolLoading && <div className="fa2-tool-status" role="status">Đang cập nhật công cụ…</div>}
              {toolError && <div className="fa2-tool-error" role="status">{toolError}</div>}
              <ToolAnalysisResults result={result} />
            </div>
          </details>
        </div>
      </div>
    </div>
  );
}

function ToolAnalysisResults({ result }: { result: AnalyzeResponse }) {
  const hasToolResults = !!result.interval_analysis || !!result.line_analysis || !!result.transform_preview;
  const isTangentTool = result.line_analysis?.mode !== undefined && result.line_analysis.mode !== 'intersect';

  if (!hasToolResults) {
    return <div className="fa2-tool-empty">Chọn công cụ để xem kết quả.</div>;
  }

  return (
    <div className="fa2-tool-results">
      {result.interval_analysis && (
        <Section title={`GTLN/GTNN trên ${result.interval_analysis.open_a || result.interval_analysis.open_b ? 'khoảng' : 'đoạn'}`} icon="points">
          <IntervalExtremaAnalysis interval={result.interval_analysis} />
        </Section>
      )}

      {result.line_analysis && (
        <Section title={isTangentTool ? 'Tiếp tuyến và pháp tuyến đồ thị' : 'Tương giao với đường thẳng'} icon="graph">
          <div className="fa2-compact-list">
            <div className="fa2-mono fa2-mono-inc">
              <span className="fa2-mono-label">{isTangentTool ? 'Kết quả' : 'Đường thẳng'}:</span>
              <span className="fa2-mono-val">
                <KatexSpan tex={
                  result.line_analysis.equation_latex
                  || mathTex(result.line_analysis.equation_exact || result.line_analysis.equation)
                } />
              </span>
            </div>
            {(result.line_analysis.status || result.line_analysis.kind || result.line_analysis.condition_exact) && (
              <details className="fa2-result-disclosure">
                <summary>Chi tiết kiểm chứng</summary>
                <div className="fa2-verification-details">
                  <span>Trạng thái: {analyzerStatusLabel(result.line_analysis.status)}</span>
                  {result.line_analysis.kind && <span>Loại kết quả: {analyzerLineKindLabel(result.line_analysis.kind)}</span>}
                  {result.line_analysis.condition_exact && (
                    <span>Điều kiện: <KatexSpan tex={mathTex(result.line_analysis.condition_exact)} /></span>
                  )}
                </div>
              </details>
            )}
            {isTangentTool ? (
              <div className="fa2-transform-formula fa2-tangent-list">
                {result.line_analysis.tangents?.map((tangent, index) => (
                  <div key={`${tangent.x0_exact}-${index}`} className="fa2-tangent-result">
                    <KatexSpan tex={tangent.equation_latex || mathTex(tangent.equation_exact)} />
                    <span>Tiếp điểm <KatexSpan tex={pointTex(tangent.x0_exact, tangent.y0_exact)} /></span>
                  </div>
                ))}
                {result.line_analysis.conclusion && <div className="fa2-conclusion"><strong>Kết luận</strong><MixedTextRenderer text={result.line_analysis.conclusion} /></div>}
              </div>
            ) : (
              <>
                <IntervalLine label="Số giao điểm" value={result.line_analysis.intersection_count == null ? 'Chưa xác định' : String(result.line_analysis.intersection_count)} className="fa2-mono-inc" />
                {result.line_analysis.intersection_count_status && (
                  <details className="fa2-result-disclosure">
                    <summary>Độ đầy đủ của giao điểm</summary>
                    <span>{analyzerStatusLabel(result.line_analysis.intersection_count_status)}</span>
                  </details>
                )}
                {(result.line_analysis.intersections ?? []).map((pt, index) => (
                  <div key={`line-${index}`}>
                    <PointBadge label="Giao điểm" tex={pointTex(pt.x_exact || pt.x, pt.y_exact || pt.y, pt.x_latex, pt.y_latex)} kind="axis" />
                    <details className="fa2-result-disclosure fa2-point-evidence">
                      <summary>Chi tiết kiểm chứng giao điểm {index + 1}</summary>
                      <dl className="fa2-evidence-list">
                        <div><dt>Xấp xỉ</dt><dd><KatexSpan tex={pointTex(pt.x, pt.y)} /></dd></div>
                        <div><dt>Độ chính xác</dt><dd>{analyzerStatusLabel(pt.verification)}</dd></div>
                        {pt.residual != null && <div><dt>Sai số dư</dt><dd><KatexSpan tex={mathTex(pt.residual)} /></dd></div>}
                        {pt.error_bound != null && <div><dt>Chặn sai số</dt><dd><KatexSpan tex={mathTex(pt.error_bound)} /></dd></div>}
                        {pt.multiplicity != null && <div><dt>Bội</dt><dd><KatexSpan tex={String(pt.multiplicity)} /></dd></div>}
                      </dl>
                    </details>
                  </div>
                ))}
                {(result.line_analysis.relative_intervals?.above.length ?? 0) > 0 && <IntervalLine label={<KatexSpan tex="f(x)>d" />} value={mathUnionTex(result.line_analysis.relative_intervals!.above)} valueIsLatex className="fa2-mono-inc" />}
                {(result.line_analysis.relative_intervals?.below.length ?? 0) > 0 && <IntervalLine label={<KatexSpan tex="f(x)<d" />} value={mathUnionTex(result.line_analysis.relative_intervals!.below)} valueIsLatex className="fa2-mono-dec" />}
                {result.line_analysis.area_v2?.status === 'complete' && result.line_analysis.area_v2.total_latex && (
                  <IntervalLine label="Tổng diện tích" value={result.line_analysis.area_v2.total_latex} valueIsLatex className="fa2-mono-inc" />
                )}
                {result.line_analysis.area_v2?.components.map((component, index) => (
                  <IntervalLine
                    key={`area-${index}`}
                    label={<>Miền {index + 1} <KatexSpan tex={`[${mathTex(component.left_exact, component.left_latex)};${mathTex(component.right_exact, component.right_latex)}]`} /></>}
                    value={component.area_latex}
                    valueIsLatex
                    className="fa2-mono-inc"
                  />
                ))}
                {result.line_analysis.roots_v2?.families.map((family, index) => (
                  <div key={`root-family-${index}`} className="fa2-interval-note"><KatexSpan tex={`x\\in ${family.set_latex}`} /></div>
                ))}
                {result.line_analysis.roots_v2 && result.line_analysis.roots_v2.status !== 'complete' && (
                  <details className="fa2-result-disclosure">
                    <summary>Độ đầy đủ của nghiệm</summary>
                    <span>{analyzerStatusLabel(result.line_analysis.roots_v2.status)}</span>
                  </details>
                )}
                {result.line_analysis.roots_v2?.warnings.map((warning, index) => <div key={`root-warning-${index}`} className="fa2-interval-note">{warning}</div>)}
                {result.line_analysis.area_v2?.warnings.map((warning, index) => <div key={`area-warning-${index}`} className="fa2-interval-note">{warning}</div>)}
              </>
            )}
            {result.line_analysis.warnings?.map((warning) => <div key={warning} className="fa2-interval-note">{warning}</div>)}
          </div>
        </Section>
      )}

      {result.transform_preview && (
        <Section title="Biến đổi đồ thị" icon="graph">
          <div className="fa2-transform-formula">
            <KatexSpan tex={TRANSFORM_LABEL_TEX[result.transform_preview.type] ?? sympyToLatex(result.transform_preview.label)} className="fa2-transform-rule" />
            <KatexSpan tex={`g(x)=${result.transform_preview.expression_latex || sympyToLatex(result.transform_preview.expression)}`} className="fa2-katex" />
            <span className="fa2-interval-note">{result.transform_preview.convention}</span>
          </div>
          {result.transform_preview.pedagogical_steps && result.transform_preview.pedagogical_steps.length > 0 && (
            <div className="fa2-pedagogical-steps">
              <strong>Các bước biến đổi</strong>
              <ol>
                {result.transform_preview.pedagogical_steps.map((step, idx) => (
                  <li key={`step-${idx}`}><MixedTextRenderer text={step} /></li>
                ))}
              </ol>
            </div>
          )}
        </Section>
      )}
    </div>
  );
}

function QuickSummary({ result }: { result: AnalyzeResponse }) {
  const expressionTex = result.evaluated_expression_latex || result.expression_latex || sympyToLatex(result.evaluated_expression || result.expression);
  const rootValues = result.x_intercepts_v2?.roots.length
    ? result.x_intercepts_v2.roots.map((root) => mathTex(root.x_exact || root.x, root.x_latex))
    : result.x_intercepts.map((root) => mathTex(root));
  const criticalValues = result.critical_points.map((point) => ({
    label: analyzerCriticalPointLabel(point.kind, point.kind_label),
    tex: pointTex(
      point.x_exact || point.x,
      point.y_exact ?? point.y,
      point.x_value?.latex,
      point.y_value?.latex,
    ),
  }));
  const hasHighlights = Boolean(
    result.domain_latex
    || result.range_latex
    || result.x_intercepts.length
    || result.y_intercept != null
    || result.critical_points.length,
  );

  return (
    <div className="fa2-quick-card">
      <div className="fa2-quick-head">
        <span className="fa2-quick-eyebrow">Kết quả chính</span>
        <KatexSpan tex={`y=${expressionTex}`} className="fa2-quick-expression" />
        {result.verification && (
          <span className={`fa2-verification-badge is-${result.verification.status}`}>
            {verificationLabel(result.verification.status)}
          </span>
        )}
      </div>
      <div className="fa2-quick-rows">
        {result.domain_latex && <SummaryCard label="Tập xác định" tex={result.domain_latex} />}
        {result.range_latex && <SummaryCard label="Tập giá trị" tex={result.range_latex} />}
        {rootValues.length > 0 && <SummaryCard label="Giao với trục Ox" tex={mathListTex(rootValues)} />}
        {result.y_intercept != null && <SummaryCard label="Giao với trục Oy" tex={pointTex('0', result.y_intercept)} />}
        {criticalValues.length > 0 && <SummaryMathListCard label="Cực trị" values={criticalValues} />}
        {result.parameters?.active_exact?.m && <SummaryCard label="Giá trị tham số" tex={`m=${sympyToLatex(result.parameters.active_exact.m)}`} />}
      </div>
      {!hasHighlights && <p className="fa2-empty-note">Backend chưa xác nhận được đặc trưng chính cho hàm này.</p>}
      {result.requires_parameter_confirmation && (
        <div className="fa2-interval-note" role="status">Chọn phân tích theo trường hợp hoặc nhập giá trị chính xác của <KatexSpan tex="m" /> rồi phân tích lại.</div>
      )}
      {result.parameter_analysis_v2 && <ParameterCaseSummary analysis={result.parameter_analysis_v2} />}
      {result.x_intercepts_v2 && <RootSummary analysis={result.x_intercepts_v2} />}
      {result.curriculum_presentation && (
        <details className="fa2-result-disclosure">
          <summary>Gợi ý học tập lớp {result.curriculum_presentation.profile.grade}</summary>
          <div className="fa2-curriculum-summary">
            <div>
              <span>Lỗi thường gặp</span>
              <ul>{result.curriculum_presentation.common_mistakes.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
            <div>
              <span>Câu hỏi dự đoán</span>
              <ul>{result.curriculum_presentation.predicted_questions.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          </div>
        </details>
      )}
    </div>
  );
}

function WarningSummary({ warnings }: { warnings: string[] }) {
  const uniqueWarnings = Array.from(new Set(warnings.map((warning) => warning.trim()).filter(Boolean)));
  if (uniqueWarnings.length === 0) return null;
  return (
    <details className="fa2-warning-summary">
      <summary>{uniqueWarnings.length} lưu ý về kết quả</summary>
      <ul>{uniqueWarnings.map((warning) => <li key={warning}><MixedTextRenderer text={warning} /></li>)}</ul>
    </details>
  );
}

function AnalysisSteps({ steps }: { steps: NonNullable<AnalyzeResponse['analysis_steps']> }) {
  return (
    <Section title="Các bước khảo sát" icon="derivative">
      <ol className="fa2-analysis-steps">
        {steps.map((step) => (
          <li key={step.key} className={`is-${step.status}`}>
            <details open={step.status === 'partial'}>
              <summary>
                <span>{step.order}. {step.title}</span>
                <span className="fa2-step-status">{stepStatusLabel(step.status)}</span>
              </summary>
              {step.formula_latex && <KatexSpan tex={step.formula_latex} className="fa2-katex" />}
              {step.evidence.length > 0 && (
                <ul>{step.evidence.map((item, index) => <li key={`${step.key}-evidence-${index}`}><MixedTextRenderer text={item} /></li>)}</ul>
              )}
              {step.warnings.map((warning, index) => <p key={`${step.key}-warning-${index}`} role="status">{warning}</p>)}
            </details>
          </li>
        ))}
      </ol>
    </Section>
  );
}

function stepStatusLabel(status: NonNullable<AnalyzeResponse['analysis_steps']>[number]['status']) {
  return {
    complete: 'Đầy đủ',
    partial: 'Một phần',
    unknown: 'Chưa xác định',
    skipped: 'Đã bỏ qua',
  }[status];
}

function verificationLabel(status: NonNullable<AnalyzeResponse['verification']>['status']) {
  return {
    verified: 'Đã kiểm chứng',
    partially_verified: 'Kiểm chứng một phần',
    unverified: 'Chưa kiểm chứng',
    failed: 'Kiểm chứng thất bại',
  }[status];
}

function asymptoteValues(result: AnalyzeResponse): string[] {
  return [
    ...result.vertical_asymptotes.map((item) => `x=${mathTex(item.x)}`),
    ...result.horizontal_asymptotes.map((item) => `y=${mathTex(item.value)}`),
    ...(result.oblique_asymptote ? [mathTex(result.oblique_asymptote)] : []),
  ];
}

function ParameterSnapshotComparison({
  current,
  snapshots,
  onSave,
  onRemove,
  onClear,
}: {
  current: AnalyzeResponse;
  snapshots: ParameterSnapshot[];
  onSave: () => void;
  onRemove: (value: string) => void;
  onClear: () => void;
}) {
  const rows = snapshots.map((snapshot) => snapshot.result);
  const currentValue = current.parameters?.active_exact?.m;
  return (
    <Section title="So sánh snapshot tham số" icon="points">
      <div className="fa2-ocr-review-actions">
        <button type="button" className="sp-btn-secondary" onClick={onSave} disabled={!currentValue}>Lưu giá trị hiện tại</button>
        {snapshots.length > 0 && <button type="button" className="sp-btn-secondary" onClick={onClear}>Xóa các giá trị đã lưu</button>}
      </div>
      {rows.length === 0 ? <p className="fa2-interval-note">Phân tích bằng giá trị chính xác, rồi lưu tối đa 6 mốc để so sánh.</p> : (
        <div className="fa2-table-scroll">
          <table className="fa2-result-table">
            <thead><tr><th>m</th><th>Tập xác định</th><th>Tập giá trị</th><th>Nghiệm thực</th><th>Cực trị</th><th>Tiệm cận</th><th>Thao tác</th></tr></thead>
            <tbody>
              {rows.map((item) => {
                const value = item.parameters?.active_exact?.m ?? '?';
                const roots = item.x_intercepts_v2?.total_known == null ? analyzerStatusLabel(item.x_intercepts_v2?.status) : String(item.x_intercepts_v2.total_known);
                const extrema = item.critical_points.map((point) => pointTex(
                  point.x_exact || point.x,
                  point.y_exact ?? point.y,
                  point.x_value?.latex,
                  point.y_value?.latex,
                ));
                const asymptotes = asymptoteValues(item);
                return (
                  <tr key={value}>
                    <th><KatexSpan tex={`m=${sympyToLatex(value)}`} /></th>
                    <td>{item.domain_latex ? <KatexSpan tex={item.domain_latex} /> : 'Chưa xác định'}</td>
                    <td>{item.range_latex ? <KatexSpan tex={item.range_latex} /> : 'Chưa xác định'}</td>
                    <td>{roots}</td>
                    <td>{extrema.length ? extrema.map((tex, index) => <KatexSpan key={`${tex}-${index}`} tex={tex} />) : 'Không có điểm đã xác nhận'}</td>
                    <td>{asymptotes.length ? asymptotes.map((tex, index) => <KatexSpan key={`${tex}-${index}`} tex={tex} />) : 'Không có tiệm cận đã xác nhận'}</td>
                    <td><button type="button" className="sp-btn-secondary" onClick={() => onRemove(value)}>Xóa</button></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function ParameterCaseSummary({ analysis }: { analysis: NonNullable<AnalyzeResponse['parameter_analysis_v2']> }) {
  return (
    <div className="fa2-interval-note fa2-parameter-cases">
      <strong>Phân hoạch tham số: {analyzerStatusLabel(analysis.status)}</strong>
      {analysis.boundaries.length > 0 && <span>Mốc đổi trường hợp <KatexSpan tex={mathListTex(analysis.boundaries.map((item) => mathTex(item.exact)))} /></span>}
      {analysis.cases.map((item, index) => {
        const condition = item.condition_latex || item.condition_exact;
        const degree = typeof item.degree === 'number' ? `, bậc ${item.degree}` : '';
        const extrema = typeof item.extrema_count === 'number' ? `, ${item.extrema_count} cực trị` : '';
        const roots = typeof item.root_count === 'number' ? `, ${item.root_count} nghiệm thực` : '';
        const asymptotes = typeof item.vertical_asymptote_count === 'number' ? `, ${item.vertical_asymptote_count} tiệm cận đứng` : '';
        return <div key={`${condition}-${index}`}><KatexSpan tex={condition} /> <span>— {analyzerStatusLabel(item.status)}{degree}{extrema}{roots}{asymptotes}; {analyzerStatusLabel(item.verification)}</span></div>;
      })}
      {analysis.warnings.map((warning) => <span key={warning}>{warning}</span>)}
    </div>
  );
}

function RootSummary({ analysis }: { analysis: NonNullable<AnalyzeResponse['x_intercepts_v2']> }) {
  const rootsTex = analysis.roots.map((root) => root.x_latex || sympyToLatex(root.x_exact || root.x));
  const familiesTex = analysis.families.map((family) => family.set_latex);
  const sets = [rootsTex.length ? `\\{${rootsTex.join(', ')}\\}` : '', ...familiesTex].filter(Boolean);
  const value = sets.join('\\cup ') || (analysis.status === 'complete' ? '\\varnothing' : '\\text{chưa xác định}');
  const copyValues = analysis.roots.flatMap((root, index) => root.value
    ? [{ label: `Nghiệm ${index + 1}`, value: root.value }]
    : []);

  return (
    <div className="fa2-interval-note fa2-root-summary">
      <span>Giao điểm với Ox</span>
      <KatexSpan tex={`x\\in ${value}`} />
      {copyValues.length > 0 && <CopyValuesMenu label="nghiệm" values={copyValues} />}
      {(analysis.truncated || analysis.status !== 'complete') && <span>Độ đầy đủ: {analyzerStatusLabel(analysis.status)}. {analysis.warnings.join(' ')}</span>}
    </div>
  );
}

function CopyValuesMenu({ label, values }: { label: string; values: Array<{ label: string; value: ExactApproxValue }> }) {
  const [copied, setCopied] = useState<string | null>(null);

  async function copy(text: string, kind: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(kind);
    } catch {
      setCopied('Không thể sao chép');
    }
  }

  return (
    <details className="fa2-copy-values">
      <summary>Sao chép {label}</summary>
      <div>
        {values.map(({ label: valueLabel, value }) => (
          <div className="fa2-copy-value-group" key={valueLabel}>
            <span>{valueLabel}</span>
            <button type="button" onClick={() => void copy(value.exact, `Đã sao chép ${valueLabel.toLowerCase()}`)}>Chính xác</button>
            {value.approx != null && <button type="button" onClick={() => void copy(String(value.approx), `Đã sao chép ${valueLabel.toLowerCase()} xấp xỉ`)}>Xấp xỉ</button>}
          </div>
        ))}
      </div>
      {copied && <span role="status">{copied}</span>}
    </details>
  );
}

function CopyValueButtons({ label, value }: { label: string; value: ExactApproxValue }) {
  return <CopyValuesMenu label={label.toLowerCase()} values={[{ label, value }]} />;
}

function SummaryCard({ label, tex }: { label: string; tex: string }) {
  return <div className="fa2-summary-card"><span>{label}</span><KatexSpan tex={tex} /></div>;
}

function SummaryMathListCard({ label, values }: { label: string; values: Array<{ label: string; tex: string }> }) {
  return (
    <div className="fa2-summary-card">
      <span>{label}</span>
      <div className="fa2-summary-math-list">
        {values.map((value, index) => (
          <div key={`${value.label}-${index}`}>
            <small>{value.label}</small>
            <KatexSpan tex={value.tex} />
          </div>
        ))}
      </div>
    </div>
  );
}

function PointBadge({ label, tex, kind }: { label: string; tex: string; kind: string }) {
  const icon = kind === 'max' ? 'triangleUp' : kind === 'min' ? 'triangleDown' : kind === 'inflection' ? 'trend' : 'target';
  return <div className={`fa2-ext fa2-ext-${kind}`}><span className="fa2-ext-icon" aria-hidden="true"><SvgIcon name={icon} /></span><div className="fa2-ext-body"><span className="fa2-ext-kind">{label}</span><KatexSpan tex={tex} className="fa2-ext-coords" /></div></div>;
}

function Asymptote({ label, tex }: { label: string; tex: string }) {
  return <div className="fa2-asym"><span className="fa2-asym-tag">{label}</span><KatexSpan tex={tex} /></div>;
}

type IntervalAnalysis = NonNullable<AnalyzeResponse['interval_analysis']>;

type IntervalCandidate = { label: string; x: string; y: string; detail?: string };

function IntervalExtremaAnalysis({ interval }: { interval: IntervalAnalysis }) {
  const boundaryCandidates: IntervalCandidate[] = interval.boundary_evidence?.flatMap((item) => {
    const value = item.value.value_exact ?? item.value.value;
    if (value == null) return [];
    return [{
      label: item.kind === 'endpoint' ? 'Biên thuộc miền' : `Giới hạn phía ${item.side}`,
      x: item.x_exact,
      y: value,
      detail: `${analyzerStatusLabel(item.value.status)}; ${item.attained ? 'đạt trong miền' : 'không đạt tại biên'}`,
    }];
  }) ?? [
    { label: interval.open_a ? 'Giới hạn trái' : 'Cận trái', x: interval.a, y: interval.fa },
    { label: interval.open_b ? 'Giới hạn phải' : 'Cận phải', x: interval.b, y: interval.fb },
  ];
  const candidates: IntervalCandidate[] = [
    ...boundaryCandidates,
    ...interval.extrema_inside.map((point) => ({ label: point.label, x: point.x_exact || point.x, y: point.y })),
  ];

  const leftBracket = interval.open_a ? '(' : '[';
  const rightBracket = interval.open_b ? ')' : ']';

  return (
    <div className="fa2-interval-analysis">
      <div className="fa2-interval-overview">
        <KatexSpan tex={`x\\in${leftBracket}${mathTex(interval.a)},\\, ${mathTex(interval.b)}${rightBracket}`} />
        {interval.range_latex && <KatexSpan tex={`f(x)\\in ${interval.range_latex}`} />}
        {interval.domain_intersection_exact && <KatexSpan tex={`D\\cap I=${mathTex(interval.domain_intersection_exact)}`} />}
      </div>
      <details className="fa2-result-disclosure">
        <summary>Chi tiết phương pháp</summary>
        <div className="fa2-verification-details">
          <span>Độ đầy đủ: {analyzerStatusLabel(interval.status)}</span>
          <span>Phương pháp: {analyzerMethodLabel(interval.method)}</span>
          <span>Xét từng thành phần liên thông của tập xác định.</span>
        </div>
      </details>
      {!!interval.domain_components?.length && (
        <div className="fa2-interval-components" aria-label="Các thành phần miền được khảo sát">
          {interval.domain_components.map((component, index) => (
            <KatexSpan
              key={`${component.start_exact}-${component.end_exact}-${index}`}
              tex={`${component.left_open ? '(' : '['}${sympyToLatex(component.start_exact)},${sympyToLatex(component.end_exact)}${component.right_open ? ')' : ']'}`}
            />
          ))}
        </div>
      )}
      <table className="fa2-result-table fa2-interval-table"><thead><tr><th>Điểm xét</th><th><KatexSpan tex="x" /></th><th><KatexSpan tex="f(x)" /></th><th>Kiểm chứng</th></tr></thead><tbody>
        {candidates.map((candidate) => (
          <tr key={`${candidate.label}-${candidate.x}-${candidate.y}`}>
            <th>{candidate.label}</th>
            <td><KatexSpan tex={sympyToLatex(candidate.x)} /></td>
            <td><KatexSpan tex={sympyToLatex(candidate.y)} /></td>
            <td>{candidate.detail ?? 'Ứng viên đại số'}</td>
          </tr>
        ))}
      </tbody></table>
      {interval.supremum && (
        <div className="fa2-extreme-result">
          <KatexSpan tex={`${interval.supremum.attained ? '\\max' : '\\sup'} f=${interval.supremum.value_latex}`} />
          {interval.supremum.value_v2 && <CopyValueButtons label="Giá trị trên" value={interval.supremum.value_v2} />}
          <span>{interval.supremum.attained ? 'Đạt tại' : 'Không đạt'} {interval.supremum.attainment_set_latex && <KatexSpan tex={interval.supremum.attainment_set_latex} />}</span>
        </div>
      )}
      {interval.infimum && (
        <div className="fa2-extreme-result">
          <KatexSpan tex={`${interval.infimum.attained ? '\\min' : '\\inf'} f=${interval.infimum.value_latex}`} />
          {interval.infimum.value_v2 && <CopyValueButtons label="Giá trị dưới" value={interval.infimum.value_v2} />}
          <span>{interval.infimum.attained ? 'Đạt tại' : 'Không đạt'} {interval.infimum.attainment_set_latex && <KatexSpan tex={interval.infimum.attainment_set_latex} />}</span>
        </div>
      )}
      {!!interval.warnings?.length && (
        <ul className="fa2-tool-warnings">{interval.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
      )}
      <div className="fa2-conclusion">
        <strong>Kết luận</strong>
        <MixedTextRenderer text={interval.conclusion} />
      </div>
    </div>
  );
}

function IntervalLine({
  label,
  value,
  valueIsLatex = false,
  className,
}: {
  label: ReactNode;
  value: string;
  valueIsLatex?: boolean;
  className: string;
}) {
  return <div className={`fa2-mono ${className}`}><span className="fa2-mono-label">{label}</span><span className="fa2-mono-val"><KatexSpan tex={valueIsLatex ? value : mathTex(value)} /></span></div>;
}

function Section({
  title,
  icon,
  children,
  className = '',
  headTrailing,
}: {
  title: string;
  icon: IconName;
  children: ReactNode;
  className?: string;
  headTrailing?: ReactNode;
}) {
  return (
    <div className={`fa2-section ${className}`.trim()}>
      <div className="fa2-section-head">
        <span className="fa2-section-icon" aria-hidden="true"><SvgIcon name={icon} /></span>
        <span className="fa2-section-title">{title}</span>
        {headTrailing != null && headTrailing !== false && <div className="fa2-section-trailing">{headTrailing}</div>}
      </div>
      <div className="fa2-section-body">{children}</div>
    </div>
  );
}

