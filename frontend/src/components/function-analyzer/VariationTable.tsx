import { Fragment, useId, useState, type CSSProperties } from 'react';
import type { AnalyzeResponse } from '../../api/client';
import { KatexSpan, sympyToLatex } from '../KatexSpan';
import { SvgIcon } from './icons';

export function VariationTable({
  rows,
  expanded: expandedProp,
  onExpandedChange,
  hideZoomButton = false,
}: {
  rows: AnalyzeResponse['variation_table'];
  expanded?: boolean;
  onExpandedChange?: (open: boolean) => void;
  hideZoomButton?: boolean;
}) {
  const [internalExpanded, setInternalExpanded] = useState(false);
  const controlled = expandedProp !== undefined && onExpandedChange !== undefined;
  const isExpanded = controlled ? expandedProp : internalExpanded;
  const setIsExpanded = (open: boolean) => {
    if (controlled) onExpandedChange(open);
    else setInternalExpanded(open);
  };
  if (!rows || rows.length === 0) return null;
  const dynamicCols = rows.length * 2 - 1;
  const forceTimeline = rows.length > 4;
  const gridStyle = { '--bbt-cols': dynamicCols } as CSSProperties;

  return (
    <div className={`bbt-layout ${forceTimeline ? 'bbt-layout-force-timeline' : ''}`}>
      {!hideZoomButton && (
        <div className="bbt-actions">
          <button type="button" className="bbt-zoom-btn" onClick={() => setIsExpanded(true)} aria-label="Ấn để phóng to">
            <span aria-hidden="true"><SvgIcon name="magnify" /></span>
          </button>
        </div>
      )}
      <VariationGrid rows={rows} style={gridStyle} />
      <div className="bbt-timeline">
        {rows.slice(0, -1).map((row, index) => {
          const next = rows[index + 1];
          const direction = normalizeDirection(row.arrow_to_next);
          return (
            <div key={`tl-${index}`} className={`bbt-timeline-item ${direction === 'up' ? 'bbt-timeline-up' : direction === 'down' ? 'bbt-timeline-down' : ''}`}>
              <div className="bbt-timeline-range"><KatexSpan tex={`${sympyToLatex(row.x)} \\to ${sympyToLatex(next.x)}`} /></div>
              <div className="bbt-timeline-trend">{renderArrowLatex(row.arrow_to_next)}</div>
              <div className="bbt-timeline-values"><KatexSpan tex={`${nodeValueTex(rows, index)} \\to ${nodeValueTex(rows, index + 1)}`} /></div>
            </div>
          );
        })}
      </div>
      {isExpanded && (
        <div className="bbt-modal" role="dialog" aria-modal="true" aria-label="Bảng biến thiên phóng to" onClick={() => setIsExpanded(false)}>
          <div className="bbt-modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="bbt-modal-head">
              <span>Bảng biến thiên phóng to</span>
              <button type="button" className="bbt-modal-close" onClick={() => setIsExpanded(false)} aria-label="Đóng bảng biến thiên phóng to">Đóng</button>
            </div>
            <VariationGrid rows={rows} style={gridStyle} className="bbt-wrap-expanded" />
          </div>
        </div>
      )}
    </div>
  );
}

