import type { RenderResponse } from '../types/scene';

type Vec3 = { x: number; y: number; z: number };
import { GeoGebraView } from './GeoGebraView';
import { ThreeGeometryView, type ThreeSceneInteraction } from './ThreeGeometryView';

interface RendererPanelProps {
  result: RenderResponse | null;
  threeInteraction?: ThreeSceneInteraction;
  onGeoGebraPointChange?: (name: string, point: Vec3) => void | Promise<void>;
}

export function RendererPanel({ result, threeInteraction, onGeoGebraPointChange }: RendererPanelProps) {
  if (!result) {
    return <EmptyState />;
  }

  if (result.payload.renderer === 'geogebra_2d' || result.payload.renderer === 'geogebra_3d') {
    return <GeoGebraView commands={result.payload.geogebra_commands} renderer={result.payload.renderer} scene={result.scene} view={result.scene.view} onPointChange={onGeoGebraPointChange} />;
  }

  if (result.payload.three_scene) {
    return <ThreeGeometryView scene={result.payload.three_scene} interaction={threeInteraction} />;
  }

  return (
    <div className="empty-state">
      <div className="empty-state-content">
        <GeometryIllustration />
        <h2>Không có dữ liệu renderer phù hợp</h2>
        <p>Hãy thử chọn công cụ vẽ khác trong phần tùy chọn nâng cao.</p>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="empty-state">
      <div className="empty-state-content">
        <GeometryIllustration />
        <h2>Chưa có hình dựng</h2>
        <p>Nhập đề bài hoặc chọn một đề mẫu bên trái để bắt đầu.</p>
      </div>
    </div>
  );
}

function GeometryIllustration() {
  return (
    <svg className="empty-state-graphic" viewBox="0 0 220 160" aria-hidden="true">
      <rect x="24" y="22" width="172" height="116" rx="18" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M58 112L102 48L156 112Z" fill="none" stroke="currentColor" strokeWidth="3" strokeLinejoin="round" />
      <path d="M102 48L102 112" fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="6 6" />
      <circle cx="58" cy="112" r="5" fill="currentColor" />
      <circle cx="102" cy="48" r="5" fill="currentColor" />
      <circle cx="156" cy="112" r="5" fill="currentColor" />
      <path d="M42 128H178" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
