import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import ts from 'typescript';
const require = createRequire(import.meta.url);
const dir = mkdtempSync(join(tmpdir(), 'lahza-profile-'));
after(() => rmSync(dir, { recursive: true, force: true }));
for (const [file, output] of [['api/types','types'], ['lib/montage','montage'], ['lib/montage-edit','edit'], ['lib/export-profiles','profiles'], ['components/SafeZone','safe']]) {
  const code = ts.transpileModule(readFileSync(new URL(`../src/${file}.${output === 'safe' ? 'tsx' : 'ts'}`, import.meta.url), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX },
  }).outputText.replaceAll('"../api/types"','"./types.mjs"').replaceAll('"./montage"','"./montage.mjs"')
    .replaceAll('"react/jsx-runtime"', JSON.stringify(pathToFileURL(require.resolve('react/jsx-runtime')).href));
  writeFileSync(join(dir, `${output}.mjs`), code);
}
const load = name => import(pathToFileURL(join(dir, `${name}.mjs`)).href);
const { profileIssues, applyRecommendedFormat } = await load('profiles');
const { record, travel } = await load('edit');
const { timelineDuration, timelineRev } = await load('montage');
const { SafeZoneOverlay } = await load('safe');
const { renderToStaticMarkup } = await import('react-dom/server');
const { createElement } = await import('react');
const tl = (duration = 180000, w = 1080, h = 1920) => ({ format: { aspect: '9:16', w, h, fps: 30, audio_hz: 48000 },
  video: [{ id: 'a', src_in_ms: 1000, src_out_ms: duration + 1000, speed: 1, fx: [] }], text: [], stickers: [], music: [], captions: { enabled: true, words: [] } });
const profile = (id = 'youtube_shorts') => ({ id, name: id, recommended_format: { aspect: '9:16', w: 1080, h: 1920, fps: 30 },
  safe_zone: { top_pct: .10, bottom_pct: .25, side_pct: .10 }, restrictions: { max_duration_s: id === 'youtube_shorts' ? 180 : null, square_or_vertical: id === 'youtube_shorts' },
  recommendations: { max_duration_s: id === 'instagram_reels' ? 180 : null, encoding: 'MP4 / H.264 / AAC', fps_note: 'Lahza preset, not a minimum' }, sources: [] });
test('Shorts accepts exactly 180s and square/vertical; rejects longer or landscape', () => {
  const p = profile();
  assert.equal(profileIssues(tl(), p).filter(x => x.severity === 'error').length, 0);
  assert.equal(profileIssues(tl(180000, 1080, 1080), p).filter(x => x.severity === 'error').length, 0);
  assert.ok(profileIssues(tl(180001), p).some(x => x.code === 'durationLimit'));
  assert.ok(profileIssues(tl(1000, 1920, 1080), p).some(x => x.code === 'shapeLimit'));
});
test('Instagram duration and FPS remain nonblocking recommendations from profile metadata', () => {
  const t = tl(200000); t.format.fps = 24;
  const issues = profileIssues(t, profile('instagram_reels'));
  assert.equal(issues.filter(x => x.severity === 'error').length, 0);
  assert.ok(issues.some(x => x.code === 'fpsAdvice')); assert.ok(issues.some(x => x.code === 'durationAdvice'));
});
test('duration validation includes title cards and source speed', () => {
  const t = tl(180000); t.video[0].speed = 2;
  assert.equal(timelineDuration(t), 90000);
  t.text = [{ kind: 'card', start_ms: 90000, end_ms: 181000 }];
  assert.ok(profileIssues(t, profile()).some(x => x.code === 'durationLimit'));
});
test('profile choice changes no format; explicit recommended landscape apply keeps all clip/overlay timings', () => {
  const original = tl();
  const selected = { ...original, target_platform: 'youtube_video' };
  assert.equal(selected.format, original.format);
  const p = profile('youtube_video'); p.recommended_format = { aspect: '16:9', w: 1920, h: 1080, fps: 30 };
  const applied = applyRecommendedFormat(selected, p);
  assert.deepEqual(applied.format, { ...original.format, ...p.recommended_format });
  for (const track of ['video','text','captions','stickers','music']) assert.equal(applied[track], original[track]);
  assert.equal(timelineDuration(applied), timelineDuration(original));
  assert.equal(applyRecommendedFormat(original, { ...p, recommended_format: null }), original);
  let h = record({ past: [], present: original, future: [] }, selected); h = record(h, applied);
  assert.equal(travel(h, 'undo').present, selected); assert.equal(travel(travel(h, 'undo'), 'redo').present, applied);
  assert.notEqual(timelineRev(original), timelineRev(selected));
});
test('safe overlay reads dynamic custom margins, including landscape; rotated sticker warning uses pixel bounds', () => {
  const margins = { top: .05, bottom: .08, side: .12 };
  const html = renderToStaticMarkup(createElement(SafeZoneOverlay, { visible: true, margins }));
  for (const style of ['top:5%', 'bottom:8%', 'left:12%', 'right:12%']) assert.ok(html.includes(style));
  assert.equal(renderToStaticMarkup(createElement(SafeZoneOverlay, { visible: false, margins })), '');
  const t = tl(); t.stickers = [{ id: 'rotated', x: .5, y: .4, width: .1, height: .6, rotation: 90 }];
  assert.ok(profileIssues(t, profile()).some(x => x.code === 'stickerAdvice'));
  t.stickers[0].rotation = 0;
  assert.ok(!profileIssues(t, profile()).some(x => x.code === 'stickerAdvice'));
});
test('locale fallback spread precedes localized profile keys', () => {
  const source = ts.createSourceFile('messages.ts', readFileSync(new URL('../src/i18n/editor-extra/index.ts', import.meta.url), 'utf8'), ts.ScriptTarget.Latest, true);
  for (const statement of source.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (!['uz','ru','cyrl'].includes(declaration.name.getText(source))) continue;
      const props = declaration.initializer.properties;
      const spread = props.findIndex(ts.isSpreadAssignment);
      const local = props.findIndex(p => p.name?.getText(source) === 'platform');
      assert.ok(spread < local, 'English fallback must not overwrite localized platform copy');
    }
  }
});

test('creation sends explicit platform and omits aspect unless user overrides it', async () => {
  const { platformCreationOverrides } = await load('profiles');
  assert.deepEqual(platformCreationOverrides(), { target_platform: 'custom' });
  assert.deepEqual(platformCreationOverrides('youtube_video'), { target_platform: 'youtube_video' });
  assert.deepEqual(platformCreationOverrides('instagram_reels', '16:9'), { target_platform: 'instagram_reels', aspect: '16:9' });
  assert.deepEqual(platformCreationOverrides('youtube_shorts', '1:1'), { target_platform: 'youtube_shorts', aspect: '1:1' });
});
