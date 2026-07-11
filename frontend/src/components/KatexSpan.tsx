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
  const normalizedTex = normalizeLatexForKatex(tex);
  const plainText = latexTextFallback(normalizedTex);
  const html = useMemo(() => {
    if (plainText || !looksLikeMathExpression(normalizedTex)) return null;
    const rendered = renderKatex(normalizedTex, display);
    if (rendered) return rendered;
    const fallback = sympyToLatex(normalizedTex);
    return fallback !== normalizedTex ? renderKatex(fallback, display) : null;
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

export function MixedTextRenderer({ text, className }: { text: string; className?: string }) {
  if (!text.includes('$') && !text.includes('\\(') && !text.includes('\\[')) {
    // If it is purely math (no Vietnamese chars) and contains math symbols, treat it as math
    if (/^[^À-ỹ]+$/.test(text) && /\\[a-zA-Z]+|[=^_{}]/.test(text)) {
      return <KatexSpan tex={text} className={className} />;
    }
    return <span className={className}>{text}</span>;
  }
  
  const parts = text.split(/(\$\$[\s\S]+?\$\$|\$[\s\S]+?\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\))/g);
  return (
    <span className={className}>
      {parts.map((part, index) => {
        if (part.startsWith('$$') && part.endsWith('$$')) {
          return <KatexSpan key={index} tex={part.slice(2, -2)} display className="display-math" />;
        }
        if (part.startsWith('$') && part.endsWith('$')) {
          return <KatexSpan key={index} tex={part.slice(1, -1)} display={false} className="inline-math" />;
        }
        if (part.startsWith('\\[') && part.endsWith('\\]')) {
          return <KatexSpan key={index} tex={part.slice(2, -2)} display className="display-math" />;
        }
        if (part.startsWith('\\(') && part.endsWith('\\)')) {
          return <KatexSpan key={index} tex={part.slice(2, -2)} display={false} className="inline-math" />;
        }
        return <span key={index}>{part}</span>;
      })}
    </span>
  );
}

function renderKatex(value: string, display: boolean): string | null {
  try {
    const html = katex.renderToString(value, {
      throwOnError: false,
      displayMode: display,
      output: 'html',
      strict: false,
    });
    return html.includes('katex-error') ? null : html;
  } catch {
    return null;
  }
}

export function normalizeLatexForKatex(value: string): string {
  let tex = normalizeKatexInput(value).replace(/[​-‍﻿]/g, '').trim();
  if (!tex) return '';
  tex = stripMathDelimiters(tex)
    .replace(/^\s*(Công thức|Thế số|Kết quả|Formula|Substitution|Result)\s*:\s*/i, '')
    .replace(/−/g, '-')
    .replace(/[×✕]/g, '\\times ')
    .replace(/[·∙]/g, '\\cdot ')
    .replace(/≤/g, '\\le ')
    .replace(/≥/g, '\\ge ')
    .replace(/≠/g, '\\ne ')
    .replace(/≈/g, '\\approx ')
    .replace(/∞/g, '\\infty ')
    .replace(/π/g, '\\pi ')
    .replace(/√\s*\(([^)]+)\)/g, '\\sqrt{$1}')
    .replace(/√\s*([^\s+\-*/^=]+)/g, '\\sqrt{$1}')
    .replace(/∥\s*([^∥]+?)\s*∥/g, '\\left\\|$1\\right\\|')
    .replace(/(^|[^\\])\b(d?frac)\s*\{/g, '$1\\frac{')
    .replace(/(^|[^\\])\b(sqrt)\s*\{/g, '$1\\sqrt{')
    .replace(/(^|[^\\])\b(sin|cos|tan|ln|log)\s*(?=\()/g, '$1\\$2');

  const absFracMatch = tex.match(/^\s*([0-9]+(?:\.[0-9]+)?)\s*[|∣]\s*([^|∣]+)\s*[|∣]\s*$/);
  if (absFracMatch && !tex.includes('\\frac')) {
    tex = `\\frac{\\left|${absFracMatch[2].trim()}\\right|}{${absFracMatch[1]}}`;
  }
  return tex.replace(/\s{2,}/g, ' ').trim();
}

function stripMathDelimiters(value: string): string {
  const pairs: Array<[RegExp, number]> = [
    [/^\$\$([\s\S]+)\$\$$/, 1],
    [/^\$([^$]+)\$$/, 1],
    [/^\\\(([\s\S]+)\\\)$/, 1],
    [/^\\\[([\s\S]+)\\\]$/, 1],
  ];
  for (const [pattern, group] of pairs) {
    const match = value.match(pattern);
    if (match) return match[group].trim();
  }
  return value;
}

function looksLikeMathExpression(value: string): boolean {
  if (!value) return false;
  if (/\\[a-zA-Z]+|[=^_{}]|\d|[+\-*/<>]|\\times|\\cdot/.test(value)) return true;
  return !/[À-ỹ]/.test(value) && value.length <= 32;
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
    .replace(/\bAbs\(([^)]+)\)/g, '\\left|$1\\right|')
    .replace(/\*/g, ' \\cdot ');
  s = s
    .replace(/-?\boo\b/g, (m) => (m.startsWith('-') ? '-\\infty' : '\\infty'))
    .replace(/\bzoo\b/g, '\\infty')
    .replace(/\bnan\b/gi, 'không xác định');
  return normalizeLatexForKatex(s);
}
