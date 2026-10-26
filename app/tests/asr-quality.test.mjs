import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

// Transkripsiya sifati (Sozlamalar): Tez (base) / Aniq (small) tanlovi mantig'i va 4 tildagi matnlar.
const dir = mkdtempSync(join(tmpdir(), 'lahza-asrq-'));
after(() => rmSync(dir, { recursive: true, force: true }));
const src = readFileSync(new URL('../src/lib/asr-quality.ts', import.meta.url), 'utf8');
writeFileSync(join(dir, 'q.mjs'), ts.transpileModule(src, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText);
const q = await import(pathToFileURL(join(dir, 'q.mjs')).href);

const status = (over = {}) => ({
  mode: 'fast', current_model_id: 'custom:navai-whisper-base-uzbek',
  fast: { installed: true },
  accurate: { installed: false, download_bytes: 251_966_951, download_available: false },
  ...over,
});

test('tanlov harakati: o\'rnatilmagan Aniq - taklif, o\'rnatilgan - darhol almashish', () => {
  assert.equal(q.chooseAction(status(), 'fast'), 'none');
  assert.equal(q.chooseAction(status(), 'accurate'), 'offer');
  const both = status({ accurate: { installed: true, download_bytes: 0, download_available: false } });
  assert.equal(q.chooseAction(both, 'accurate'), 'switch');
  assert.equal(q.chooseAction({ ...both, mode: 'accurate' }, 'fast'), 'switch');
  assert.equal(q.chooseAction(status({ mode: 'none', fast: { installed: false } }), 'fast'), 'missing');
});

test('boshqa ASR yoki ASR yo\'q bo\'lsa radio tanlanmaydi', () => {
  assert.equal(q.selectedMode(status()), 'fast');
  assert.equal(q.selectedMode(status({ mode: 'accurate' })), 'accurate');
  assert.equal(q.selectedMode(status({ mode: 'custom' })), null);
  assert.equal(q.selectedMode(status({ mode: 'none' })), null);
});

test('yuklash hajmi ~240 MB ko\'rinishida', () => {
  assert.equal(q.approxMb(251_966_951), '~240 MB');
  assert.equal(q.approxMb(1), '~10 MB');
});

test('davom etayotgan asr-quality vazifasi topiladi, tugaganlari va boshqalari - yo\'q', () => {
  const jobs = {
    a: { id: 'a', status: 'done', meta: { op: 'asr-quality' } },
    b: { id: 'b', status: 'running', meta: { op: 'setup' } },
    c: { id: 'c', status: 'running', meta: { op: 'asr-quality' } },
  };
  assert.equal(q.activeQualityJob(jobs)?.id, 'c');
  assert.equal(q.activeQualityJob({ a: jobs.a, b: jobs.b }), undefined);
  assert.equal(q.isActive({ id: 'x', status: 'queued', meta: {} }), true);
});

test('matnlar 4 tilda: sekinlik va hajm o\'rni bor', () => {
  for (const file of ['uz', 'uz-Cyrl', 'ru', 'en']) {
    const text = readFileSync(new URL(`../src/i18n/${file}.ts`, import.meta.url), 'utf8');
    const hint = text.match(/"asrq\.accurateHint": "([^"]+)"/)?.[1];
    assert.ok(hint, file);
    assert.match(hint, /2[.,]5/);
    assert.match(hint, /\{size\}/);
    for (const key of ['asrq.title', 'asrq.fast', 'asrq.offer', 'asrq.download', 'asrq.importPack', 'asrq.oldProjects', 'stage.download']) {
      assert.ok(text.includes(`"${key}":`), `${file}: ${key}`);
    }
  }
});
