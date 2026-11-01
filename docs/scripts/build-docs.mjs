import { spawnSync } from 'node:child_process';
import { cp, mkdir, mkdtemp, realpath, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildLanding } from './build-landing.mjs';

const docs = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const output = resolve(process.argv[2] || resolve(docs, 'html'));
if (output === docs) throw new Error('The build output cannot replace the documentation source.');

// Canonical paths also satisfy Diplodoc's scope checks on macOS (/var → /private/var).
const staging = await mkdtemp(join(await realpath(tmpdir()), 'manytask-docs-'));
const input = join(staging, 'input');
const rendered = join(staging, 'output');

try {
  // A previous html/ build can otherwise be copied over freshly rendered pages.
  // Keep generated output and the separately packaged landing source out of YFM.
  await cp(docs, input, {
    recursive: true,
    filter: (source) => source !== output
      && !['html', 'landing', 'scripts'].includes(relative(docs, source).split(sep)[0]),
  });
  const result = spawnSync('yfm', ['-i', input, '-o', rendered, '--allow-custom-resources'], { stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`Diplodoc build failed (${result.status}).`);

  await buildLanding(rendered);
  await mkdir(output, { recursive: true });
  await cp(rendered, output, { recursive: true, force: true });
  console.log(`Documentation and standalone landing page built in ${output}`);
} finally {
  await rm(staging, { recursive: true, force: true });
}
