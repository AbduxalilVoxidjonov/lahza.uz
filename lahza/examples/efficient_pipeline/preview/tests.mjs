import assert from "node:assert/strict";
import { test, after } from "node:test";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "../../..");
const out = mkdtempSync(join(tmpdir(), "lahza-preview-"));
after(() => rmSync(out, { recursive: true, force: true }));
execFileSync(process.execPath, [join(root, "app/node_modules/typescript/bin/tsc"),
  "-p", join(here, "tsconfig.json"), "--noEmit", "false", "--outDir", out, "--module", "commonjs",
  "--moduleResolution", "node"], { stdio: "inherit" });
const require = createRequire(import.meta.url);
const { adaptTimeline, locate, outputToSource, sourceToOutput, duckEnvelope, envelopeAt, cropRect } =
  require(join(out, "examples/efficient_pipeline/preview/model.js"));
const { timelineAss } = require(join(out, "examples/efficient_pipeline/preview/ass.js"));
const { DEFAULT_STYLE } = require(join(out, "app/src/api/types.js"));
const fixture = () => ({
  schema: "lahza.timeline/1", format: { aspect: "16:9", w: 1280, h: 720, fps: 30, audio_hz: 48000 },
  media: { a: { id: "a", path: "/local/input.mp4", duration_ms: 10000, width: 1920, height: 1080,
    fps: 30, has_audio: true, origin: "file" } },
  video: [
    { id: "v1", media: "a", src_in_ms: 1000, src_out_ms: 3000, speed: 1 },
    { id: "v2", media: "a", src_in_ms: 6000, src_out_ms: 10000, speed: 2 },
  ].map(item => ({ ...item, reframe: "center", volume_db: 0, mute: false, fx: [], reason: "test", user_edited: true })),
  text: [], music: [], captions: { enabled: false, words: [], style: DEFAULT_STYLE },
  audio: { source_gain_db: 0, fade_ms: 150 }, brand: { logo_position: "top_right", logo_opacity: 0.8 },
  provenance: { notes: [] },
});
const urls = { a: "http://127.0.0.1:9999/media/a" };

