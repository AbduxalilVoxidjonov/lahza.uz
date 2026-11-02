import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

// Partiyaviy tahlil navbati (PRO-5): sof UI mantig'i va i18n lug'atlari.
const dir = mkdtempSync(join(tmpdir(), 'lahza-batch-'));
after(() => rmSync(dir, { recursive: true, force: true }));
for (const [file, output] of [['lib/batch-queue', 'queue'], ['i18n/batch/index', 'i18n']]) {
  const code = ts.transpileModule(readFileSync(new URL(`../src/${file}.ts`, import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  }).outputText;
  writeFileSync(join(dir, `${output}.mjs`), code);
}
const q = await import(pathToFileURL(join(dir, 'queue.mjs')).href);
const { batchDictionaries, fmt } = await import(pathToFileURL(join(dir, 'i18n.mjs')).href);

const item = (id, status, position, extra = {}) => ({
  id, project_id: 'p', episode_id: null, path: `/v/${id}.mp4`, title: null, options: {}, position, status,
  progress: 0, stage: null, error: null, job_id: null, created_at: '', started_at: null, finished_at: null, ...extra,
});

test('parsePathList: bo\'sh qatorlar, qo\'shtirnoq va takrorlar olib tashlanadi', () => {
  assert.deepEqual(q.parsePathList(' /a.mp4 \n\n"/b c.mp4"\r\n/a.mp4\n\'/d.mov\''), ['/a.mp4', '/b c.mp4', '/d.mov']);
  assert.deepEqual(q.parsePathList('   \n'), []);
  assert.deepEqual(q.mergePaths(['/a'], ['/b', '/a', '/b', '/c']), ['/a', '/b', '/c']);
});

test('moveQueued: faqat kutayotganlar tartiblanadi; chegarada null', () => {
  const items = [item('r', 'running', 1), item('a', 'queued', 4), item('b', 'queued', 2), item('c', 'queued', 3), item('d', 'done', 0)];
  assert.deepEqual(q.moveQueued(items, 'c', -1), ['c', 'b', 'a']);
  assert.deepEqual(q.moveQueued(items, 'b', 1), ['c', 'b', 'a']);
  assert.deepEqual(q.moveQueued(items, 'a', 'top'), ['a', 'b', 'c']);
  assert.equal(q.moveQueued(items, 'b', -1), null);
  assert.equal(q.moveQueued(items, 'b', 'top'), null);
  assert.equal(q.moveQueued(items, 'a', 1), null);
  assert.equal(q.moveQueued(items, 'r', 1), null);
});

test('holatga qarab amallar', () => {
  assert.ok(q.canCancel('queued') && q.canCancel('running') && !q.canCancel('done'));
  assert.ok(!q.canRemove('running') && q.canRemove('queued') && q.canRemove('failed'));
  assert.ok(q.canRetry('failed') && q.canRetry('cancelled') && !q.canRetry('done') && !q.canRetry('queued'));
});

test('withLiveJob va summarize: jonli progress va umumiy ulush', () => {
  const run = item('r', 'running', 1, { job_id: 'j1', progress: 0.1 });
  const merged = q.withLiveJob(run, { id: 'j1', progress: 0.5, stage: 'asr' });
  assert.equal(merged.progress, 0.5);
  assert.equal(merged.stage, 'asr');
  assert.equal(q.withLiveJob(run, { id: 'boshqa', progress: 0.9, stage: 'x' }), run);
  assert.equal(q.withLiveJob(item('d', 'done', 2, { job_id: 'j1' }), { id: 'j1', progress: 0.2, stage: 'x' }).progress, 0);
  const s = q.summarize([merged, item('a', 'queued', 2), item('d', 'done', 3), item('f', 'failed', 4)]);
  assert.deepEqual({ ...s, progress: undefined }, { total: 4, queued: 1, running: 1, done: 1, failed: 1, cancelled: 0, progress: undefined });
  assert.equal(s.progress, (0.5 + 0 + 1 + 1) / 4);
  assert.equal(q.summarize([]).progress, 0);
});

test('i18n: har til lug\'atida bir xil kalitlar va bo\'sh bo\'lmagan matn', () => {
  const keys = Object.keys(batchDictionaries.uz).sort();
  for (const [locale, dict] of Object.entries(batchDictionaries)) {
    assert.deepEqual(Object.keys(dict).sort(), keys, locale);
    for (const [k, v] of Object.entries(dict)) assert.ok(v.trim(), `${locale}.${k}`);
    for (const s of ['queued', 'running', 'done', 'failed', 'cancelled']) assert.ok(dict[s], `${locale}.${s}`);
  }
  assert.equal(fmt(batchDictionaries.uz.summary, { done: 2, total: 3, failed: 1 }), 'Tayyor: 2/3 · xato: 1');
});
