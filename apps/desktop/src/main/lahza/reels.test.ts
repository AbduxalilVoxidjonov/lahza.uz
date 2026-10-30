import { describe, expect, it } from 'vitest'
import { clipSegments, fillTransform, focusAt, planReel, type LahzaSentence } from './reels'

describe('clipSegments (port of lahza_engine/timeline.py)', () => {
  it('a plain clip is one segment', () => {
    expect(clipSegments({ start_ms: 1000, end_ms: 5000 })).toEqual([{ src_start_ms: 1000, src_end_ms: 5000, out_ms: 0 }])
  })

  it('cuts split the clip and close the gap', () => {
    expect(clipSegments({ start_ms: 0, end_ms: 10_000, cuts: [[6000, 7000], [2000, 3000]] })).toEqual([
      { src_start_ms: 0, src_end_ms: 2000, out_ms: 0 },
      { src_start_ms: 3000, src_end_ms: 6000, out_ms: 2000 },
      { src_start_ms: 7000, src_end_ms: 10_000, out_ms: 5000 },
    ])
  })

  it('cuts outside the clip and overlapping cuts are clamped and merged', () => {
    expect(clipSegments({ start_ms: 1000, end_ms: 5000, cuts: [[0, 1500], [2000, 3000], [2500, 3500], [4800, 9000]] })).toEqual([
      { src_start_ms: 1500, src_end_ms: 2000, out_ms: 0 },
      { src_start_ms: 3500, src_end_ms: 4800, out_ms: 500 },
    ])
  })

  it('a hook replays its kept intersection before the body', () => {
    expect(clipSegments({ start_ms: 0, end_ms: 10_000, cuts: [[8000, 8500]], hook: { start_ms: 7000, end_ms: 9000 } })).toEqual([
      { src_start_ms: 7000, src_end_ms: 8000, out_ms: 0 },
      { src_start_ms: 8500, src_end_ms: 9000, out_ms: 1000 },
      { src_start_ms: 0, src_end_ms: 8000, out_ms: 1500 },
      { src_start_ms: 8500, src_end_ms: 10_000, out_ms: 9500 },
    ])
  })

  it('refuses an empty clip', () => {
    expect(() => clipSegments({ start_ms: 5, end_ms: 5 })).toThrow()
  })
})

describe('fillTransform', () => {
  const src = { width: 1920, height: 1080 }, reel = { width: 1080, height: 1920 }

  it('16:9 into 9:16 fills by height and centres', () => {
    const t = fillTransform(src, reel)
    expect(t.scale_x).toBeCloseTo(1920 / 1080)
    expect(t.scale_y).toBe(t.scale_x)
    expect(t.x).toBeCloseTo(540)
    expect(t.y).toBeCloseTo(960)
  })

  it('a focus point lands on the canvas centre', () => {
    const t = fillTransform(src, reel, { cx: 0.4, cy: 0.5 })
    // world = Position + S·(local − ½·size): the focus pixel maps to x = 540.
    const focusWorldX = t.x + t.scale_x * (0.4 * 1920 - 0.5 * 1920)
    expect(focusWorldX).toBeCloseTo(540)
  })

  it('a focus near the edge is clamped so no background shows', () => {
    const t = fillTransform(src, reel, { cx: 0.0, cy: 0.5 })
    const leftEdgeWorld = t.x + t.scale_x * (0 - 0.5 * 1920)
    expect(leftEdgeWorld).toBeCloseTo(0)
  })
})

describe('focusAt', () => {
  it('takes the last key at or before t, centre for layouts without one crop', () => {
    const keys = [
      { t_ms: 0, layout: 'focus', cx: 0.3, cy: 0.5, zoom: 1 },
      { t_ms: 4000, layout: 'split', cx: 0.5, cy: 0.5, zoom: 1 },
      { t_ms: 2000, layout: 'manual', cx: 0.7, cy: 0.4, zoom: 1.2 },
    ]
    expect(focusAt(keys, 1000)).toEqual({ cx: 0.3, cy: 0.5, zoom: 1 })
    expect(focusAt(keys, 2500)).toEqual({ cx: 0.7, cy: 0.4, zoom: 1.2 })
    expect(focusAt(keys, 5000)).toEqual({ cx: 0.5, cy: 0.5, zoom: 1 })
    expect(focusAt([], 0)).toEqual({ cx: 0.5, cy: 0.5, zoom: 1 })
  })
})

