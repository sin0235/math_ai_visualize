/**
 * Lightweight KaTeX renderer — renders a LaTeX string inline.
 * Falls back to raw text if KaTeX fails or expression is not LaTeX.
 */
import katex from 'katex';
import 'katex/dist/katex.min.css';
import { useMemo } from 'react';

interface KatexSpanProps {
  tex: string;
  display?: boolean;
  className?: string;
}

export function KatexSpan({ tex, display = false, className }: KatexSpanProps) {
  const normalizedTex = normalizeKatexInput(tex);
  const plainText = latexTextFallback(normalizedTex);
  const html = useMemo(() => {
    if (plainText) return null;
    try {
      return katex.renderToString(normalizedTex, {
        throwOnError: false,
        displayMode: display,
        output: 'html',
        strict: false,
      });
    } catch {
      return null;
    }
  }, [normalizedTex, display, plainText]);

  if (!html) {
    return <span className={className}>{plainText || normalizedTex}</span>;
  }

  return (
    <span
      className={className}
      // biome-ignore lint/security/noDangerouslySetInnerHtml: trusted KaTeX output
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function normalizeKatexInput(value: string): string {
  if (!/<\/?[a-z][\s\S]*>/i.test(value)) return value;
  const doc = new DOMParser().parseFromString(value, 'text/html');
  return doc.body.textContent?.replace(/\s+/g, ' ').trim() || '';
}

function latexTextFallback(value: string): string | null {
  const match = value.match(/^\\text\{([\s\S]+)\}$/);
  if (!match) return null;
  const text = match[1].replace(/\\,/g, ' ').replace(/\\ /g, ' ').replace(/\s+/g, ' ').trim();
  return text.length > 18 || /[À-ỹ]/.test(text) ? text : null;
}

/** Convert a SymPy-style string to a rough LaTeX string for display */
export function sympyToLatex(expr: string): string {
  let s = expr
    .replace(/\*\*/g, '^')
    .replace(/\bsqrt\(([^)]+)\)/g, '\\sqrt{$1}')
    .replace(/\blog\(([^)]+)\)/g, '\\ln($1)')
    .replace(/\bsin\(([^)]+)\)/g, '\\sin($1)')
    .replace(/\bcos\(([^)]+)\)/g, '\\cos($1)')
    .replace(/\btan\(([^)]+)\)/g, '\\tan($1)')
    .replace(/\*/g, ' \\cdot ');
  // oo vô cực SymPy — chỉ token độc lập (\b), không đụng floor, root, zoo…
  s = s.replace(/-?\boo\b/g, (m) => (m.startsWith('-') ? '-\\infty' : '\\infty'));
  return s;
}
