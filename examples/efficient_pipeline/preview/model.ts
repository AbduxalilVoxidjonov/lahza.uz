import type { MontageTimeline, Crop } from "../../../app/src/api/types";

export type { MontageTimeline };
export interface Interval { startMs: number; endMs: number }
export interface Point { ms: number; gain: number }
export interface SimpleColor { brightness: number; contrast: number; saturation: number }
export interface Clip {
  id: string; media: string; url: string; startMs: number; endMs: number;
  inMs: number; outMs: number; speed: number; fps: number; gain: number;
  width: number; height: number; crop: Crop;
}
export interface PreviewPlan {
  clips: readonly Clip[]; durationMs: number; width: number; height: number;
  speech: readonly Interval[]; timeline: MontageTimeline;
}
const check = (condition: boolean, message: string): void => {
  if (!condition) throw new Error(message);
};
export const dbGain = (db: number): number => 10 ** (db / 20);
const finite = (...values: number[]): boolean => values.every(Number.isFinite);
/** Python round(x) for nonnegative durations: exact .5 ties go to the even integer.
 * No epsilon: values immediately around a tie must stay on their own side. */
function roundHalfEven(value: number): number {
  const lower = Math.floor(value);
  return value - lower === 0.5 ? lower + (lower % 2) : Math.round(value);
}

/** Input is the existing typed API contract, not a second timeline schema.
 * URLs must resolve real media bytes (Range/CORS), never a browser fake path. */
export function adaptTimeline(
  timeline: MontageTimeline, mediaURLs: Readonly<Record<string, string>>,
  sourceVAD: Readonly<Record<string, readonly Interval[]>> = {},
): PreviewPlan {
  check(timeline.schema === "lahza.timeline/1", "Timeline schema mos emas");
  check(timeline.video.length > 0, "Kamida bitta video kerak");
  check(!timeline.color, "FFmpeg rang preset/LUT preview qo‘llanmaydi; eksport preview ishlating");
  check(timeline.text.length === 0 && !(timeline.stickers?.length) && !timeline.brand.logo_path,
    "Matn kartasi, stiker va logo bu bounded preview’da qo‘llanmaydi (ASS alohida)");
  check(timeline.audio.loudnorm_lufs == null, "LUFS preview qo‘llanmaydi");
  check(finite(timeline.format.w, timeline.format.h, timeline.audio.source_gain_db,
    timeline.audio.fade_ms) && timeline.format.w > 0 && timeline.format.h > 0 &&
    timeline.audio.fade_ms >= 0, "Format/audio noto‘g‘ri");
  let cursor = 0;
  const clips = timeline.video.map((item): Clip => {
    const media = timeline.media[item.media];
    const url = mediaURLs[item.media];
    check(Boolean(media && url), `Media URL topilmadi: ${item.media}`);
    if (!media || !url) throw new Error("Media yo‘q");
    check(!item.transition_in && item.fx.length === 0,
      `Transition/FX qo‘llanmaydi: ${item.id}; eksport preview ishlating`);
    check(item.reframe === "center" || Boolean(item.crop),
      `Auto/focus/blur preview qo‘llanmaydi: ${item.id}; statik crop tanlang`);
    check(finite(item.src_in_ms, item.src_out_ms, item.speed, item.volume_db,
      media.width, media.height, media.fps, media.duration_ms) &&
      item.src_in_ms >= 0 && item.src_out_ms > item.src_in_ms &&
      item.src_out_ms <= media.duration_ms && item.speed >= 0.25 && item.speed <= 4 &&
      media.width >= 2 && media.height >= 2 && media.fps > 0, `Video chegarasi noto‘g‘ri: ${item.id}`);
    const crop = item.crop ?? { cx: 0.5, cy: 0.5, zoom: 1 };
    check(finite(crop.cx, crop.cy, crop.zoom) && crop.cx >= 0 && crop.cx <= 1 &&
      crop.cy >= 0 && crop.cy <= 1 && crop.zoom >= 1, "Crop noto‘g‘ri");
    const duration = roundHalfEven((item.src_out_ms - item.src_in_ms) / item.speed);
    check(duration >= 1, "Video juda qisqa");
    const clip: Clip = {
      id: item.id, media: item.media, url, startMs: cursor, endMs: cursor + duration,
      inMs: item.src_in_ms, outMs: item.src_out_ms, speed: item.speed, fps: media.fps,
      gain: item.mute ? 0 : dbGain(item.volume_db + timeline.audio.source_gain_db),
      width: media.width, height: media.height, crop: { ...crop },
    };
    cursor += duration;
    return clip;
  });
  // Bounds automation allocation and keeps this an interactive reference, not a batch engine.
  check(cursor <= 600_000, "Preview chegarasi: 10 daqiqa");
  check(timeline.music.length <= 1, "Bu namunada bitta musiqa qatlami qo‘llanadi");
  for (const music of timeline.music) {
    check(Boolean(timeline.media[music.media]), "Musiqa media topilmadi");
    check(finite(music.start_ms, music.src_in_ms, music.gain_db, music.fade_in_ms,
      music.fade_out_ms, music.end_ms ?? cursor) && music.start_ms >= 0 &&
      music.src_in_ms >= 0 && (music.end_ms ?? cursor) > music.start_ms &&
      music.fade_in_ms >= 0 && music.fade_out_ms >= 0, "Musiqa chegarasi noto‘g‘ri");
  }
  const speech = mergeIntervals(clips.flatMap(clip => (sourceVAD[clip.media] ?? []).flatMap(vad => {
    check(finite(vad.startMs, vad.endMs) && vad.startMs >= 0 && vad.endMs > vad.startMs, "VAD noto‘g‘ri");
    const a = Math.max(vad.startMs, clip.inMs), b = Math.min(vad.endMs, clip.outMs);
    return b > a ? [{ startMs: sourceToOutput(clip, a / 1000), endMs: sourceToOutput(clip, b / 1000) }] : [];
  })));
  return { clips, durationMs: cursor, width: timeline.format.w, height: timeline.format.h, speech, timeline };
}

