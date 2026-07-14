export interface SegmentAppearanceInput {
  color?: string | null;
  line_width?: number | null;
  style?: 'solid' | 'dashed' | 'dotted' | null;
}

export interface SegmentAppearance {
  color: string;
  lineWidth: number;
  dashed: boolean;
  dashSize: number;
  gapSize: number;
  opacity: number;
}

export function segmentAppearance(
  segment: SegmentAppearanceInput,
  dynamicHidden: boolean,
  highlighted: boolean,
): SegmentAppearance {
  const dotted = segment.style === 'dotted';
  const dashed = dynamicHidden || dotted || segment.style === 'dashed';
  const requestedWidth = clamp(segment.line_width ?? 2, 1, 4);

  if (highlighted) {
    return {
      color: '#f97316',
      lineWidth: Math.max(requestedWidth, 4),
      dashed,
      dashSize: dotted ? 0.05 : 0.18,
      gapSize: dotted ? 0.1 : 0.11,
      opacity: 1,
    };
  }
  if (dynamicHidden) {
    return {
      color: '#9aa4b2',
      lineWidth: Math.min(requestedWidth, 1.4),
      dashed: true,
      dashSize: 0.26,
      gapSize: 0.16,
      opacity: 0.62,
    };
  }
  return {
    color: segment.color ?? '#1d3557',
    lineWidth: requestedWidth,
    dashed,
    dashSize: dotted ? 0.05 : 0.18,
    gapSize: dotted ? 0.1 : 0.11,
    opacity: 1,
  };
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}
