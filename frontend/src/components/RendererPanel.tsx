import type { RenderResponse } from '../types/scene';
import { GeoGebraView } from './GeoGebraView';
import { ThreeGeometryView } from './ThreeGeometryView';

interface RendererPanelProps {
  result: RenderResponse | null;
}

export function RendererPanel({ result }: RendererPanelProps) {
  if (!result) {
    return <div className="empty-state">Nhập đề bài để bắt đầu dựng hình.</div>;
  }

  if (result.payload.renderer.startsWith('geogebra')) {
    return <GeoGebraView commands={result.payload.geogebra_commands} />;
  }

  if (result.payload.three_scene) {
    return <ThreeGeometryView scene={result.payload.three_scene} />;
  }

  return <div className="empty-state">Không có dữ liệu renderer phù hợp.</div>;
}
