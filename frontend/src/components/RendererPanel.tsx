import { lazy, Suspense } from 'react';
import type { RenderResponse } from '../types/scene';

type Vec3 = { x: number; y: number; z: number };
import { GeoGebraView } from './GeoGebraView';
import type { ThreeSceneImageCapture, ThreeSceneInteraction } from './ThreeGeometryView';

const ThreeGeometryView = lazy(() => import('./ThreeGeometryView').then((module) => ({ default: module.ThreeGeometryView })));

interface RendererPanelProps {
  result: RenderResponse | null;
  threeInteraction?: ThreeSceneInteraction;
  onGeoGebraPointChange?: (name: string, point: Vec3) => void | Promise<void>;
  highlightedObjects?: string[];
  saving?: boolean;
  onThreeImageCaptureReady?: (capture: ThreeSceneImageCapture | null) => void;
}

export function RendererPanel({ result, threeInteraction, onGeoGebraPointChange, highlightedObjects, saving, onThreeImageCaptureReady }: RendererPanelProps) {
  if (!result) {
    return <EmptyState />;
  }

  if (result.payload.renderer === 'geogebra_2d' || result.payload.renderer === 'geogebra_3d') {
    return (
      <div className="renderer-frame">
        <RenderMetadataBanner result={result} />
        <GeoGebraView commands={result.payload.geogebra_commands} renderer={result.payload.renderer} scene={result.scene} view={result.scene.view} onPointChange={onGeoGebraPointChange} />
        {saving && <div className="renderer-saving-overlay">Đang dựng lại hình...</div>}
      </div>
    );
  }

  if (result.payload.three_scene) {
    return (
      <div className="renderer-frame">
        <RenderMetadataBanner result={result} />
        <Suspense fallback={<div className="renderer-loading-state">Đang tải trình dựng 3D...</div>}>
          <ThreeGeometryView scene={result.payload.three_scene} interaction={threeInteraction} highlightedObjects={highlightedObjects} onImageCaptureReady={onThreeImageCaptureReady} />
        </Suspense>
        {saving && <div className="renderer-saving-overlay">Đang dựng lại hình...</div>}
      </div>
    );
  }

  return (
    <div className="empty-state">
      <div className="empty-state-content">
        <GeometryIllustration />
        <h2>Không có dữ liệu renderer phù hợp</h2>
        <p>Thử chọn GeoGebra 2D, GeoGebra 3D hoặc Three.js trong Tùy chọn nâng cao rồi dựng lại.</p>
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
        <p>Nhập đề bài, dán ảnh hoặc chọn đề mẫu để bắt đầu dựng hình.</p>
      </div>
    </div>
  );
}

function RenderMetadataBanner({ result }: { result: RenderResponse }) {
  const pendingUserReview = !result.user_confirmed && (
    result.status === 'fallback'
    || result.requires_user_confirmation
    || result.source.fallback_used
    || result.repair_report.requires_confirmation
    || result.renderer_compatibility.status === 'requires_confirmation'
  );
  if (pendingUserReview) return null;

  const degraded = !result.user_confirmed && (result.degraded || result.source.fallback_used || result.fallback_source === 'mock' || result.fallback_source === 'provider_fallback');
  const needsAttention = degraded
    || (!result.user_confirmed && result.status !== 'verified')
    || result.ai_source === 'byok'
    || result.source.kind === 'byok'
    || result.renderer_compatibility.status !== 'compatible';
  if (!needsAttention) return null;

  const warning = degraded || (!result.user_confirmed && result.requires_user_confirmation) || result.status === 'failed' || result.renderer_compatibility.status === 'incompatible';
  return (
    <div className={`renderer-metadata-banner${warning ? ' warning' : ''}`}>
      <strong>{renderMetadataTitle(result)}</strong>
      <span>{renderMetadataMessage(result)}</span>
    </div>
  );
}

function renderMetadataTitle(result: RenderResponse) {
  if (result.renderer_compatibility.status === 'incompatible') return 'Renderer không tương thích';
  if (result.status === 'fallback') return 'Kết quả fallback';
  if (result.requires_user_confirmation) return 'Cần người dùng xác nhận';
  if (result.status === 'partially_verified') return 'Kết quả kiểm chứng một phần';
  if (result.source.kind === 'byok' || result.ai_source === 'byok') return 'Đang dùng BYOK';
  return 'Trạng thái dựng hình';
}

function renderMetadataMessage(result: RenderResponse) {
  const compatibilityMessage = result.renderer_compatibility.messages[0];
  if (compatibilityMessage) return compatibilityMessage;
  if (result.source.fallback_reason) return result.source.fallback_reason;
  if (result.fallback_source === 'mock' || result.source.kind === 'mock') return 'Hệ thống đã dùng mock fallback, hình chỉ mang tính tham khảo.';
  if (result.fallback_source === 'provider_fallback' || result.source.fallback_used) return 'Hệ thống đã dùng provider fallback, nên kiểm tra lại nội dung hình.';
  if (result.source.kind === 'byok' || result.ai_source === 'byok') return 'Kết quả được sinh bằng provider OpenAI-compatible của tài khoản.';
  if (result.verification_report.status !== 'passed') return 'Một số quan hệ hình học chưa được kiểm chứng đầy đủ.';
  return 'Nguồn dựng hình có trạng thái cần chú ý.';
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
