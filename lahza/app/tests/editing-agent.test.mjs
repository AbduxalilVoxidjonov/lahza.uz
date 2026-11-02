import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
const dir = mkdtempSync(join(tmpdir(), 'lahza-agent-'));
after(() => rmSync(dir, { recursive: true, force: true }));
for (const [file, name] of [['lib/editing-agent', 'agent'], ['api/types', 'types'], ['i18n/editing-agent/messages', 'messages']]) {
  writeFileSync(join(dir, `${name}.mjs`), ts.transpileModule(readFileSync(new URL(`../src/${file}.ts`, import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  }).outputText);
}
const { boundedPlan, parseStatus, parsePlan, parsePreview, checkedTimeline, contextStamp, selectedVideoId, RequestGate, planRefusal, reviewAgentPlan } = await import(pathToFileURL(join(dir, 'agent.mjs')));
const { DEFAULT_STYLE } = await import(pathToFileURL(join(dir, 'types.mjs')));
const timeline = () => ({ schema: 'lahza.timeline/1', format: { aspect: '16:9', w: 1920, h: 1080, fps: 30, audio_hz: 48000 }, media: {}, video: [], text: [], music: [], captions: { enabled: false, style: structuredClone(DEFAULT_STYLE), words: [] }, brand: { logo_position: 'top_left', logo_opacity: 1 }, audio: { source_gain_db: 0, fade_ms: 0 }, provenance: { notes: [] } });
const context = () => ({ prompt: 'make captions bigger', timeline: timeline(), selection: { type: 'video', id: 'a' }, mode: 'ai' });
test('status accepts explicit model missing and rejects malformed contract fields', () => {
  const status = { available: false, reason: 'model missing', model_id: null, supported_operations: ['format'] };
  assert.deepEqual(parseStatus(status), status);
  for (const patch of [{ available: 'yes' }, { reason: undefined }, { model_id: 4 }, { supported_operations: [{}] }]) assert.throws(() => parseStatus({ ...status, ...patch }));
});
test('plans remain opaque bounded JSON and envelope strings are guarded', () => {
  const valid = { plan: { schema: 'lahza.edit-plan/1', base_revision: 'a'.repeat(64), commands: [{ tool: 'set_format', args: { profile: 'instagram_reels' } }], unresolved: [] }, changes: ['Format'], warnings: [], model_id: 'local-model' };
  assert.deepEqual(parsePlan(valid), valid);
  for (const plan of [null, [], 'text', { number: Infinity }, JSON.parse('{"__proto__":{}}'), { huge: 'a'.repeat(10001) }]) assert.equal(boundedPlan(plan), false);
  let deep = {}; for (let i = 0; i < 26; i++) deep = { nested: deep };
  assert.equal(boundedPlan(deep), false);
  assert.equal(boundedPlan({ rows: Array(20001).fill(1) }), false);
  for (const patch of [{ changes: [null] }, { warnings: 'bad' }, { model_id: null }]) assert.throws(() => parsePlan({ ...valid, ...patch }));
});
test('preview envelope and complete timeline reject malformed nested data', () => {
  const tl = timeline();
  assert.equal(checkedTimeline(tl), tl);
  assert.deepEqual(parsePreview({ timeline: tl, changes: [], warnings: [] }).timeline, tl);
  for (const value of [null, {}, { ...tl, video: [{}] }, { ...tl, format: { ...tl.format, fps: '30' } }, { ...tl, captions: { ...tl.captions, words: [{ text: 'missing fields' }] } }, { ...tl, captions: { ...tl.captions, style: { ...DEFAULT_STYLE, font_size: NaN } } }]) assert.throws(() => checkedTimeline(value));
  assert.throws(() => parsePreview({ timeline: [], changes: [], warnings: [] }));
});
test('new captions and freeze effects validate even when original collections were empty', () => {
  const tl = timeline();
  tl.text.push({ id: 'caption', start_ms: 0, end_ms: 1000, text: 'Hi', kind: 'title', position: 'lower', animation: 'none' });
  tl.video.push({ id: 'a', media: 'm', src_in_ms: 0, src_out_ms: 5000, reframe: 'center', speed: 1, volume_db: 0, mute: false, reason: '', user_edited: true, fx: [{ plugin: 'freeze', at_ms: 1000, params: {}, source: 'qolda', dur_ms: 1000 }] });
  assert.equal(checkedTimeline(tl), tl);
  tl.video[0].fx[0].source = 'invalid'; assert.throws(() => checkedTimeline(tl));
});
test('each prompt, draft, selection and mode change invalidates a request', () => {
  for (const change of [c => { c.prompt = 'other'; }, c => { c.timeline.format.fps = 24; }, c => { c.selection.id = 'b'; }, c => { c.selection = { type: 'text', id: 'a' }; }, c => { c.mode = 'local'; }]) {
    const c = context(), gate = new RequestGate(); gate.update(contextStamp(c)); const ticket = gate.capture();
    change(c); gate.update(contextStamp(c)); assert.equal(gate.current(ticket), false);
  }
});
test('change and revert never revives old async response or Apply ticket', () => {
  const c = context(), gate = new RequestGate(), original = contextStamp(c);
  gate.update(original); const ticket = gate.capture();
  gate.update('changed'); gate.update(original);
  assert.equal(gate.current(ticket), false);
  assert.equal(gate.current(gate.capture(), original), true);
});
test('late responses cannot overwrite a changed draft and functional edit rechecks current draft', async () => {
  const c = context(), gate = new RequestGate(); gate.update(contextStamp(c)); const ticket = gate.capture();
  let resolve; const pending = new Promise(r => { resolve = r; }); let applied = false;
  const result = pending.then(() => { if (gate.current(ticket)) applied = true; });
  c.prompt = 'new request'; gate.update(contextStamp(c)); resolve(); await result;
  assert.equal(applied, false);
  const fresh = gate.capture(); const actual = structuredClone(c); actual.timeline.format.fps = 60;
  assert.equal(gate.current(fresh, contextStamp(actual)), false);
});
test('only selected video IDs are sent to executor', () => {
  assert.equal(selectedVideoId(null), null);
  assert.equal(selectedVideoId({ type: 'text', id: 'a' }), null);
  assert.equal(selectedVideoId({ type: 'video', id: 'a' }), 'a');
});

const planResponse = commands => ({ plan: { schema: 'lahza.edit-plan/1', base_revision: '0'.repeat(64), commands, unresolved: [] }, changes: [], warnings: [], model_id: 'model' });
test('exact backend command union accepts all tools and preserves opaque plan identity', () => {
  const commands = [
    { tool: 'set_format', args: { profile: 'youtube_shorts' } },
    { tool: 'set_captions', args: { enabled: true, font_size: null } },
    { tool: 'set_captions', args: { enabled: false } },
    { tool: 'add_caption', args: { text: 'Hello\nworld', start_ms: 0, end_ms: 1000 } },
    { tool: 'set_color', args: { preset: 'cool' } },
    { tool: 'freeze_clip', args: { clip_id: 'a', at_ms: 0, duration_ms: 100 } },
  ];
  const response = planResponse(commands);
  assert.equal(parsePlan(response).plan, response.plan);
  response.plan.unresolved = ['Unsupported request'];
  assert.equal(parsePlan(response).plan, response.plan); // Executor blocks unresolved semantics.
});
test('malformed plan schema, revision, bounds and extra fields fail at the API boundary', () => {
  for (const patch of [
    { schema: 'future' }, { base_revision: 'A'.repeat(64) }, { base_revision: 'a'.repeat(63) },
    { commands: Array(13).fill({ tool: 'set_color', args: { preset: 'warm' } }) },
    { unresolved: [''] }, { unresolved: ['a'.repeat(501)] }, { unresolved: Array(13).fill('x') },
    { extra: true }, { commands: 'bad' },
  ]) {
    const response = planResponse([]); Object.assign(response.plan, patch);
    assert.throws(() => parsePlan(response), /Invalid editing-agent plan response/);
  }
});
test('malformed commands cannot reach the executor through a successful PlanOut', () => {
  const invalid = [
    { tool: 'run_script', args: {} }, { tool: 'constructor', args: {} },
    { tool: 'set_format', args: { profile: 'custom' } },
    { tool: 'set_color', args: { preset: 'cinematic' } },
    { tool: 'set_color', args: { preset: 'warm', extra: true } },
    { tool: 'set_color', args: { preset: 'warm' }, extra: true },
    ...[23, 201, 24.5, '80'].map(font_size => ({ tool: 'set_captions', args: { enabled: true, font_size } })),
    { tool: 'set_captions', args: { enabled: 1 } },
    ...['', 'x'.repeat(501), '{code}', 'back\\slash', '\x00'].map(text => ({ tool: 'add_caption', args: { text, start_ms: 0, end_ms: 1 } })),
    { tool: 'add_caption', args: { text: 'ok', start_ms: -1, end_ms: 1 } },
    { tool: 'add_caption', args: { text: 'ok', start_ms: 0, end_ms: 0 } },
    ...[99, 5001, 100.5].map(duration_ms => ({ tool: 'freeze_clip', args: { clip_id: 'a', at_ms: 0, duration_ms } })),
    { tool: 'freeze_clip', args: { clip_id: '', at_ms: 0, duration_ms: 100 } },
    { tool: 'freeze_clip', args: { clip_id: 'a', at_ms: 0.5, duration_ms: 100 } },
  ];
  for (const command of invalid) assert.throws(() => parsePlan(planResponse([command])), JSON.stringify(command));
});

test('unresolved plans retain warnings and opaque commands without entering preview', () => {
  const response = planResponse([{ tool: 'set_color', args: { preset: 'warm' } }]);
  response.plan.unresolved = ['Cannot remove background'];
  response.warnings = ['Please revise the request'];
  const result = parsePlan(response);
  assert.equal(result.plan, response.plan);
  assert.deepEqual(result.warnings, response.warnings);
  assert.deepEqual(planRefusal(result.plan), response.plan.unresolved);
  assert.deepEqual(planRefusal(planResponse([]).plan), []);
  assert.throws(() => planRefusal({ unresolved: [] }));
});
test('parsePreview accepts anonymized actual Python PreviewOut model_dump by alias', () => {
  const fixture = JSON.parse(readFileSync(new URL('./fixtures/editing-agent-preview.json', import.meta.url), 'utf8'));
  const preview = parsePreview(fixture);
  assert.equal(preview.timeline.schema, 'lahza.timeline/1');
  assert.deepEqual(preview.timeline, fixture.timeline);
  const malformed = structuredClone(fixture);
  malformed.timeline.video[0].speed = '1';
  assert.throws(() => parsePreview(malformed));
});
const actualPreview = new URL('../../build/local-llm/contract-preview.json', import.meta.url);
test('parsePreview accepts local unmodified Python contract output', { skip: !existsSync(actualPreview) }, () => {
  const fixture = JSON.parse(readFileSync(actualPreview, 'utf8'));
  assert.equal(parsePreview(fixture).timeline.schema, 'lahza.timeline/1');
});

test('refusal skips preview entirely; resolved plan is forwarded as the same opaque value', async () => {
  const response = planResponse([]);
  response.plan.unresolved = ['Unsupported edit'];
  const refused = await reviewAgentPlan(parsePlan(response).plan, async () => { assert.fail('must not call preview for unresolved plan'); });
  assert.equal(refused.kind, 'refused');
  assert.deepEqual(refused.unresolved, response.plan.unresolved);
  response.plan.unresolved = [];
  let calls = 0;
  const ready = await reviewAgentPlan(parsePlan(response).plan, async plan => {
    calls++; assert.equal(plan, response.plan); return 'preview';
  });
  assert.deepEqual(ready, { kind: 'ready', preview: 'preview' }); assert.equal(calls, 1);
});
test('AI dictionaries cover every label in all four locales without technical operation IDs', async () => {
  const { dictionaries } = await import(pathToFileURL(join(dir, 'messages.mjs')));
  const keys = Object.keys(dictionaries.uz).sort();
  for (const locale of ['uz', 'uz-Cyrl', 'ru', 'en']) {
    assert.deepEqual(Object.keys(dictionaries[locale]).sort(), keys);
    for (const text of Object.values(dictionaries[locale])) {
      assert.equal(typeof text, 'string'); assert.ok(text.length);
      assert.doesNotMatch(text, /Premiere|set_format|set_captions|add_caption|set_color|freeze_clip/);
    }
  }
  for (const key of ['title', 'mode', 'local', 'ai', 'generate', 'apply', 'refusal', 'settings']) assert.notEqual(dictionaries.uz[key], dictionaries.en[key], key);
});
