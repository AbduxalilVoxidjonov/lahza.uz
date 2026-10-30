/** Lahza highlight → WeftCut timeline, as pure data. The engine speaks
 *  source-absolute milliseconds; the timeline speaks integer microseconds. A
 *  clip is not one span: `cuts` remove source ranges and a `hook` replays a
 *  range at the front, so a clip becomes several source segments laid end to
 *  end — the same segments `lahza_engine/timeline.py` renders, so what lands
 *  on the timeline plays exactly as Lahza's own export would. */

import type { LahzaClip, LahzaKeyframe, LahzaMedia, LahzaSentence } from '../../shared/lahza'

export type { LahzaClip, LahzaKeyframe, LahzaMedia, LahzaSentence }

/** One kept source range and where it starts in the clip's output, both ms. */
export interface ClipSegment { src_start_ms: number; src_end_ms: number; out_ms: number }

/** Port of `Timeline` (lahza_engine/timeline.py): kept ranges after cuts,
 *  preceded by the hook's intersection with them. */
export function clipSegments(clip: Pick<LahzaClip, 'start_ms' | 'end_ms' | 'cuts' | 'hook'>): ClipSegment[] {
  if (clip.end_ms <= clip.start_ms) throw new Error(`clip end ${clip.end_ms} must be after start ${clip.start_ms}`)
  const kept: Array<[number, number]> = []
  let cursor = clip.start_ms
  for (const [ra, rb] of [...(clip.cuts ?? [])].sort((x, y) => x[0] - y[0] || x[1] - y[1])) {
    const a = Math.max(ra, clip.start_ms), b = Math.min(rb, clip.end_ms)
    if (b <= a) continue
    if (a > cursor) kept.push([cursor, a])
    cursor = Math.max(cursor, b)
  }
  if (cursor < clip.end_ms) kept.push([cursor, clip.end_ms])
  const prefix: Array<[number, number]> = clip.hook
    ? kept.map(([a, b]): [number, number] => [Math.max(a, clip.hook!.start_ms), Math.min(b, clip.hook!.end_ms)]).filter(([a, b]) => b > a)
    : []
  const out: ClipSegment[] = []
  let at = 0
  for (const [a, b] of [...prefix, ...kept]) {
    out.push({ src_start_ms: a, src_end_ms: b, out_ms: at })
    at += b - a
  }
  return out
}

export interface Transform { x: number; y: number; scale_x: number; scale_y: number; anchor_x: number; anchor_y: number }

/** Scale-to-fill a `canvas` with a `source` frame, centred on the normalized
 *  focus point (cx, cy) and clamped so no canvas edge shows past the picture.
 *  WeftCut's transform is `world = Position + S·(local − anchor·naturalSize)`
 *  with the full source as natural size, so with a centre anchor the focus
 *  lands on the canvas centre when Position = centre − S·size·(focus − ½). */
export function fillTransform(source: { width: number; height: number }, canvas: { width: number; height: number }, focus: { cx: number; cy: number } = { cx: 0.5, cy: 0.5 }, zoom = 1): Transform {
  const s = Math.max(canvas.width / source.width, canvas.height / source.height) * Math.max(1, zoom)
  // Half the visible window, in normalized source units, bounds the focus.
  const hx = canvas.width / (2 * s * source.width), hy = canvas.height / (2 * s * source.height)
  const clamp = (v: number, h: number) => (h >= 0.5 ? 0.5 : Math.min(1 - h, Math.max(h, v)))
  const fx = clamp(focus.cx, hx), fy = clamp(focus.cy, hy)
  return {
    x: canvas.width / 2 - s * source.width * (fx - 0.5),
    y: canvas.height / 2 - s * source.height * (fy - 0.5),
    scale_x: s, scale_y: s, anchor_x: 0.5, anchor_y: 0.5,
  }
}

/** The reframe key in force at clip-output time `t_ms`: the last one at or
 *  before it (the first one before any). Only `focus`/`manual` keys carry a
 *  crop centre; `split` and `fit_blur` layouts have no single-crop equivalent,
 *  so they fall back to centre fill. */