function VariationGrid({ rows, style, className = '' }: { rows: AnalyzeResponse['variation_table']; style: CSSProperties; className?: string }) {
  return (
    <div className={`bbt-wrap ${className}`.trim()} style={style}>
      <div className="bbt-row bbt-row-x">
        <div className="bbt-cell bbt-label"><KatexSpan tex="x" className="bbt-label-tex" /></div>
        {rows.map((row, index) => (
          <Fragment key={`x-${index}`}>
            <div className="bbt-cell bbt-x-val"><KatexSpan tex={sympyToLatex(row.x)} /></div>
            {index < rows.length - 1 && <div className="bbt-cell bbt-gap" />}
          </Fragment>
        ))}
      </div>
      <div className="bbt-row bbt-row-fp">
        <div className="bbt-cell bbt-label"><KatexSpan tex="f'(x)" className="bbt-label-tex" /></div>
        {rows.map((row, index) => (
          <Fragment key={`fp-${index}`}>
            <div className="bbt-cell bbt-zero">{renderMarkerLatex(row.kind)}</div>
            {index < rows.length - 1 && (
              <div className="bbt-cell bbt-gap bbt-fp-arrow">
                {renderDerivativeSignLatex(row.arrow_to_next)}
              </div>
            )}
          </Fragment>
        ))}
      </div>
      <div className="bbt-row bbt-row-f">
        <div className="bbt-cell bbt-label"><KatexSpan tex="f(x)" className="bbt-label-tex" /></div>
        {rows.map((row, index) => (
          <Fragment key={`f-${index}`}>
            <div className={`bbt-cell bbt-f-val ${valueLevelClass(rows, index)} ${row.kind === 'max' ? 'bbt-fmax' : row.kind === 'min' ? 'bbt-fmin' : ''}`}>
              {renderFunctionValueLatex(rows, row, index)}
            </div>
            {index < rows.length - 1 && (
              <div className="bbt-cell bbt-gap bbt-curve-cell">
                <VariationStroke direction={normalizeDirection(row.arrow_to_next)} />
              </div>
            )}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

function renderMarkerLatex(kind: string) {
  if (kind === 'max' || kind === 'min') return <KatexSpan tex="0" className="bbt-katex-inline" />;
  if (kind === 'asymptote') return <KatexSpan tex="\\parallel" className="bbt-katex-inline" />;
  return <span className="bbt-katex-placeholder" aria-hidden="true"> </span>;
}

function arrowSymbol(value: string | null) {
  const direction = normalizeDirection(value);
  if (direction === 'up') return '↗';
  if (direction === 'down') return '↘';
  return '→';
}

function arrowClass(value: string | null) {
  const direction = normalizeDirection(value);
  if (direction === 'up') return 'bbt-up';
  if (direction === 'down') return 'bbt-down';
  return '';
}

function derivativeSign(value: string | null) {
  const direction = normalizeDirection(value);
  if (direction === 'up') return '+';
  if (direction === 'down') return '−';
  return '';
}

function derivativeSignClass(value: string | null) {
  const direction = normalizeDirection(value);
  if (direction === 'up') return 'bbt-sign-pos';
  if (direction === 'down') return 'bbt-sign-neg';
  return '';
}

function normalizeDirection(value: string | null): 'up' | 'down' | null {
  if (!value) return null;
  const raw = value.trim().toLowerCase();
  if (raw.includes('↗') || raw.includes('up') || raw.includes('increase') || raw.includes('inc') || raw === '+') return 'up';
  if (raw.includes('↘') || raw.includes('down') || raw.includes('decrease') || raw.includes('dec') || raw === '-' || raw === '−') return 'down';
  return null;
}

function renderDerivativeSignLatex(value: string | null) {
  const sign = derivativeSign(value);
  if (!sign) return <span className="bbt-katex-placeholder" aria-hidden="true"> </span>;
  return <KatexSpan tex={sign === '+' ? '+' : '-'} className={`bbt-katex-inline ${derivativeSignClass(value)}`} />;
}

function renderArrowLatex(value: string | null) {
  const symbol = arrowSymbol(value);
  const tex = symbol === '↗' ? '\\nearrow' : symbol === '↘' ? '\\searrow' : '\\to';
  return <KatexSpan tex={tex} className={`bbt-katex-inline ${arrowClass(value)}`} />;
}

function renderFunctionValueLatex(
  rows: AnalyzeResponse['variation_table'],
  row: AnalyzeResponse['variation_table'][number],
  index: number,
) {
  if (row.y) return <KatexSpan tex={sympyToLatex(row.y)} />;
  if (row.kind === 'boundary') return <KatexSpan tex={boundaryInfinityTex(rows, index)} className="bbt-boundary" />;
  if (row.kind === 'asymptote') return <span className="bbt-katex-placeholder" aria-hidden="true"> </span>;
  return <span className="bbt-katex-placeholder" aria-hidden="true"> </span>;
}

function boundaryInfinityTex(rows: AnalyzeResponse['variation_table'], index: number) {
  if (index === 0) {
    const direction = normalizeDirection(rows[index]?.arrow_to_next ?? null);
    if (direction === 'down') return '+\\infty';
    if (direction === 'up') return '-\\infty';
    return '\\infty';
  }
  if (index === rows.length - 1) {
    const direction = normalizeDirection(rows[index - 1]?.arrow_to_next ?? null);
    if (direction === 'up') return '+\\infty';
    if (direction === 'down') return '-\\infty';
    return '\\infty';
  }
  return '\\infty';
}

function nodeValueTex(rows: AnalyzeResponse['variation_table'], index: number) {
  const row = rows[index];
  if (!row) return '\\varnothing';
  if (row.y) return sympyToLatex(row.y);
  if (row.kind === 'boundary') return boundaryInfinityTex(rows, index);
  return '\\varnothing';
}

function valueLevelClass(rows: AnalyzeResponse['variation_table'], index: number) {
  const current = rows[index];
  if (!current || current.kind === 'asymptote') return '';
  const incoming = normalizeDirection(index > 0 ? rows[index - 1]?.arrow_to_next ?? null : null);
  const outgoing = normalizeDirection(rows[index]?.arrow_to_next ?? null);

  if (!incoming && outgoing) return outgoing === 'up' ? 'bbt-level-low' : 'bbt-level-high';
  if (incoming && !outgoing) return incoming === 'up' ? 'bbt-level-high' : 'bbt-level-low';
  if (incoming === 'up' && outgoing === 'down') return 'bbt-level-high';
  if (incoming === 'down' && outgoing === 'up') return 'bbt-level-low';
  if (incoming === 'up' && outgoing === 'up') return 'bbt-level-mid';
  if (incoming === 'down' && outgoing === 'down') return 'bbt-level-mid';
  return '';
}

function VariationStroke({ direction }: { direction: 'up' | 'down' | null }) {
  const markerId = `${useId()}bbt-arrow`;
  const path = direction === 'up' ? 'M 8 34 L 92 8' : direction === 'down' ? 'M 8 8 L 92 34' : 'M 8 21 L 92 21';
  return (
    <svg viewBox="0 0 100 42" className={`bbt-stroke ${direction === 'up' ? 'bbt-up' : direction === 'down' ? 'bbt-down' : ''}`} aria-hidden="true">
      <defs>
        <marker id={markerId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
        </marker>
      </defs>
      <path d={path} fill="none" stroke="currentColor" strokeWidth="1.75" markerEnd={`url(#${markerId})`} />
    </svg>
  );
}


