import { readFileSync } from 'node:fs';
import { registerHooks } from 'node:module';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

import ts from 'typescript';

const testFile = process.argv[2];
if (!testFile) throw new Error('Thiếu đường dẫn test TypeScript.');

registerHooks({
  load(url, context, nextLoad) {
    if (!url.endsWith('.ts') && !url.endsWith('.tsx')) return nextLoad(url, context);
    const source = readFileSync(new URL(url), 'utf8');
    return {
      format: 'module',
      shortCircuit: true,
      source: ts.transpileModule(source, {
        compilerOptions: {
          jsx: ts.JsxEmit.ReactJSX,
          module: ts.ModuleKind.ESNext,
          target: ts.ScriptTarget.ES2022,
        },
      }).outputText,
    };
  },
});

await import(pathToFileURL(resolve(testFile)).href);