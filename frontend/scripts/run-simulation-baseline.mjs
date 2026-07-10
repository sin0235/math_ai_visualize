/**
 * Phase 0 baseline runner without full Vitest install.
 * Prefers tsx / vite-node. Fallback pure-JS checks are diagnostics only —
 * preferred runner failure always exits non-zero so CI cannot go false-green.
 */
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const entry = path.join(root, 'src/simulation/math/baseline.test.ts');

const runners = [
  ['npx', ['--yes', 'tsx', entry]],
  ['npx', ['--yes', 'vite-node', entry]],
];

let lastError = '';
for (const [cmd, args] of runners) {
  const result = spawnSync(cmd, args, {
    cwd: root,
    encoding: 'utf8',
    env: { ...process.env, FORCE_COLOR: '0' },
    shell: process.platform === 'win32',
  });
  if (result.status === 0) {
    process.stdout.write(result.stdout || '');
    process.stderr.write(result.stderr || '');
    process.exit(0);
  }
  lastError = `${cmd} ${args.join(' ')}\n${result.stderr || result.stdout || result.error || ''}`;
}

// Fallback diagnostics (local only). Never treat as CI success.
function assert(c, m) {
  if (!c) throw new Error(m);
}

function integrate(fn, a, b, intervals = 800) {
  const n = Math.max(2, Math.floor(intervals / 2) * 2);
  const h = (b - a) / n;
  let sum = fn(a) + fn(b);
  for (let i = 1; i < n; i += 1) sum += fn(a + i * h) * (i % 2 === 0 ? 2 : 4);
  return (sum * h) / 3;
}

try {
  const half = integrate((x) => x, 0, 1);
  assert(Math.abs(half - 0.5) < 1e-4, `integrate failed ${half}`);
  assert(Math.abs(Math.sin(Math.PI / 6) ** 2 + Math.cos(Math.PI / 6) ** 2 - 1) < 1e-10, 'identity');
  console.log('Simulation baseline fallback diagnostics OK (install tsx for full suite)');
} catch (error) {
  console.error('Fallback diagnostics failed:', error);
}

console.error('Full suite runner failed (exit 1):\n', lastError);
process.exit(1);