test("existing timeline: source ms / speed -> output; exact cuts use next item", () => {
  const tl = fixture(), snapshot = structuredClone(tl);
  const plan = adaptTimeline(tl, urls);
  assert.equal(plan.durationMs, 4000);
  assert.equal(locate(plan, 1999).index, 0);
  assert.equal(locate(plan, 2000).index, 1);
  assert.equal(outputToSource(locate(plan, 2500).clip, 2500), 7);
  assert.equal(sourceToOutput(locate(plan, 2500).clip, 7), 2500);
  assert.equal(locate(plan, -10).ms, 0);
  assert.equal(locate(plan, 90000).ms, 4000);
  assert.throws(() => locate(plan, NaN));
  assert.deepEqual(tl, snapshot);
});
test("duration follows Python server half-even rounding; inverse stays bounded", () => {
  const tl = fixture(); tl.video = [{ ...tl.video[0], src_out_ms: 2501, speed: 1.5 }];
  const plan = adaptTimeline(tl, urls), clip = plan.clips[0];
  assert.equal(plan.durationMs, Math.round(1501 / 1.5));
  assert.equal(sourceToOutput(clip, 100), plan.durationMs);
  for (const ms of [0, 100, 500, 999]) assert.ok(Math.abs(sourceToOutput(clip, outputToSource(clip, ms)) - ms) < 1e-6);
  tl.video[0] = { ...tl.video[0], src_in_ms: 0, src_out_ms: 1001, speed: 2 };
  assert.equal(adaptTimeline(tl, urls).durationMs, 500); // Python round(500.5), NOT Math.round.
  tl.video[0].src_out_ms = 1003;
  assert.equal(adaptTimeline(tl, urls).durationMs, 502); // Python round(501.5).
});
test("VAD intersects cuts, scales speed, and maps repeated source ranges independently", () => {
  const tl = fixture();
  tl.video.push({ ...tl.video[0], id: "repeat" });
  const plan = adaptTimeline(tl, urls, { a: [{ startMs: 2000, endMs: 7000 }] });
  assert.deepEqual(plan.speech, [
    { startMs: 1000, endMs: 2500 }, { startMs: 5000, endMs: 6000 },
  ]);
});
test("ducking attack/release and initial-in-speech seek gain", () => {
  const points = duckEnvelope([{ startMs: 1000, endMs: 2000 }], 50, 200, -12);
  const low = 10 ** (-12 / 20);
  assert.equal(envelopeAt(points, 500), 1);
  assert.ok(Math.abs(envelopeAt(points, 1025) - (1 + low) / 2) < 1e-9);
  assert.ok(Math.abs(envelopeAt(points, 1500) - low) < 1e-9);
  assert.ok(Math.abs(envelopeAt(points, 2100) - (1 + low) / 2) < 1e-9);
  assert.equal(envelopeAt(points, 2200), 1);
  assert.equal(envelopeAt(duckEnvelope([]), 1000), 1);
  assert.throws(() => duckEnvelope([], 0));
});
test("short speech gaps use conservative hangover instead of conflicting ramps", () => {
  const points = duckEnvelope([{ startMs: 0, endMs: 100 }, { startMs: 180, endMs: 400 }]);
  assert.ok(envelopeAt(points, 150) < 0.3);
  assert.equal(envelopeAt(points, 600), 1);
});
test("static even-pixel crop stays inside source", () => {
  const clip = adaptTimeline(fixture(), urls).clips[0];
  assert.deepEqual(cropRect(clip, 16 / 9), { x: 0, y: 0, w: 1920, h: 1080 });
  const rect = cropRect({ ...clip, crop: { cx: 1, cy: 1, zoom: 2 } }, 9 / 16);
  assert.ok(rect.x + rect.w <= clip.width && rect.y + rect.h <= clip.height);
  assert.ok(Object.values(rect).every(x => x % 2 === 0));
});
test("unsupported features fail explicitly rather than silently changing export look", () => {
  for (const change of [
    tl => { tl.video[1].transition_in = { plugin: "dissolve", dur_ms: 200 }; },
    tl => { tl.color = { plugin: "uz.lahza.color.warm" }; },
    tl => { tl.video[0].fx = [{ plugin: "freeze" }]; },
    tl => { tl.video[0].reframe = "auto"; },
    tl => { tl.stickers = [{ id: "s" }]; },
    tl => { tl.audio.loudnorm_lufs = -14; },
    tl => { tl.video[0].speed = 0; },
    tl => { tl.video[0].src_out_ms = 10001; },
  ]) {
    const tl = fixture(); change(tl);
    assert.throws(() => adaptTimeline(tl, urls));
  }
  assert.throws(() => adaptTimeline(fixture(), {}), /URL/);
});
test("ASS uses OUTPUT time and serializes worker calls with latest-frame backpressure", async () => {
  const calls = [], releases = [], sizes = [];
  let active = 0, maxActive = 0, destroyed = false;
  // Test double for scheduling only; this is not claimed as libass/browser validation.
  const port = {
    ready: Promise.resolve(),
    async manualRender(data) {
      active++; maxActive = Math.max(maxActive, active); calls.push(data.mediaTime);
      sizes.push([data.width, data.height]);
      await new Promise(resolve => releases.push(resolve)); active--;
    },
    async destroy() { destroyed = true; },
  };
  const errors = [];
  const ass = timelineAss(port, 3840, 2160, error => errors.push(error));
  ass.setIsPaused(false);
  ass.setCurrentTime(2500);
  await new Promise(resolve => setImmediate(resolve));
  ass.setCurrentTime(2510); ass.setCurrentTime(2520);
  releases.shift()();
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(calls, [2.5, 2.52]); // A source video at 7 s is never used by the port.
  assert.deepEqual(sizes, [[1280, 720], [1280, 720]]);
  releases.shift()();
  await ass.destroy();
  assert.equal(maxActive, 1); assert.equal(destroyed, true); assert.deepEqual(errors, []);
});
test("ASS cleanup while initialization pending suppresses stale renders", async () => {
  let ready, calls = 0, destroyed = false;
  const port = { ready: new Promise(resolve => { ready = resolve; }),
    async manualRender() { calls++; }, async destroy() { destroyed = true; } };
  const ass = timelineAss(port, 1280, 720, () => assert.fail("unexpected failure"));
  ass.setCurrentTime(1000);
  const done = ass.destroy(); ready(); await done;
  assert.equal(calls, 0); assert.equal(destroyed, true);
});
