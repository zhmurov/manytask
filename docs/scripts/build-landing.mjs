import { cp, mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const docs = resolve(dirname(fileURLToPath(import.meta.url)), '..');

/** @param {string} output @returns {Promise<void>} */
export async function buildLanding(output) {
  await mkdir(output, { recursive: true });
  await cp(resolve(docs, 'landing/index.html'), resolve(output, 'index.html'));
  await cp(resolve(docs, 'landing/assets'), resolve(output, 'landing-assets'), { recursive: true });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const output = resolve(process.argv[2] || resolve(docs, 'html'));
  await buildLanding(output);
  console.log(`Standalone landing page built in ${output}`);
}
