import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
// PRO-4: subtitr yozuvi (lotin/kirill) - standart qiymat, agent tekshiruvi va i18n kalitlari.
const dir = mkdtempSync(join(tmpdir(), 'lahza-script-'));
after(() => rmSync(dir, { recursive: true, force: true }));
for (const [file, name] of [['lib/editing-agent', 'agent'], ['api/types', 'types']]) {
  writeFileSync(join(dir, `${name}.mjs`), ts.transpileModule(readFileSync(new URL(`../src/${file}.ts`, import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  }).outputText);
}
const { isAgentTimeline } = await import(pathToFileURL(join(dir, 'agent.mjs')));
const { DEFAULT_STYLE } = await import(pathToFileURL(join(dir, 'types.mjs')));
const timeline = style => ({ schema: 'lahza.timeline/1', format: { aspect: '9:16', w: 1080, h: 1920, fps: 30, audio_hz: 48000 }, media: {}, video: [], text: [], music: [], captions: { enabled: true, style, words: [] }, brand: { logo_position: 'top_left', logo_opacity: 1 }, audio: { source_gain_db: 0, fade_ms: 0 }, provenance: { notes: [] } });
test('default style keeps Latin script (existing behaviour unchanged)', () => {
  assert.equal(DEFAULT_STYLE.script, 'latin');
});
test('agent timeline accepts latin/cyrillic or missing script and rejects unknown values', () => {
  const { script: _omit, ...legacy } = DEFAULT_STYLE;
  assert.equal(isAgentTimeline(timeline(legacy)), true);
  assert.equal(isAgentTimeline(timeline({ ...DEFAULT_STYLE, script: 'cyrillic' })), true);
  assert.equal(isAgentTimeline(timeline({ ...DEFAULT_STYLE, script: 'arab' })), false);
});
test('every locale names the script selector', () => {
  for (const loc of ['uz', 'uz-Cyrl', 'ru', 'en']) {
    const src = readFileSync(new URL(`../src/i18n/${loc}.ts`, import.meta.url), 'utf8');
    for (const key of ['style.script', 'script.latin', 'script.cyrillic']) assert.match(src, new RegExp(`"${key.replace('.', '\\.')}":`), `${loc}: ${key}`);
  }
  assert.match(readFileSync(new URL('../src/i18n/uz.ts', import.meta.url), 'utf8'), /"script\.cyrillic": "Кирилл"/);
});
