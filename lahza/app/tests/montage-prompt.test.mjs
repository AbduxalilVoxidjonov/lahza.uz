import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
const dir = mkdtempSync(join(tmpdir(), 'lahza-prompt-'));
after(() => rmSync(dir, { recursive: true, force: true }));
for (const [file, output] of [['api/types','types'], ['lib/montage','montage'], ['lib/export-profiles','export-profiles'], ['lib/montage-edit','edit'], ['lib/montage-prompt','prompt']]) {
  const code = ts.transpileModule(readFileSync(new URL(`../src/${file}.ts`, import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  }).outputText.replaceAll('"../api/types"','"./types.mjs"').replaceAll('"./montage"','"./montage.mjs"').replaceAll('"./export-profiles"','"./export-profiles.mjs"');
  writeFileSync(join(dir, `${output}.mjs`), code);
}
const load = name => import(pathToFileURL(join(dir, `${name}.mjs`)).href);
const { planMontagePrompt: plan, applyMontagePrompt: apply, promptPlanIsCurrent } = await load('prompt');
const { record, travel } = await load('edit');
const { DEFAULT_STYLE } = await load('types');
const { timelineDuration } = await load('montage');
const selected = { type: 'video', id: 'b' };
const timeline = () => ({
  format: { aspect: '16:9', w: 1920, h: 1080, fps: 24, audio_hz: 48000 },
  video: [{ id: 'a', media: 'm', src_in_ms: 0, src_out_ms: 2000, speed: 1, fx: [] },
    { id: 'b', media: 'm', src_in_ms: 1000, src_out_ms: 11000, speed: 2, fx: [], user_edited: false }],
  media: { m: { duration_ms: 12000 } }, text: [], stickers: [{ id: 'keep', start_ms: 500, end_ms: 3000 }], music: [],
  captions: { enabled: false, style: structuredClone(DEFAULT_STYLE), words: [{ text: 'actual', start_ms: 500, end_ms: 1000 }] },
});
const profiles = ['instagram_reels','youtube_shorts','youtube_video'].map(id => ({ id, name: id,
  recommended_format: { aspect: id === 'youtube_video' ? '16:9' : '9:16', w: id === 'youtube_video' ? 1920 : 1080, h: id === 'youtube_video' ? 1080 : 1920, fps: 30 } }));
const parse = (input, tl = timeline(), selection = selected) => plan(input, tl, selection, profiles);
const deepFreeze = value => { if (value && typeof value === 'object') { Object.freeze(value); for (const v of Object.values(value)) deepFreeze(v); } return value; };
test('English and Uzbek formats use supplied profiles without trimming or modifying source', () => {
  for (const [command, id] of [['reels format','instagram_reels'],['shorts formati','youtube_shorts'],['videoni youtube formatida qil','youtube_video']]) {
    const tl = deepFreeze(timeline()); const p = parse(command, tl);
    assert.deepEqual(p.issues, []); const after = apply(p, tl, selected);
    assert.equal(after.target_platform, id); assert.equal(after.format.fps, 30);
    assert.deepEqual(after.video, tl.video); assert.deepEqual(after.stickers, tl.stickers);
    assert.equal(timelineDuration(after), timelineDuration(tl));
  }
});
test('normal Uzbek multi-clause example uses selected clip local time and explicit default hold', () => {
  const tl = timeline();
  const p = parse('videoni Reels formatida qil; captionni kattalashtir; 3-soniyada stop-kadr qo‘y', tl);
  assert.deepEqual(p.issues, []); assert.equal(p.changes.length, 3);
  const fx = p.after.video[1].fx[0];
  assert.deepEqual(fx, { plugin: 'uz.lahza.speed.freeze', at_ms: 3000, dur_ms: 1000, params: { dur_ms: 1000 }, source: 'qolda' });
  assert.ok(p.changes[2].detail.includes('source 7000 ms')); // src_in 1000 + local 3000 * speed 2
  assert.equal(timelineDuration(p.after), timelineDuration(tl));
  assert.equal(p.after.video[0].fx.length, 0);
});
test('explicit English/Uzbek freeze durations, decimal commas and boundaries', () => {
  for (const input of ['freeze selected at 0,5s for 0,5s', 'tanlangan klipning 0.5-soniyasida 0.5 soniya stop-kadr']) {
    const p = parse(input); assert.deepEqual(p.issues, []);
    assert.equal(p.after.video[1].fx[0].at_ms, 500); assert.equal(p.after.video[1].fx[0].dur_ms, 500);
  }
  for (const input of ['freeze selected at 5s for 1s','freeze selected at 4.5s for 1s','freeze selected at 0s for 0.01s','freeze selected at 0s for 6s']) {
    const p = parse(input); assert.ok(p.issues.some(x => x.code === 'promptBounds')); assert.equal(apply(p, timeline(), selected), null);
  }
});
test('invalid source bounds, selection and overlapping freeze reject application', () => {
  for (const selection of [null, { type: 'text', id: 'b' }, { type: 'video', id: 'missing' }]) assert.ok(parse('3-soniyada stop-kadr qo‘y', timeline(), selection).issues.some(x => x.code === 'promptSelectVideo'));
  for (const patch of [{ src_out_ms: 13000 }, { src_in_ms: -1 }, { speed: 0 }, { src_out_ms: NaN }]) {
    const tl = timeline(); Object.assign(tl.video[1], patch);
    assert.ok(parse('freeze selected at 1s for 1s', tl).issues.some(x => x.code === 'promptBounds'));
  }
  const tl = timeline(); tl.video[1].fx = [{ plugin: 'uz.lahza.speed.freeze', at_ms: 2000, dur_ms: 2000, params: {} }];
  assert.ok(parse('3-soniyada stop-kadr qo‘y', tl).issues.some(x => x.code === 'promptBounds'));
});
test('caption toggles/sizing retain actual words and imported text; font stays in 24..200', () => {
  const tl = timeline(); tl.text = [{ id: 'imported', start_ms: 100, end_ms: 600, text: 'SRT' }];
  const p = parse('subtitr yoq, captionni kattalashtir', tl);
  assert.deepEqual(p.issues, []); assert.equal(p.after.captions.enabled, true); assert.equal(p.after.captions.style.font_size, 80);
  assert.deepEqual(p.after.captions.words, tl.captions.words); assert.deepEqual(p.after.text, tl.text);
  assert.equal(parse('captions off', p.after).after.captions.enabled, false);
  tl.captions.style.font_size = 198;
  assert.equal(parse('captions larger', tl).after.captions.style.font_size, 200);
  tl.captions.style.font_size = 25;
  assert.equal(parse('captions smaller', tl).after.captions.style.font_size, 24);
  tl.captions.style.font_size = 24;
  assert.ok(parse('captions smaller', tl).issues.length);
});
test('separators outside quotes preserve quoted data and decimal timing; captions use montage time', () => {
  const p = parse('warm color, captions on keyin caption "Hello, keyin; <script>" 0,5s–1,5s');
  assert.deepEqual(p.issues, []); assert.equal(p.changes.length, 3);
  assert.equal(p.after.text[0].text, 'Hello, keyin; <script>');
  assert.equal(p.after.text[0].start_ms, 500); assert.equal(p.after.text[0].end_ms, 1500);
  assert.equal(p.after.text[0].animation, 'none');
  assert.ok(parse('caption "too late" 6s–9s').issues.length);
});
test('only verified warm/film presets and exact parameters are generated', () => {
  for (const [command, plugin] of [['iliq rang','uz.lahza.color.warm'],['cinematic color','uz.lahza.color.film'],['kino rangi','uz.lahza.color.film']]) {
    const p = parse(command); assert.deepEqual(p.issues, []);
    assert.deepEqual(p.after.color, { plugin, at_ms: 0, dur_ms: null, params: { kuch: 1 }, source: 'qolda' });
  }
});
test('unknown clauses/scripts/paths and ambiguous settings block all changes', () => {
  for (const input of ['captions on; delete everything', 'reels format and delete everything', 'warm color; install skill /tmp/code', 'captions on; $(rm -rf /)', '__proto__', 'captions on; captions off', 'reels format; shorts format', 'warm color; cinematic color']) {
    const tl = timeline(), p = parse(input, tl); assert.ok(p.issues.length, input);
    assert.equal(apply(p, tl, selected), null, input);
    assert.equal(tl.captions.enabled, false);
  }
  assert.equal(parse('reels format; captionni kattalashtir; not supported').changes.length, 2);
});
test('bounds, unclosed quotes and unavailable metadata cannot apply', () => {
  for (const input of ['', 'x'.repeat(2001), Array(13).fill('caption "a" 0s–1s').join(';'), 'caption "unfinished']) assert.ok(parse(input).issues.some(x => x.code === 'promptLimit'));
  assert.ok(plan('reels format', timeline(), selected, []).issues.some(x => x.code === 'promptProfileMissing'));
});
test('draft and selection staleness reject plans; apply and undo are one immutable transaction', () => {
  const tl = deepFreeze(timeline()); const p = parse('reels format; captions on; warm color; 3-soniyada stop-kadr qo‘y', tl);
  const before = JSON.stringify(tl); const planned = JSON.stringify(p);
  assert.ok(promptPlanIsCurrent(p, structuredClone(tl), selected));
  const changed = structuredClone(tl); changed.captions.words[0].text = 'corrected';
  assert.equal(apply(p, changed, selected), null);
  assert.equal(apply(p, tl, { type: 'video', id: 'a' }), null);
  const after = apply(p, tl, selected); assert.ok(after);
  const history = record({ past: [], present: tl, future: [] }, after);
  assert.equal(history.past.length, 1); assert.deepEqual(travel(history, 'undo').present, tl);
  after.color.params.kuch = .5;
  assert.equal(JSON.stringify(p), planned); assert.equal(JSON.stringify(tl), before);
});

test('no-op commands do not promise a nonexistent undo step', () => {
  const tl = timeline(); const p = parse('captions off', tl);
  assert.ok(p.issues.some(x => x.code === 'promptUnchanged'));
  assert.equal(apply(p, tl, selected), null);
});