export function focusAt(keys: readonly LahzaKeyframe[], t_ms: number): { cx: number; cy: number; zoom: number } {
  const lane = keys.filter((k) => (k.lane ?? 'a') === 'a').sort((a, b) => a.t_ms - b.t_ms)
  let key = lane[0]
  for (const k of lane) if (k.t_ms <= t_ms) key = k
  if (!key || (key.layout !== 'focus' && key.layout !== 'manual')) return { cx: 0.5, cy: 0.5, zoom: 1 }
  return { cx: key.cx, cy: key.cy, zoom: key.zoom || 1 }
}

export interface CaptionWord { text: string; t_start_us: number; t_end_us: number }
export interface CaptionSegment { text: string; t_start_us: number; t_end_us: number; words: CaptionWord[] }
export interface PlacedSegment {
  src_in_us: number; src_out_us: number; t_start_us: number; t_end_us: number
  transform: Transform | null
}
export interface ReelPlan {
  segments: PlacedSegment[]
  /** One `apply_transcripts` entry for the whole clip, timeline-absolute. */
  transcript: { word_timing: 'exact'; segments: CaptionSegment[] }
  duration_us: number
}

const US = 1000
/** Words per caption cue — Lahza's `StyleTemplate.max_words` default. */
export const REEL_CAPTION_MAX_WORDS = 3
/** A silence longer than this starts a new cue. */
const CAPTION_PAUSE_MS = 700
/** Instagram / Shorts cover the bottom 35% of a vertical frame with their own
 *  UI (Lahza's `SAFE_ZONE`), so a Reel's captions sit on that line. */
export const REEL_CAPTION_BOTTOM = 0.65

/** Lay one clip on the timeline starting at `t_start_us`: one video segment
 *  per kept range, each reframed for the canvas, and the clip's words mapped
 *  through the same segments into short caption cues (at most `max_words`
 *  words, never across a sentence, a cut or a pause). */
export function planReel(input: {
  clip: LahzaClip; sentences: readonly LahzaSentence[]; media: Pick<LahzaMedia, 'width' | 'height'>
  canvas: { width: number; height: number }; t_start_us: number; keyframes?: readonly LahzaKeyframe[]; max_words?: number
}): ReelPlan {
  const { clip, sentences, media, canvas, t_start_us } = input
  const sameAspect = Math.abs(media.width * canvas.height - media.height * canvas.width) < media.width
  const segs = clipSegments(clip)
  const placed: PlacedSegment[] = segs.map((g) => {
    const f = focusAt(input.keyframes ?? [], g.out_ms)
    return {
      src_in_us: g.src_start_ms * US, src_out_us: g.src_end_ms * US,
      t_start_us: t_start_us + g.out_ms * US, t_end_us: t_start_us + (g.out_ms + g.src_end_ms - g.src_start_ms) * US,
      transform: sameAspect && f.zoom <= 1 ? null : fillTransform(media, canvas, f, f.zoom),
    }
  })
  const maxWords = Math.max(1, input.max_words ?? REEL_CAPTION_MAX_WORDS)
  const cues: CaptionSegment[] = []
  for (const g of segs) {
    const toTimeline = (ms: number) => t_start_us + (g.out_ms + ms - g.src_start_ms) * US
    for (const s of sentences) {
      const words = s.words.filter((w) => w.start_ms >= g.src_start_ms && w.end_ms <= g.src_end_ms && w.text.trim() !== '')
      // A Reel reads a few words at a time (Lahza's own `max_words`), and a
      // pause is where a reader expects the line to change.
      let chunk: typeof words = []
      const flush = () => {
        if (chunk.length === 0) return
        cues.push({
          text: chunk.map((w) => w.text.trim()).join(' '),
          t_start_us: toTimeline(chunk[0]!.start_ms), t_end_us: toTimeline(chunk[chunk.length - 1]!.end_ms),
          words: chunk.map((w) => ({ text: w.text.trim(), t_start_us: toTimeline(w.start_ms), t_end_us: toTimeline(w.end_ms) })),
        })
        chunk = []
      }
      for (const w of words) {
        const prev = chunk[chunk.length - 1]
        if (chunk.length >= maxWords || (prev && w.start_ms - prev.end_ms > CAPTION_PAUSE_MS)) flush()
        chunk.push(w)
      }
      flush()
    }
  }
  const last = segs[segs.length - 1]!
  return {
    segments: placed,
    transcript: { word_timing: 'exact', segments: cues },
    duration_us: (last.out_ms + last.src_end_ms - last.src_start_ms) * US,
  }
}
