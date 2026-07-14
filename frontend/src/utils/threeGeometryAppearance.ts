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

export function faceOpacity(requested: number): number {
  if (requested >= 0.45) return clamp(requested, 0.45, 0.68);
  return clamp(requested, 0.2, 0.28);
}

export function planeOpacity(requested: number): number {
  if (requested >= 0.2) return clamp(requested, 0.14, 0.28);
  return clamp(requested * 0.55, 0.06, 0.12);
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
      color: '#748094',
      lineWidth: Math.min(Math.max(requestedWidth, 1.7), 2),
      dashed: true,
      dashSize: 0.22,
      gapSize: 0.13,
      opacity: 0.78,
    };
  }
  const primarySolid = !dashed && (!segment.color || segment.color.toLowerCase() === '#1d3557');
  return {
    color: segment.color ?? '#1d3557',
    lineWidth: primarySolid ? Math.max(requestedWidth, 2.6) : requestedWidth,
    dashed,
    dashSize: dotted ? 0.05 : 0.18,
    gapSize: dotted ? 0.1 : 0.11,
    opacity: 1,
  };
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}
