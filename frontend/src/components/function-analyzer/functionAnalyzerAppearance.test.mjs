import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const css = readFileSync(new URL('./function-analyzer.css', import.meta.url), 'utf8');

function ruleBody(selector) {
  const start = css.indexOf(`${selector} {`);
  assert.notEqual(start, -1, `Thiếu rule ${selector}`);
  const bodyStart = css.indexOf('{', start) + 1;
  let depth = 1;
  for (let index = bodyStart; index < css.length; index += 1) {
    if (css[index] === '{') depth += 1;
    if (css[index] === '}') depth -= 1;
    if (depth === 0) return css.slice(bodyStart, index);
  }
  throw new Error(`Rule ${selector} chưa đóng ngoặc`);
}

const panel = ruleBody('.fa2-panel');
assert.match(panel, /overflow-x:\s*clip/);
assert.match(panel, /background:\s*var\(--surface\)/);
assert.doesNotMatch(css, /linear-gradient\(/, 'Analyzer không được dùng lưới hoặc gradient trang trí ngoài đồ thị');

const analyzerShell = ruleBody('.app-shell:has(.fa2-panel)');
assert.match(analyzerShell, /background:\s*var\(--surface\)/);

const resultShell = ruleBody('.fa2-result-shell');
assert.match(resultShell, /grid-template-columns:\s*minmax\(0,\s*1\.52fr\)\s+minmax\(300px,\s*0\.68fr\)/);
assert.match(resultShell, /gap:\s*0/);
assert.match(resultShell, /overflow:\s*clip/);
assert.match(resultShell, /border:\s*1px solid var\(--line\)/);
assert.match(resultShell, /background:\s*var\(--paper\)/);

const graphColumn = ruleBody('.fa2-graph-column');
assert.match(graphColumn, /border-right:\s*1px solid var\(--line\)/);

const quickRows = ruleBody('.fa2-quick-rows');
assert.match(quickRows, /grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/);
assert.match(quickRows, /border-top:\s*1px solid var\(--line\)/);
assert.match(quickRows, /border-bottom:\s*1px solid var\(--line\)/);

const summaryCard = ruleBody('.fa2-quick-rows .fa2-summary-card');
assert.match(summaryCard, /border:\s*0/);
assert.match(summaryCard, /background:\s*transparent/);

const rootSummary = ruleBody('.fa2-quick-card > .fa2-root-summary');
assert.match(rootSummary, /border:\s*0/);
assert.match(rootSummary, /background:\s*transparent/);

const capabilitySummary = ruleBody('.fa2-analysis-column .math-capability-summary');
assert.match(capabilitySummary, /border-top:\s*1px solid var\(--line\)/);
assert.match(capabilitySummary, /border-radius:\s*0/);
assert.match(capabilitySummary, /background:\s*transparent/);

assert.match(css, /@media \(max-width:\s*900px\)[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)/);
assert.match(css, /@media \(max-width:\s*680px\)[\s\S]*?min-height:\s*44px/);
assert.match(css, /@media \(prefers-reduced-motion:\s*reduce\)/);

const screenReaderTable = ruleBody('.fa2-panel table.sr-only');
assert.match(screenReaderTable, /display:\s*block/);
assert.match(screenReaderTable, /max-width:\s*1px/);
assert.match(screenReaderTable, /max-height:\s*1px/);

const variationTimelineItem = ruleBody('.fa2-analysis-column .bbt-timeline-item');
assert.match(variationTimelineItem, /border:\s*0/);
assert.match(variationTimelineItem, /border-radius:\s*0/);
assert.match(variationTimelineItem, /background:\s*transparent/);

console.log('Function Analyzer appearance tests passed.');
