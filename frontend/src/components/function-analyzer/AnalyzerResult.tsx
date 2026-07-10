import { useState, type ReactNode } from 'react';
import type { AnalyzeResponse } from '../../api/client';
import { KatexSpan, sympyToLatex } from '../KatexSpan';
import { TRANSFORM_LABEL_TEX } from './constants';
import { FunctionGraph } from './FunctionGraph';
import { SvgIcon, type IconName } from './icons';
import { VariationTable } from './VariationTable';

export function EmptyAnalyzerResult() {
  return (
    <div className="fa2-empty-result">
      <div className="fa2-empty-icon" aria-hidden="true"><SvgIcon name="graph" /></div>
      <strong>Đồ thị và kết quả sẽ hiện ở đây</strong>
      <span>Nhập công thức ở cột trái rồi bấm Phân tích để xem đồ thị, bảng biến thiên và các điểm đặc biệt.</span>
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

export function AnalyzerResult({ result, toolControls }: { result: AnalyzeResponse; toolControls: ReactNode }) {
  const hasShapeDetails = result.concave_up_intervals.length > 0 || result.concave_down_intervals.length > 0 || result.horizontal_asymptotes.length > 0 || result.vertical_asymptotes.length > 0 || !!result.oblique_asymptote;
  const [variationBbtOpen, setVariationBbtOpen] = useState(false);
  const [activeResultTab, setActiveResultTab] = useState<'quick' | 'tools'>('quick');
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
          <div className="fa2-result-tabs">
            <div className="fa2-tab-list" role="tablist" aria-label="Kết quả phân tích">
              <button type="button" role="tab" aria-selected={activeResultTab === 'quick'} className={`fa2-result-tab ${activeResultTab === 'quick' ? 'is-active' : ''}`} onClick={() => setActiveResultTab('quick')}>Kết quả nhanh</button>
              <button type="button" role="tab" aria-selected={activeResultTab === 'tools'} className={`fa2-result-tab ${activeResultTab === 'tools' ? 'is-active' : ''}`} onClick={() => setActiveResultTab('tools')}>Công cụ khảo sát</button>
            </div>
            <div className="fa2-tab-panel">
              {activeResultTab === 'quick' ? (
                <div className="fa2-quick-workbench">
                  <QuickSummary result={result} />

                  <Section
                    title="Đạo hàm và biến thiên"
                    icon="derivative"
                    headTrailing={
                      hasVariationTable ? (
                        <button type="button" className="bbt-zoom-btn bbt-zoom-btn-borderless" onClick={() => setVariationBbtOpen(true)} aria-label="Ấn để phóng to">
                          <span aria-hidden="true"><SvgIcon name="magnify" /></span>
                        </button>
                      ) : null
                    }
                  >
                    <div className="fa2-formula-row"><KatexSpan tex="f'(x)=" className="fa2-label-mono fa2-label-katex" /><KatexSpan tex={result.derivative_latex || sympyToLatex(result.derivative || '')} className="fa2-katex" /></div>
                    {result.second_derivative && <div className="fa2-formula-row"><KatexSpan tex="f''(x)=" className="fa2-label-mono fa2-label-katex" /><KatexSpan tex={result.second_derivative_latex || sympyToLatex(result.second_derivative)} className="fa2-katex" /></div>}
                    <VariationTable rows={result.variation_table} tableV2={result.variation_table_v2 ?? null} expanded={variationBbtOpen} onExpandedChange={setVariationBbtOpen} hideZoomButton />
                  </Section>

                  {hasShapeDetails && (
                    <Section title="Lồi lõm và tiệm cận" icon="asymptote">
                      <div className="fa2-compact-list">
                        {result.concave_up_intervals.length > 0 && <IntervalLine label="Lồi" value={result.concave_up_intervals.join(', ')} className="fa2-mono-inc" />}
                        {result.concave_down_intervals.length > 0 && <IntervalLine label="Lõm" value={result.concave_down_intervals.join(', ')} className="fa2-mono-dec" />}
                        {result.horizontal_asymptotes.map((ha, i) => <Asymptote key={`ha-${i}`} label="Ngang" tex={`y = ${sympyToLatex(ha.value)}`} />)}
                        {result.vertical_asymptotes.map((va, i) => <Asymptote key={`va-${i}`} label="Đứng" tex={`x = ${sympyToLatex(va.x)}`} />)}
                        {result.oblique_asymptote && <Asymptote label="Xiên" tex={sympyToLatex(result.oblique_asymptote)} />}
                      </div>
                    </Section>
                  )}
                </div>
              ) : (
                <div className="fa2-tools-workbench">
                  {toolControls}
                  <ToolAnalysisResults result={result} />
                </div>
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

function ToolAnalysisResults({ result }: { result: AnalyzeResponse }) {
  const hasToolResults = !!result.interval_analysis || !!result.line_analysis || !!result.transform_preview;

  if (!hasToolResults) {
    return <div className="fa2-tool-empty">Chọn công cụ để xem kết quả.</div>;
  }

  return (
    <div className="fa2-tool-results">
      {result.interval_analysis && (
        <Section title="GTLN/GTNN trên đoạn" icon="points">
          <IntervalExtremaAnalysis interval={result.interval_analysis} />
        </Section>
      )}

      {result.line_analysis && (
        <Section title={result.line_analysis.mode === 'tangent_at' ? 'Tiếp tuyến đồ thị' : 'Tương giao với đường thẳng'} icon="graph">
          <div className="fa2-compact-list">
            <IntervalLine label={result.line_analysis.mode === 'tangent_at' ? 'Tiếp tuyến' : 'Đường thẳng'} value={result.line_analysis.equation} className="fa2-mono-inc" />
            
            {result.line_analysis.mode === 'tangent_at' ? (
              <div className="fa2-transform-formula" style={{ marginTop: 12 }}>
                <strong>Kết luận:</strong> {result.line_analysis.conclusion}
              </div>
            ) : (
              <>
                <IntervalLine label="Số giao điểm" value={String(result.line_analysis.intersection_count)} className="fa2-mono-inc" />
                {result.line_analysis.intersections.map((pt, index) => <PointBadge key={`line-${index}`} label="Giao điểm" tex={`(${sympyToLatex(pt.x)},\\; ${sympyToLatex(pt.y)})`} kind="axis" />)}
                {result.line_analysis.relative_intervals.above.length > 0 && <IntervalLine label="f(x) > d" value={result.line_analysis.relative_intervals.above.join(', ')} className="fa2-mono-inc" />}
                {result.line_analysis.relative_intervals.below.length > 0 && <IntervalLine label="f(x) < d" value={result.line_analysis.relative_intervals.below.join(', ')} className="fa2-mono-dec" />}
                {result.line_analysis.area_between_curves && (
                  <IntervalLine label="Diện tích hình phẳng" value={result.line_analysis.area_between_curves} className="fa2-mono-inc" />
                )}
              </>
            )}
          </div>
        </Section>
      )}

      {result.transform_preview && (
        <Section title="Biến đổi đồ thị" icon="graph">
          <div className="fa2-transform-formula">
            <KatexSpan tex={TRANSFORM_LABEL_TEX[result.transform_preview.type] ?? sympyToLatex(result.transform_preview.label)} className="fa2-transform-rule" />
            <KatexSpan tex={`g(x)=${result.transform_preview.expression_latex || sympyToLatex(result.transform_preview.expression)}`} className="fa2-katex" />
          </div>
          {result.transform_preview.pedagogical_steps && result.transform_preview.pedagogical_steps.length > 0 && (
            <div className="fa2-pedagogical-steps" style={{ marginTop: 16, fontSize: '0.9em', color: 'var(--text-secondary)' }}>
              <strong>Các bước biến đổi:</strong>
              <ul style={{ paddingLeft: 20, marginTop: 8 }}>
                {result.transform_preview.pedagogical_steps.map((step, idx) => (
                  <li key={`step-${idx}`}>{step}</li>
                ))}
              </ul>
            </div>
          )}
        </Section>
      )}
    </div>
  );
}

function QuickSummary({ result }: { result: AnalyzeResponse }) {
  const expressionTex = result.evaluated_expression_latex || result.expression_latex || sympyToLatex(result.evaluated_expression || result.expression);

  return (
    <div className="fa2-quick-card">
      <div className="fa2-quick-head">
        <span className="fa2-quick-eyebrow">Kết quả nhanh</span>
        <KatexSpan tex={`y=${expressionTex}`} className="fa2-quick-expression" />
      </div>
      <div className="fa2-quick-rows">
        {result.domain_latex && <SummaryCard label="Tập xác định" tex={result.domain_latex} />}
        {result.range_latex && <SummaryCard label="Tập giá trị" tex={result.range_latex} />}
        {(result.derivative_latex || result.derivative) && <SummaryCard label="Đạo hàm" tex={result.derivative_latex || sympyToLatex(result.derivative || '')} />}
      </div>
    </div>
  );
}

function SummaryCard({ label, tex }: { label: string; tex: string }) {
  return <div className="fa2-summary-card"><span>{label}</span><KatexSpan tex={tex} /></div>;
}

function PointBadge({ label, tex, kind }: { label: string; tex: string; kind: string }) {
  const icon = kind === 'max' ? 'triangleUp' : kind === 'min' ? 'triangleDown' : kind === 'inflection' ? 'trend' : 'target';
  return <div className={`fa2-ext fa2-ext-${kind}`}><span className="fa2-ext-icon" aria-hidden="true"><SvgIcon name={icon} /></span><div className="fa2-ext-body"><span className="fa2-ext-kind">{label}</span><KatexSpan tex={tex} className="fa2-ext-coords" /></div></div>;
}

function Asymptote({ label, tex }: { label: string; tex: string }) {
  return <div className="fa2-asym"><span className="fa2-asym-tag">{label}</span><KatexSpan tex={tex} /></div>;
}

type IntervalAnalysis = NonNullable<AnalyzeResponse['interval_analysis']>;

type IntervalCandidate = { label: string; x: string; y: string };

function intervalExtremaConclusionTex(kind: 'max' | 'min', data: IntervalAnalysis): string {
  const a = sympyToLatex(data.a);
  const b = sympyToLatex(data.b);
  const pt = kind === 'max' ? data.max_point : data.min_point;
  const op = kind === 'max' ? '\\max' : '\\min';
  const xv = sympyToLatex(pt.x);
  const yv = sympyToLatex(pt.y);
  return `\\displaystyle ${op}_{x\\in\\left[${a},\\,${b}\\right]} f(x)=f\\left(${xv}\\right)=${yv}`;
}

function IntervalExtremaAnalysis({ interval }: { interval: IntervalAnalysis }) {
  const candidates: IntervalCandidate[] = [
    { label: interval.open_a ? 'Giới hạn trái' : 'Cận trái', x: interval.a, y: interval.fa },
    { label: interval.open_b ? 'Giới hạn phải' : 'Cận phải', x: interval.b, y: interval.fb },
    ...interval.extrema_inside.map((point) => ({ label: point.label, x: point.x_exact || point.x, y: point.y })),
  ];

  const leftBracket = interval.open_a ? '(' : '[';
  const rightBracket = interval.open_b ? ')' : ']';

  return (
    <div className="fa2-interval-analysis">
      <div className="fa2-interval-note" style={{ flexDirection: 'column', textAlign: 'center', gap: 8 }}>
        <KatexSpan tex={`x\\in${leftBracket}${sympyToLatex(interval.a)},\\, ${sympyToLatex(interval.b)}${rightBracket}`} />
        <span>Xét giá trị tại hai cận và các điểm cực trị nằm trong vùng khảo sát.</span>
      </div>
      <table className="fa2-result-table fa2-interval-table"><thead><tr><th>Điểm xét</th><th><KatexSpan tex="x" /></th><th><KatexSpan tex="f(x)" /></th></tr></thead><tbody>
        {candidates.map((candidate) => (
          <tr key={`${candidate.label}-${candidate.x}-${candidate.y}`}>
            <th>{candidate.label}</th>
            <td><KatexSpan tex={sympyToLatex(candidate.x)} /></td>
            <td><KatexSpan tex={sympyToLatex(candidate.y)} /></td>
          </tr>
        ))}
      </tbody></table>
      <div className="fa2-extrema-conclusion" style={{ marginTop: 16, fontSize: '0.95em' }}>
        <strong>Kết luận:</strong> {interval.conclusion}
      </div>
    </div>
  );
}

function IntervalLine({ label, value, className }: { label: string; value: string; className: string }) {
  return <div className={`fa2-mono ${className}`}><span className="fa2-mono-label">{label}:</span><span className="fa2-mono-val"><KatexSpan tex={sympyToLatex(value)} /></span></div>;
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