describe('planReel', () => {
  const sentences: LahzaSentence[] = [
    { id: 1, start_ms: 0, end_ms: 3000, text: 'salom dunyo bugun', words: [
      { text: 'salom', start_ms: 0, end_ms: 500 }, { text: 'dunyo', start_ms: 600, end_ms: 1200 }, { text: 'bugun', start_ms: 2100, end_ms: 2900 },
    ] },
    { id: 2, start_ms: 3000, end_ms: 5000, text: "yo'q", words: [{ text: "yo'q", start_ms: 3100, end_ms: 3600 }] },
  ]

  it('maps segments and words to timeline microseconds through the cuts', () => {
    const plan = planReel({
      clip: { id: 'c', start_ms: 0, end_ms: 4000, title: 't', score: 1, cuts: [[1500, 2000]] },
      sentences, media: { width: 1920, height: 1080 }, canvas: { width: 1080, height: 1920 }, t_start_us: 10_000_000,
    })
    expect(plan.segments.map(({ src_in_us, src_out_us, t_start_us, t_end_us }) => ({ src_in_us, src_out_us, t_start_us, t_end_us }))).toEqual([
      { src_in_us: 0, src_out_us: 1_500_000, t_start_us: 10_000_000, t_end_us: 11_500_000 },
      { src_in_us: 2_000_000, src_out_us: 4_000_000, t_start_us: 11_500_000, t_end_us: 13_500_000 },
    ])
    expect(plan.duration_us).toBe(3_500_000)
    expect(plan.segments[0]!.transform?.scale_x).toBeCloseTo(1920 / 1080)
    expect(plan.transcript.word_timing).toBe('exact')
    expect(plan.transcript.segments).toEqual([
      { text: 'salom dunyo', t_start_us: 10_000_000, t_end_us: 11_200_000, words: [
        { text: 'salom', t_start_us: 10_000_000, t_end_us: 10_500_000 },
        { text: 'dunyo', t_start_us: 10_600_000, t_end_us: 11_200_000 },
      ] },
      { text: 'bugun', t_start_us: 11_600_000, t_end_us: 12_400_000, words: [{ text: 'bugun', t_start_us: 11_600_000, t_end_us: 12_400_000 }] },
      { text: "yo'q", t_start_us: 12_600_000, t_end_us: 13_100_000, words: [{ text: "yo'q", t_start_us: 12_600_000, t_end_us: 13_100_000 }] },
    ])
  })

  it('breaks captions into short cues: at most max_words, and at every long pause', () => {
    const words = ['bir', 'ikki', 'uch', "to'rt", 'besh', 'olti'].map((text, i) => ({ text, start_ms: i * 400 + (i >= 4 ? 1000 : 0), end_ms: i * 400 + 300 + (i >= 4 ? 1000 : 0) }))
    const plan = planReel({
      clip: { id: 'c', start_ms: 0, end_ms: 4000, title: 't', score: 1 },
      sentences: [{ id: 1, start_ms: 0, end_ms: 4000, text: '', words }],
      media: { width: 1920, height: 1080 }, canvas: { width: 1080, height: 1920 }, t_start_us: 0,
    })
    // 'besh' follows a 1.1 s silence, so "to'rt" closes its cue early.
    expect(plan.transcript.segments.map((s) => s.text)).toEqual(['bir ikki uch', "to'rt", 'besh olti'])
    expect(planReel({
      clip: { id: 'c', start_ms: 0, end_ms: 4000, title: 't', score: 1 },
      sentences: [{ id: 1, start_ms: 0, end_ms: 4000, text: '', words }],
      media: { width: 1920, height: 1080 }, canvas: { width: 1080, height: 1920 }, t_start_us: 0, max_words: 5,
    }).transcript.segments.map((s) => s.text)).toEqual(["bir ikki uch to'rt", 'besh olti'])
  })

  it('a source already at the canvas aspect is not transformed', () => {
    const plan = planReel({
      clip: { id: 'c', start_ms: 0, end_ms: 1000, title: 't', score: 1 },
      sentences: [], media: { width: 1080, height: 1920 }, canvas: { width: 1080, height: 1920 }, t_start_us: 0,
    })
    expect(plan.segments[0]!.transform).toBeNull()
    expect(plan.transcript.segments).toEqual([])
  })
})
