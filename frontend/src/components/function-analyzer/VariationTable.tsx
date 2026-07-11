import { Fragment, useEffect, useId, useRef, useState, type CSSProperties } from 'react';
import type { AnalyzeResponse, VariationNodeV2, VariationSegmentV2, VariationTableV2 } from '../../api/client';
import { KatexSpan, sympyToLatex } from '../KatexSpan';
import { SvgIcon } from './icons';

export function VariationTable({
  rows,
  tableV2 = null,
  expanded: expandedProp,
  onExpandedChange,
  hideZoomButton = false,
}: {
  rows: AnalyzeResponse['variation_table'];
  tableV2?: VariationTableV2 | null;
  expanded?: boolean;
  onExpandedChange?: (open: boolean) => void;
  hideZoomButton?: boolean;
}) {
  const [internalExpanded, setInternalExpanded] = useState(false);
  const modalRef = useRef<HTMLDivElement | null>(null);
  const zoomButtonRef = useRef<HTMLButtonElement | null>(null);
  const controlled = expandedProp !== undefined && onExpandedChange !== undefined;
  const isExpanded = controlled ? expandedProp : internalExpanded;
  const setIsExpanded = (open: boolean) => {
    if (controlled) onExpandedChange(open);
    else setInternalExpanded(open);
  };

  useEffect(() => {
    if (!isExpanded) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : zoomButtonRef.current;
    const modal = modalRef.current;
    modal?.querySelector<HTMLElement>('button')?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        setIsExpanded(false);
        return;
      }
      if (event.key !== 'Tab' || !modal) return;
      const focusable = Array.from(modal.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previousFocus?.focus();
    };
  }, [isExpanded]);

  const canRenderV2 = !!tableV2 && tableV2.nodes.length > 0;
  const hasLegacyRows = !!rows && rows.length > 0;
  if (!canRenderV2 && !hasLegacyRows) return null;

  const dynamicCols = (canRenderV2 ? tableV2.nodes.length : rows.length) * 2 - 1;
  const forceTimeline = (canRenderV2 ? tableV2.nodes.length : rows.length) > 4;
  const gridStyle = { '--bbt-cols': dynamicCols } as CSSProperties;

  return (
    <div className={`bbt-layout ${forceTimeline ? 'bbt-layout-force-timeline' : ''}`}>
      {!hideZoomButton && (
        <div className="bbt-actions">
          <button ref={zoomButtonRef} type="button" className="bbt-zoom-btn" onClick={() => setIsExpanded(true)} aria-label="Phóng to bảng biến thiên">
            <span aria-hidden="true"><SvgIcon name="magnify" /></span>
          </button>
        </div>
      )}
      {canRenderV2 ? <VariationGridV2 table={tableV2} style={gridStyle} /> : <VariationGridLegacy rows={rows} style={gridStyle} />}
      {canRenderV2 && <VariationSemanticTable table={tableV2} />}
      {canRenderV2 ? <VariationTimelineV2 table={tableV2} /> : <VariationTimelineLegacy rows={rows} />}
      {isExpanded && (
        <div className="bbt-modal" role="dialog" aria-modal="true" aria-labelledby="bbt-modal-title" onClick={() => setIsExpanded(false)}>
          <div ref={modalRef} className="bbt-modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="bbt-modal-head">
              <span id="bbt-modal-title">Bảng biến thiên phóng to</span>
              <button type="button" className="bbt-modal-close" onClick={() => setIsExpanded(false)} aria-label="Đóng bảng biến thiên phóng to">Đóng</button>
            </div>
            {canRenderV2 ? <VariationGridV2 table={tableV2} style={gridStyle} className="bbt-wrap-expanded" /> : <VariationGridLegacy rows={rows} style={gridStyle} className="bbt-wrap-expanded" />}
          </div>
        </div>
      )}
    </div>
  );
}

