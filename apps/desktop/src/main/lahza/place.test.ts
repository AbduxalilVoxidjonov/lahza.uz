import { describe, expect, it, vi } from 'vitest'
import { placeHighlight } from './place'
import type { LahzaEngine } from './engine'

/** A root composition with an A-roll, a caption track, and whatever layers
 *  the A-roll already holds. */
function project(opts: { width?: number; height?: number; aRollLayers?: Array<{ t_start_us: number; t_end_us: number }> } = {}) {
  return {
    root_id: 'root',
    compositions: { root: {
      id: 'root', width: opts.width ?? 1920, height: opts.height ?? 1080,
      tracks: [
        { id: 'track-a', role: 'ARoll', layers: opts.aRollLayers ?? [] },
        { id: 'track-c', role: 'Caption', layers: [] },
      ],
    } },
  }
}

function fakeHost(initial: ReturnType<typeof project>) {
  let snap = initial
  const calls: Array<{ name: string; args: Record<string, unknown>; client?: string }> = []
  let n = 0
  const host = {
    openedProject: () => ({ dir: '/p' }) as never,
    actor: { snapshot: () => snap } as never,
    mediaImporter: { ensureImported: vi.fn(async () => ({ mediaId: 'media-1', disposition: 'added', existing: false, sameContentAs: [] })) } as never,
    mcpCall: (name: string, argsJson: string, client?: string) => {
      const args = JSON.parse(argsJson) as Record<string, unknown>
      calls.push({ name, args, client })
      if (name === 'update_composition') {
        const patch = args.patch as { width: number; height: number }
        snap = { ...snap, compositions: { root: { ...snap.compositions.root, ...patch } } }
        return { ok: true, result: { content: [], structuredContent: {} } }
      }
      if (name === 'add_video_layer') return { ok: true, result: { content: [], structuredContent: { video_layer_id: `v${++n}` } } }
      if (name === 'apply_transcripts') {
        const segments = (args.transcripts as Array<{ segments: unknown[] }>)[0]!.segments
        const root = snap.compositions.root
        const tracks = root.tracks.map((t) => t.role === 'Caption'
          ? { ...t, layers: [...t.layers, ...segments.map((_, i) => ({ id: `cap${t.layers.length + i}`, t_start_us: 0, t_end_us: 0 }))] }
          : t)
        snap = { ...snap, compositions: { root: { ...root, tracks } } }
        return { ok: true, result: { content: [], structuredContent: { caption_track_id: 'track-c', cues: segments.length } } }
      }
      return { ok: true, result: { content: [], structuredContent: {} } }
    },
  }
  return { host: host as never, calls }
}

function fakeEngine(over: { status?: string; clip?: Record<string, unknown>; keyframes?: unknown } = {}): LahzaEngine {
  const clip = { id: 'c1', start_ms: 10_000, end_ms: 14_000, title: 'Muhim fikr', score: 0.9, cuts: [[11_000, 12_000]], hook: null, ...over.clip }
  return {
    request: vi.fn(async (_m: string, route: string) => {
      if (route === '/v1/episodes/e1') return { id: 'e1', title: 'Podkast', status: over.status ?? 'ready', media: { path: 'D:/v/podkast.mp4', width: 1920, height: 1080, duration_ms: 3_600_000 } }
      if (route === '/v1/episodes/e1/clips') return [clip]
      if (route === '/v1/episodes/e1/transcript') return { sentences: [{ id: 1, start_ms: 10_000, end_ms: 14_000, text: 'bu juda muhim', words: [
        { text: 'bu', start_ms: 10_100, end_ms: 10_400 }, { text: 'juda', start_ms: 11_200, end_ms: 11_600 }, { text: 'muhim', start_ms: 12_500, end_ms: 13_000 },
      ] }] }
      if (route.endsWith('/keyframes')) {
        if (over.keyframes instanceof Error) throw over.keyframes
        return over.keyframes ?? []
      }
      throw new Error(`unexpected ${route}`)
    }),
  } as unknown as LahzaEngine
}

