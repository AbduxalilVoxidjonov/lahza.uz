import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import ts from 'typescript';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
const require = createRequire(import.meta.url);
const dir = mkdtempSync(join(tmpdir(), 'lahza-edit-'));
after(() => rmSync(dir, { recursive: true, force: true }));
for (const [file, output] of [['api/types', 'types'], ['lib/montage', 'montage'], ['lib/montage-edit', 'edit']]) {
  const code = ts.transpileModule(readFileSync(new URL(`../src/${file}.ts`, import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  }).outputText.replaceAll('"../api/types"', '"./types.mjs"').replaceAll('"./montage"', '"./montage.mjs"');
  writeFileSync(join(dir, `${output}.mjs`), code);
}
const { splitVideo, rippleDelete, remapTimed, record, travel } = await import(pathToFileURL(join(dir, "edit.mjs")).href);
const { timelineDuration, itemStarts } = await import(pathToFileURL(join(dir, "montage.mjs")).href);
const clip = (id, speed = 1) => ({ id, media: 'm', src_in_ms: 1000, src_out_ms: 5000, speed, fx: [], transition_in: null, user_edited: false });
const timeline = video => ({ video, media: { m: { duration_ms: 10000 } }, text: [], stickers: [], music: [{ start_ms: 0 }], captions: { words: [] } });
test('split uses speed and source offset, preserves length and metadata', () => {
  for (const speed of [0.25, 0.5, 1, 1.25, 2, 4]) {
    const tl = timeline([clip('a'), clip('b', speed)]);
    const result = splitVideo(tl, 'b', 4000 + 1000 / speed, 'right');
    assert.ok(!result.error);
    const [left, right] = result.timeline.video.slice(1);
    assert.equal(left.src_out_ms, 2000); assert.equal(right.src_in_ms, 2000);
    assert.equal(right.src_out_ms, 5000); assert.equal(right.speed, speed);
    assert.equal(right.user_edited, true); assert.equal(timelineDuration(result.timeline), timelineDuration(tl));
    assert.equal(tl.video.length, 2);
  }
});
test('split rejects edges, nonfinite values and invalid source bounds', () => {
  const tl = timeline([clip('a', 2)]);
  for (const at of [0, 2000, -1, NaN, Infinity]) assert.equal(splitVideo(tl, 'a', at, 'r').error, 'splitBounds');
  tl.media.m.duration_ms = 4000;
  assert.equal(splitVideo(tl, 'a', 1000, 'r').error, 'splitBounds');
});
test('incoming/outgoing overlap rejected; safe split preserves transitions and downstream starts', () => {
  const tl = timeline([clip('a'), clip('b'), clip('c')]);
  tl.video[1].transition_in = { dur_ms: 500 }; tl.video[2].transition_in = { dur_ms: 500 };
  for (const at of [3600, 3900, 7100, 7300]) assert.equal(splitVideo(tl, 'b', at, 'r').error, 'splitTransition');
  const result = splitVideo(tl, 'b', 5500, 'r'); assert.ok(!result.error);
  assert.deepEqual(result.timeline.video[1].transition_in, { dur_ms: 500 });
  assert.equal(result.timeline.video[2].transition_in, null);
  assert.equal(itemStarts(result.timeline).at(-1), itemStarts(tl).at(-1));
});
test('FX including freeze and unknown effects safely reject split', () => {
  for (const plugin of ['uz.lahza.speed.freeze', 'unknown']) {
    const tl = timeline([clip('a')]); tl.video[0].fx = [{ plugin, at_ms: 0, dur_ms: 100 }];
    assert.equal(splitVideo(tl, 'a', 2000, 'r').error, 'splitFx');
  }
});
test('interval remap handles before, inside, across and after deletion', () => {
  const ranges = [[0, 500], [1000, 2000], [500, 1500], [1500, 3000], [500, 3000], [2000, 3000]];
  assert.deepEqual(remapTimed(ranges.map(([start_ms, end_ms]) => ({ start_ms, end_ms })), 1000, 2000),
    [[0,500], [500,1000], [1000,2000], [500,2000], [1000,2000]].map(([start_ms,end_ms]) => ({start_ms,end_ms})));
});
test('ripple remaps all global overlay tracks, preserves music and source bounds', () => {
  const tl = timeline([clip('a', 2), clip('b')]);
  tl.text = [{ id: 'text', start_ms: 1000, end_ms: 3000 }];
  tl.stickers = [{ id: 'sticker', start_ms: 2500, end_ms: 4000 }];
  tl.captions.words = [{ text: 'gone', start_ms: 0, end_ms: 1000 }, { text: 'later', start_ms: 2500, end_ms: 3000, edited: true }];
  const result = rippleDelete(tl, 'a'); assert.ok(!result.error);
  assert.equal(result.timeline.text[0].end_ms, 1000); assert.equal(result.timeline.stickers[0].start_ms, 500);
  assert.deepEqual(result.timeline.captions.words, [{ text: 'later', start_ms: 500, end_ms: 1000, edited: true }]);
  assert.deepEqual(result.timeline.video[0], tl.video[1]); assert.equal(result.timeline.music, tl.music);
  tl.video[1].transition_in = { dur_ms: 500 };
  assert.equal(rippleDelete(tl, 'a').error, 'rippleTransition');
  assert.equal(rippleDelete(tl, 'b').error, 'rippleTransition');
});
test('history undo/redo restores full overlays/FX and branching clears redo; bounded and no-op safe', () => {
  const original = timeline([clip('a')]);
  const changed = { ...original, stickers: [{ start_ms: 1, end_ms: 2 }], captions: { words: [{ text: 'corrected' }] } };
  let h = record({ past: [], present: original, future: [] }, changed);
  h = travel(h, 'undo'); assert.deepEqual(h.present, original);
  h = travel(h, 'redo'); assert.deepEqual(h.present, changed);
  assert.equal(record(h, structuredClone(changed)), h);
  h = record(travel(h, 'undo'), { ...original, text: ['new branch'] }); assert.equal(h.future.length, 0);
  for (let i = 0; i < 110; i++) h = record(h, { ...original, text: [i] });
  assert.equal(h.past.length, 100);
});

const hotkeyCode = ts.transpileModule(readFileSync(new URL('../src/lib/hotkeys.ts', import.meta.url), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText.replace('"react"', JSON.stringify(pathToFileURL(require.resolve('react')).href));
writeFileSync(join(dir, 'hotkeys.mjs'), hotkeyCode);
const { keyName, isTypingTarget } = await import(pathToFileURL(join(dir, "hotkeys.mjs")).href);
test('Cmd/Ctrl Shift Z remains distinct; editable targets retain native undo', () => {
  for (const mod of ['metaKey', 'ctrlKey']) {
    assert.equal(keyName({ key: 'z', code: 'KeyZ', [mod]: true }), 'mod+z');
    assert.equal(keyName({ key: 'Z', code: 'KeyZ', [mod]: true, shiftKey: true }), 'mod+shift+z');
  }
  const old = globalThis.HTMLElement;
  globalThis.HTMLElement = class { constructor(editable, field) { this.isContentEditable = editable; this.field = field; } closest() { return this.field; } };
  try {
    assert.equal(isTypingTarget(new HTMLElement(true, false)), true);
    for (const field of ['input', 'textarea', 'select']) assert.equal(isTypingTarget(new HTMLElement(false, field)), true);
    assert.equal(isTypingTarget(new HTMLElement(false, null)), false);
    assert.equal(isTypingTarget(null), false);
  } finally { if (old) globalThis.HTMLElement = old; else delete globalThis.HTMLElement; }
});

const { syncSaved, acknowledgeSave } = await import(pathToFileURL(join(dir, "edit.mjs")).href);
const synced = value => ({ history: { past: [], present: value, future: [] }, baseline: value, observed: JSON.stringify(value), saving: false });
test('clean external saved change replaces history; identical refetch preserves undo/redo', () => {
  const a = timeline([clip('a')]), b = timeline([clip('b')]);
  const state = { ...synced(a), history: { past: [b], present: a, future: [b] } };
  assert.equal(syncSaved(state, structuredClone(a)), state);
  const next = syncSaved(state, b);
  assert.equal(next.baseline, b); assert.equal(next.history.present, b);
  assert.deepEqual(next.history.past, []); assert.deepEqual(next.history.future, []);
});
test('dirty work survives external change; deferred update applies when clean', () => {
  const a = timeline([clip('a')]), b = timeline([clip('b')]), c = timeline([clip('c')]);
  const state = { ...synced(a), history: record(synced(a).history, b) };
  assert.equal(syncSaved(state, c), state);
  const clean = { ...state, history: travel(state.history, 'undo') };
  assert.equal(syncSaved(clean, c).history.present, c);
});
test('own normalized save preserves undo/redo and uses server baseline', () => {
  const a = timeline([clip('a')]), b = timeline([clip('b')]);
  const normalized = { ...b, color: null };
  const state = { ...synced(a), history: record(synced(a).history, b), saving: true };
  for (const beforeAck of [state, syncSaved(state, normalized)]) {
    const saved = acknowledgeSave(beforeAck, b, normalized);
    assert.equal(saved.baseline, normalized); assert.equal(saved.history.present, normalized);
    assert.deepEqual(saved.history.past, [a]);
    const echoed = syncSaved(saved, structuredClone(normalized));
    assert.equal(echoed.history, saved.history);
    const undone = travel(echoed.history, 'undo'); assert.equal(undone.present, a);
    assert.equal(travel(undone, 'redo').present, normalized);
  }
});
test('old query response during inflight save is consumed even if editor is clean', () => {
  const a = timeline([clip('a')]), b = timeline([clip('b')]), stale = timeline([clip('stale')]);
  let state = { ...synced(a), saving: true };
  state = syncSaved(state, stale);
  assert.equal(state.history.present, a);
  state = acknowledgeSave(state, a, b);
  assert.equal(syncSaved(state, stale), state);
  assert.equal(state.history.present, b);
});
test('edits made during save survive normalized response and failed save retains baseline', () => {
  const a = timeline([clip('a')]), b = timeline([clip('b')]), c = timeline([clip('c')]);
  const state = { ...synced(a), history: record(record(synced(a).history, b), c), saving: true };
  const saved = acknowledgeSave(state, b, { ...b, color: null });
  assert.equal(saved.history, state.history); assert.equal(saved.history.present, c);
  assert.notDeepEqual(saved.history.present, saved.baseline);
  const failed = { ...state, saving: false };
  assert.equal(syncSaved(failed, a), failed); assert.equal(failed.baseline, a);
});