/** Half-open intervals: an exact cut belongs to the NEXT item. */
export function locate(plan: Pick<PreviewPlan, "clips" | "durationMs">, ms: number): { clip: Clip; index: number; ms: number } {
  if (!Number.isFinite(ms)) throw new Error("Seek vaqti noto‘g‘ri");
  const time = Math.max(0, Math.min(ms, plan.durationMs));
  let lo = 0, hi = plan.clips.length - 1;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    const clip = plan.clips[mid];
    if (!clip) throw new Error("Bo‘sh timeline");
    if (time >= clip.endMs) lo = mid + 1; else hi = mid;
  }
  const clip = plan.clips[lo];
  if (!clip) throw new Error("Bo‘sh timeline");
  return { clip, index: lo, ms: time };
}
export function outputToSource(clip: Clip, ms: number): number {
  return Math.max(clip.inMs, Math.min(clip.outMs, clip.inMs + (ms - clip.startMs) * clip.speed)) / 1000;
}
export function sourceToOutput(clip: Clip, seconds: number): number {
  return Math.max(clip.startMs, Math.min(clip.endMs, clip.startMs + (seconds * 1000 - clip.inMs) / clip.speed));
}
export function mergeIntervals(input: readonly Interval[], gapMs = 0): Interval[] {
  const out: Interval[] = [];
  for (const item of [...input].sort((a, b) => a.startMs - b.startMs)) {
    const last = out[out.length - 1];
    if (last && item.startMs <= last.endMs + gapMs) last.endMs = Math.max(last.endMs, item.endMs);
    else out.push({ ...item });
  }
  return out;
}
/** Conservative hangover: short gaps under releaseMs remain ducked. Not a compressor. */
export function duckEnvelope(speech: readonly Interval[], attackMs = 30, releaseMs = 180, duckDb = -12): Point[] {
  check(finite(attackMs, releaseMs, duckDb) && attackMs > 0 && releaseMs > 0 && duckDb <= 0, "Ducking parametri noto‘g‘ri");
  const low = dbGain(duckDb), points: Point[] = [{ ms: 0, gain: 1 }];
  for (const span of mergeIntervals(speech, releaseMs)) {
    points.push({ ms: span.startMs, gain: 1 },
      { ms: Math.min(span.endMs, span.startMs + attackMs), gain: low },
      { ms: span.endMs, gain: low }, { ms: span.endMs + releaseMs, gain: 1 });
  }
  return points;
}
export function envelopeAt(points: readonly Point[], ms: number): number {
  let lo = 0, hi = points.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if ((points[mid]?.ms ?? Infinity) <= ms) lo = mid + 1; else hi = mid;
  }
  const a = points[lo - 1], b = points[lo];
  if (!a) return points[0]?.gain ?? 1;
  if (!b || b.ms === a.ms) return a.gain;
  return a.gain + (b.gain - a.gain) * ((ms - a.ms) / (b.ms - a.ms));
}
/** Same even-pixel static crop geometry as engine reframe/planner.py. */
export function cropRect(clip: Clip, aspect: number): { x: number; y: number; w: number; h: number } {
  const even = (n: number) => Math.floor(n / 2) * 2;
  let h = Math.floor(clip.height / clip.crop.zoom), w = Math.floor(h * aspect);
  if (w > clip.width) { w = clip.width; h = Math.floor(w / aspect); }
  w = even(w); h = even(h);
  if (w < 2 || h < 2) throw new Error("Crop juda kichik");
  return { x: even(Math.max(0, Math.min(clip.width - w, Math.trunc(clip.crop.cx * clip.width - w / 2)))),
    y: even(Math.max(0, Math.min(clip.height - h, Math.trunc(clip.crop.cy * clip.height - h / 2)))), w, h };
}