describe('placeHighlight', () => {
  it('turns an empty project into a Reel and lays segments, transforms and captions through WeftCut tools', async () => {
    const { host, calls } = fakeHost(project())
    const r = await placeHighlight(host, fakeEngine(), { episode_id: 'e1', clip_id: 'c1', client: 'Claude' })

    expect(calls.map((c) => c.name)).toEqual(['update_composition', 'add_video_layer', 'update_layer_params', 'add_video_layer', 'update_layer_params', 'apply_transcripts', 'restyle_captions'])
    // Only this clip's new cues are lifted above the Reels overlay (1920 × 0.65).
    expect(calls[6]!.args).toEqual({ layer_ids: ['cap0', 'cap1'], y: 1248 })
    expect(calls.every((c) => c.client === 'Claude')).toBe(true)
    expect(calls[0]!.args).toEqual({ patch: { width: 1080, height: 1920 } })
    // The cut [11 s, 12 s) splits the clip into two segments laid end to end.
    expect(calls[1]!.args).toEqual({ media_id: 'media-1', track_id: 'track-a', src_in_us: 10_000_000, src_out_us: 11_000_000, t_start_us: 0, t_end_us: 1_000_000 })
    expect(calls[3]!.args).toEqual({ media_id: 'media-1', track_id: 'track-a', src_in_us: 12_000_000, src_out_us: 14_000_000, t_start_us: 1_000_000, t_end_us: 3_000_000 })
    expect(calls[2]!.args).toMatchObject({ layer_id: 'v1', patch: { kind: 'VideoClip', anchor_x: 0.5, anchor_y: 0.5, x: 540, y: 960 } })
    // 'juda' sat inside the cut, so only the kept words become captions.
    const transcripts = calls[5]!.args.transcripts as Array<{ segments: Array<{ text: string; t_start_us: number }> }>
    expect(transcripts[0]!.segments.map((s) => [s.text, s.t_start_us])).toEqual([['bu', 100_000], ['muhim', 1_500_000]])
    expect(calls[5]!.args.source_layer_ids).toEqual(['v1'])
    expect(r).toMatchObject({ video_layer_ids: ['v1', 'v2'], caption_track_id: 'track-c', cue_count: 2, t_start_us: 0, t_end_us: 3_000_000, canvas: { width: 1080, height: 1920 }, canvas_changed: true })
  })

  it('appends after the last A-roll layer and keeps a project with content at its own canvas', async () => {
    const { host, calls } = fakeHost(project({ aRollLayers: [{ t_start_us: 0, t_end_us: 5_000_000 }] }))
    const r = await placeHighlight(host, fakeEngine({ clip: { cuts: [] } }), { episode_id: 'e1', clip_id: 'c1' })
    // A landscape canvas has no Reels overlay to clear: captions keep their place.
    expect(calls.map((c) => c.name)).toEqual(['add_video_layer', 'apply_transcripts'])
    expect(calls[0]!.args).toMatchObject({ t_start_us: 5_000_000, t_end_us: 9_000_000 })
    expect(calls[0]!.client).toBe('Lahza')
    expect(r.canvas_changed).toBe(false)
  })

  it('a missing reframe plan falls back to centre fill', async () => {
    const { host, calls } = fakeHost(project({ width: 1080, height: 1920 }))
    await placeHighlight(host, fakeEngine({ clip: { cuts: [] }, keyframes: new Error('no vision model') }), { episode_id: 'e1', clip_id: 'c1' })
    expect(calls.find((c) => c.name === 'update_layer_params')!.args).toMatchObject({ patch: { x: 540, y: 960 } })
  })

  it('refuses an episode still analyzing, an unknown clip and a closed project', async () => {
    await expect(placeHighlight(fakeHost(project()).host, fakeEngine({ status: 'analyzing' }), { episode_id: 'e1', clip_id: 'c1' })).rejects.toMatchObject({ code: 'lahza_not_ready' })
    await expect(placeHighlight(fakeHost(project()).host, fakeEngine(), { episode_id: 'e1', clip_id: 'nope' })).rejects.toMatchObject({ code: 'lahza_clip_not_found' })
    const closed = { ...(fakeHost(project()).host as object), openedProject: () => null }
    await expect(placeHighlight(closed as never, fakeEngine(), { episode_id: 'e1', clip_id: 'c1' })).rejects.toMatchObject({ code: 'NoProjectOpen' })
  })

  it('a WeftCut refusal stops the placement with the editor\'s own message', async () => {
    const { host } = fakeHost(project())
    const refusing = { ...(host as object), mcpCall: (name: string) => name === 'add_video_layer'
      ? { ok: false, error: { code: 'invalid_params', message: 'paired-audio overlap' } }
      : { ok: true, result: { content: [], structuredContent: {} } } }
    await expect(placeHighlight(refusing as never, fakeEngine(), { episode_id: 'e1', clip_id: 'c1' })).rejects.toMatchObject({ code: 'weftcut_invalid_params', message: 'add_video_layer: paired-audio overlap' })
  })
})