function VariationSemanticTable({ table }: { table: VariationTableV2 }) {
  return (
    <table className="sr-only">
      <caption>Bảng biến thiên dạng văn bản</caption>
      <thead><tr><th>Khoảng</th><th>Dấu đạo hàm</th><th>Chiều biến thiên</th><th>Kiểm chứng</th></tr></thead>
      <tbody>
        {table.segments.map((segment, index) => (
          <tr key={`semantic-${index}`}>
            <td>{segment.left} đến {segment.right}</td>
            <td>{segment.derivative_sign}</td>
            <td>{directionLabel(segment.direction)}</td>
            <td>{segment.verification}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function directionLabel(direction: string) {
  return direction === 'increasing' ? 'Đồng biến' : direction === 'decreasing' ? 'Nghịch biến' : direction === 'constant' ? 'Không đổi' : 'Chưa xác định';
}

function VariationGridV2({ table, style, className = '' }: { table: VariationTableV2; style: CSSProperties; className?: string }) {
  return (
    <div className={`bbt-wrap ${className}`.trim()} style={style}>
      {table.status !== 'complete' && table.warnings.length > 0 && (
        <div className="bbt-v2-warning" style={{ gridColumn: `1 / span ${table.nodes.length * 2}` }}>
          {table.warnings[0]}
        </div>
      )}
      <div className="bbt-row bbt-row-x">
        <div className="bbt-cell bbt-label"><KatexSpan tex="x" className="bbt-label-tex" /></div>
        {table.nodes.map((node, index) => (
          <Fragment key={`x-${index}-${node.x}`}>
            <div className={`bbt-cell bbt-x-val ${node.kind === 'asymptote' ? 'bbt-asymptote' : ''}`}><KatexSpan tex={sympyToLatex(node.x_exact || node.x)} /></div>
            {index < table.nodes.length - 1 && <div className="bbt-cell bbt-gap" />}
          </Fragment>
        ))}
      </div>
      <div className="bbt-row bbt-row-fp">
        <div className="bbt-cell bbt-label"><KatexSpan tex="f'(x)" className="bbt-label-tex" /></div>
        {table.nodes.map((node, index) => (
          <Fragment key={`fp-${index}-${node.x}`}>
            <div className="bbt-cell bbt-zero">{renderMarkerLatex(node)}</div>
            {index < table.nodes.length - 1 && (
              <div className="bbt-cell bbt-gap bbt-fp-arrow">
                {renderDerivativeSignLatexV2(table.segments[index])}
              </div>
            )}
          </Fragment>
        ))}
      </div>
      <div className="bbt-row bbt-row-f">
        <div className="bbt-cell bbt-label"><KatexSpan tex="f(x)" className="bbt-label-tex" /></div>
        {table.nodes.map((node, index) => (
          <Fragment key={`f-${index}-${node.x}`}>
            <div className={`bbt-cell bbt-f-val ${valueLevelClassV2(table, index)} ${node.kind === 'max' ? 'bbt-fmax' : node.kind === 'min' ? 'bbt-fmin' : ''}`}>
              {renderFunctionValueLatexV2(node, index, table.nodes.length)}
            </div>
            {index < table.nodes.length - 1 && (
              <div className="bbt-cell bbt-gap bbt-curve-cell">
                <VariationStroke direction={normalizeDirectionV2(table.segments[index]?.direction)} />
              </div>
            )}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

function VariationTimelineV2({ table }: { table: VariationTableV2 }) {
  return (
    <div className="bbt-timeline">
      {table.segments.map((segment, index) => {
        const left = table.nodes[index];
        const right = table.nodes[index + 1];
        const direction = normalizeDirectionV2(segment.direction);
        return (
          <div key={`tl-v2-${index}`} className={`bbt-timeline-item ${direction === 'up' ? 'bbt-timeline-up' : direction === 'down' ? 'bbt-timeline-down' : direction === 'unknown' ? 'bbt-timeline-unknown' : ''}`}>
            <div className="bbt-timeline-range"><KatexSpan tex={`${sympyToLatex(segment.left)} \\to ${sympyToLatex(segment.right)}`} /></div>
            <div className="bbt-timeline-trend">{renderArrowLatexV2(segment)}</div>
            <div className="bbt-timeline-values"><KatexSpan tex={`${nodeValueTexV2(left, index, table.nodes.length)} \\to ${nodeValueTexV2(right, index + 1, table.nodes.length)}`} /></div>
          </div>
        );
      })}
    </div>
  );
}

function VariationGridLegacy({ rows, style, className = '' }: { rows: AnalyzeResponse['variation_table']; style: CSSProperties; className?: string }) {
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
            {index < rows.length - 1 && <div className="bbt-cell bbt-gap bbt-fp-arrow">{renderDerivativeSignLatexLegacy(row.arrow_to_next)}</div>}
          </Fragment>
        ))}
      </div>
      <div className="bbt-row bbt-row-f">
        <div className="bbt-cell bbt-label"><KatexSpan tex="f(x)" className="bbt-label-tex" /></div>
        {rows.map((row, index) => (
          <Fragment key={`f-${index}`}>
            <div className={`bbt-cell bbt-f-val ${valueLevelClassLegacy(rows, index)} ${row.kind === 'max' ? 'bbt-fmax' : row.kind === 'min' ? 'bbt-fmin' : ''}`}>
              {renderFunctionValueLatexLegacy(rows, row, index)}
            </div>
            {index < rows.length - 1 && (
              <div className="bbt-cell bbt-gap bbt-curve-cell">
                <VariationStroke direction={normalizeDirectionLegacy(row.arrow_to_next)} />
              </div>
            )}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

function VariationTimelineLegacy({ rows }: { rows: AnalyzeResponse['variation_table'] }) {
  return (
    <div className="bbt-timeline">
      {rows.slice(0, -1).map((row, index) => {
        const next = rows[index + 1];
        const direction = normalizeDirectionLegacy(row.arrow_to_next);
        return (
          <div key={`tl-${index}`} className={`bbt-timeline-item ${direction === 'up' ? 'bbt-timeline-up' : direction === 'down' ? 'bbt-timeline-down' : ''}`}>
            <div className="bbt-timeline-range"><KatexSpan tex={`${sympyToLatex(row.x)} \\to ${sympyToLatex(next.x)}`} /></div>
            <div className="bbt-timeline-trend">{renderArrowLatexLegacy(row.arrow_to_next)}</div>
            <div className="bbt-timeline-values"><KatexSpan tex={`${nodeValueTexLegacy(rows, index)} \\to ${nodeValueTexLegacy(rows, index + 1)}`} /></div>
          </div>
        );
      })}
    </div>
  );
}

function renderMarkerLatex(value: string | VariationNodeV2) {
  const node = typeof value === 'string' ? null : value;
  const kind = typeof value === 'string' ? value : value.kind;
  if (kind === 'max' || kind === 'min' || kind === 'critical' || kind === 'stationary_inflection') return <KatexSpan tex="0" className="bbt-katex-inline" />;
  if (kind === 'asymptote') return <KatexSpan tex="\\parallel" className="bbt-katex-inline" />;
  if (kind === 'hole' || (kind === 'boundary' && node?.open && !['-oo', 'oo'].includes(node.x_exact || ''))) return <KatexSpan tex="\\circ" className="bbt-katex-inline" />;
  if (kind === 'unknown') return <span className="bbt-unknown">?</span>;
  return <span className="bbt-katex-placeholder" aria-hidden="true"> </span>;
}

function renderFunctionValueLatexV2(node: VariationNodeV2, index: number, count: number) {
  if (node.kind === 'asymptote') return <SplitLimit node={node} />;
  if (node.kind === 'hole' && (node.y_exact || node.y)) return <KatexSpan tex={`\\circ\,${sympyToLatex(node.y_exact || node.y || '')}`} className="bbt-hole-value" />;
  if (node.y_exact || node.y) return <KatexSpan tex={sympyToLatex(node.y_exact || node.y || '')} />;
  const limit = index === 0 ? node.right_limit : index === count - 1 ? node.left_limit : node.left_limit || node.right_limit;
  return <LimitValue limit={limit} />;
}

function SplitLimit({ node }: { node: VariationNodeV2 }) {
  return (
    <span className="bbt-split-limit" aria-label="Giới hạn trái và phải tại tiệm cận">
      <LimitValue limit={node.left_limit} />
      <span className="bbt-split-divider" aria-hidden="true">|</span>
      <LimitValue limit={node.right_limit} />
    </span>
  );
}

function LimitValue({ limit }: { limit?: VariationNodeV2['left_limit'] }) {
  if (!limit || limit.status === 'unknown') return <span className="bbt-unknown">?</span>;
  if (limit.status === 'dne') return <KatexSpan tex="\\nexists" className="bbt-katex-inline bbt-unknown" />;
  if (!limit.value) return <span className="bbt-unknown">?</span>;
  return <KatexSpan tex={sympyToLatex(limit.value)} />;
}

function nodeValueTexV2(node: VariationNodeV2 | undefined, index: number, count: number) {
  if (!node) return '\\varnothing';
  if (node.y_exact || node.y) return sympyToLatex(node.y_exact || node.y || '');
  const limit = index === 0 ? node.right_limit : index === count - 1 ? node.left_limit : node.left_limit || node.right_limit;
  return limitTex(limit);
}

function limitTex(limit?: VariationNodeV2['left_limit']) {
  if (!limit || limit.status === 'unknown' || !limit.value) return '?';
  if (limit.status === 'dne') return '\\nexists';
  return sympyToLatex(limit.value);
}

function normalizeDirectionV2(value: string | undefined): 'up' | 'down' | 'flat' | 'unknown' {
  if (value === 'increasing') return 'up';
  if (value === 'decreasing') return 'down';
  if (value === 'constant') return 'flat';
  return 'unknown';
}

function renderDerivativeSignLatexV2(segment: VariationSegmentV2 | undefined) {
  if (!segment || segment.derivative_sign === 'unknown') return <span className="bbt-unknown">?</span>;
  if (segment.derivative_sign === '0') return <KatexSpan tex="0" className="bbt-katex-inline" />;
  return <KatexSpan tex={segment.derivative_sign === '+' ? '+' : '-'} className={`bbt-katex-inline ${segment.derivative_sign === '+' ? 'bbt-sign-pos' : 'bbt-sign-neg'}`} />;
}

function renderArrowLatexV2(segment: VariationSegmentV2 | undefined) {
  const direction = normalizeDirectionV2(segment?.direction);
  if (direction === 'up') return <KatexSpan tex="\\nearrow" className="bbt-katex-inline bbt-up" />;
  if (direction === 'down') return <KatexSpan tex="\\searrow" className="bbt-katex-inline bbt-down" />;
  if (direction === 'flat') return <KatexSpan tex="\\to" className="bbt-katex-inline" />;
  return <span className="bbt-unknown">?</span>;
}

function valueLevelClassV2(table: VariationTableV2, index: number) {
  const incoming = normalizeDirectionV2(index > 0 ? table.segments[index - 1]?.direction : undefined);
  const outgoing = normalizeDirectionV2(table.segments[index]?.direction);
  if (incoming === 'unknown' && outgoing !== 'unknown') return outgoing === 'up' ? 'bbt-level-low' : outgoing === 'down' ? 'bbt-level-high' : 'bbt-level-mid';
  if (incoming !== 'unknown' && outgoing === 'unknown') return incoming === 'up' ? 'bbt-level-high' : incoming === 'down' ? 'bbt-level-low' : 'bbt-level-mid';
  if (incoming === 'up' && outgoing === 'down') return 'bbt-level-high';
  if (incoming === 'down' && outgoing === 'up') return 'bbt-level-low';
  if (incoming === 'up' && outgoing === 'up') return 'bbt-level-mid';
  if (incoming === 'down' && outgoing === 'down') return 'bbt-level-mid';
  return '';
}

function normalizeDirectionLegacy(value: string | null): 'up' | 'down' | 'unknown' {
  if (!value) return 'unknown';
  const raw = value.trim().toLowerCase();
  if (raw.includes('↗') || raw.includes('up') || raw.includes('increase') || raw.includes('inc') || raw === '+') return 'up';
  if (raw.includes('↘') || raw.includes('down') || raw.includes('decrease') || raw.includes('dec') || raw === '-' || raw === '−') return 'down';
  return 'unknown';
}

function renderDerivativeSignLatexLegacy(value: string | null) {
  const direction = normalizeDirectionLegacy(value);
  if (direction === 'unknown') return <span className="bbt-katex-placeholder" aria-hidden="true"> </span>;
  return <KatexSpan tex={direction === 'up' ? '+' : '-'} className={`bbt-katex-inline ${direction === 'up' ? 'bbt-sign-pos' : 'bbt-sign-neg'}`} />;
}

function renderArrowLatexLegacy(value: string | null) {
  const direction = normalizeDirectionLegacy(value);
  const tex = direction === 'up' ? '\\nearrow' : direction === 'down' ? '\\searrow' : '\\to';
  return <KatexSpan tex={tex} className={`bbt-katex-inline ${direction === 'up' ? 'bbt-up' : direction === 'down' ? 'bbt-down' : ''}`} />;
}

function renderFunctionValueLatexLegacy(rows: AnalyzeResponse['variation_table'], row: AnalyzeResponse['variation_table'][number], index: number) {
  if (row.y) return <KatexSpan tex={sympyToLatex(row.y)} />;
  if (row.kind === 'boundary') return <KatexSpan tex={boundaryInfinityTexLegacy(rows, index)} className="bbt-boundary" />;
  return <span className="bbt-katex-placeholder" aria-hidden="true"> </span>;
}

function boundaryInfinityTexLegacy(_rows: AnalyzeResponse['variation_table'], _index: number) {
  return '?';
}

function nodeValueTexLegacy(rows: AnalyzeResponse['variation_table'], index: number) {
  const row = rows[index];
  if (!row) return '\\varnothing';
  if (row.y) return sympyToLatex(row.y);
  if (row.kind === 'boundary') return boundaryInfinityTexLegacy(rows, index);
  return '\\varnothing';
}

function valueLevelClassLegacy(rows: AnalyzeResponse['variation_table'], index: number) {
  const current = rows[index];
  if (!current || current.kind === 'asymptote') return '';
  const incoming = index > 0 ? normalizeDirectionLegacy(rows[index - 1]?.arrow_to_next ?? null) : 'unknown';
  const outgoing = normalizeDirectionLegacy(rows[index]?.arrow_to_next ?? null);
  if (incoming === 'unknown' && outgoing !== 'unknown') return outgoing === 'up' ? 'bbt-level-low' : 'bbt-level-high';
  if (incoming !== 'unknown' && outgoing === 'unknown') return incoming === 'up' ? 'bbt-level-high' : 'bbt-level-low';
  if (incoming === 'up' && outgoing === 'down') return 'bbt-level-high';
  if (incoming === 'down' && outgoing === 'up') return 'bbt-level-low';
  if (incoming === 'up' && outgoing === 'up') return 'bbt-level-mid';
  if (incoming === 'down' && outgoing === 'down') return 'bbt-level-mid';
  return '';
}

function VariationStroke({ direction }: { direction: 'up' | 'down' | 'flat' | 'unknown' }) {
  const markerId = `${useId()}bbt-arrow`;
  const path = direction === 'up' ? 'M 8 34 L 92 8' : direction === 'down' ? 'M 8 8 L 92 34' : 'M 8 21 L 92 21';
  const isUnknown = direction === 'unknown';
  return (
    <svg viewBox="0 0 100 42" className={`bbt-stroke ${direction === 'up' ? 'bbt-up' : direction === 'down' ? 'bbt-down' : direction === 'flat' ? 'bbt-flat' : 'bbt-stroke-unknown'}`} aria-hidden="true">
      <defs>
        <marker id={markerId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
        </marker>
      </defs>
      <path d={path} fill="none" stroke="currentColor" strokeWidth="1.75" strokeDasharray={isUnknown ? '6 5' : undefined} markerEnd={isUnknown ? undefined : `url(#${markerId})`} />
      {isUnknown && <text x="50" y="25" textAnchor="middle" className="bbt-unknown-svg">?</text>}
    </svg>
  );
}