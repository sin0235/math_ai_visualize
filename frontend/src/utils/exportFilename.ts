import type { MathScene } from '../types/scene';

export type ExportFormatKey = 'png' | 'jpg' | 'svg' | 'katex-html' | 'tikz' | 'pdf' | 'ggb';

const FORMAT_EXT: Record<ExportFormatKey, string> = {
  png: 'png',
  jpg: 'jpg',
  svg: 'svg',
  'katex-html': 'html',
  tikz: 'tex',
  pdf: 'pdf',
  ggb: 'ggb',
};

/** Loại bỏ ký tự không hợp lệ trên Windows/macOS/Linux và rút gọn. */
function sanitizeSegment(raw: string, maxLen: number): string {
  let s = raw
    .replace(/[\u0000-\u001f\u007f]/g, '')
    .replace(/[/\\?%*:|"<>]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  if (s.length > maxLen) s = s.slice(0, maxLen).trim();
  return s.replace(/\.+$/g, '').trim();
}

function stampCompact(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

function topicSegment(topic: string): string {
  const t = sanitizeSegment(topic.replace(/_/g, ' '), 40).replace(/\s+/g, '-').toLowerCase();
  return t || 'bai';
}

function problemSnippet(problemText: string): string {
  const oneLine = problemText.replace(/\s+/g, ' ').trim();
  const cut = sanitizeSegment(oneLine, 44);
  return cut.replace(/\s+/g, '-').toLowerCase();
}

/**
 * Tên file tải xuống: math-renderer-<topic>-<đoạn đề>-<YYYYMMDD-HHmmss>.<ext>
 */
export function buildExportFilename(scene: MathScene, format: ExportFormatKey): string {
  const ext = FORMAT_EXT[format];
  const topic = topicSegment(scene.topic || '');
  const snippet = problemSnippet(scene.problem_text || '');
  const stamp = stampCompact();

  const pieces = ['math-renderer', topic];
  if (snippet) pieces.push(snippet);
  pieces.push(stamp);

  let base = pieces.join('-').replace(/-+/g, '-').replace(/^-|-$/g, '');
  if (base.length > 180) base = base.slice(0, 180).replace(/-+$/, '');

  return `${base || `math-renderer-${stamp}`}.${ext}`;
}
