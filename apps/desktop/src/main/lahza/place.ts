import type { TsActorHost } from '../state/ts-actor-host'
import type { Project } from '../state/model'
import { mcpActor } from '../state/mcp-actor'
import { LahzaError, type LahzaEngine } from './engine'
import { planReel, REEL_CAPTION_BOTTOM } from './reels'
import type { LahzaClip, LahzaEpisode, LahzaKeyframe, LahzaSentence, PlaceHighlightResult } from '../../shared/lahza'

/** Reels canvas: what Lahza exports and Instagram / Shorts expect. */
export const REEL_CANVAS = { width: 1080, height: 1920 } as const

type Host = Pick<TsActorHost, 'actor' | 'mcpCall' | 'mediaImporter' | 'openedProject'>

/** One WeftCut MCP call made on the caller's behalf; a refusal throws with the
 *  editor's own message, so the caller reads why, not just that, it failed. */
function call(host: Host, client: string, name: string, args: Record<string, unknown>): Record<string, unknown> {
  const r = host.mcpCall(name, JSON.stringify(args), client)
  if (!r.ok) throw new LahzaError(`weftcut_${r.error.code}`, `${name}: ${r.error.message}`)
  return (r.result.structuredContent ?? {}) as Record<string, unknown>
}

function captionLayerIds(project: Project): Set<string> {
  return new Set(rootComposition(project).tracks.filter((t) => t.role === 'Caption').flatMap((t) => t.layers.map((l) => l.id)))
}

function rootComposition(project: Project) {
  const comp = project.compositions[project.root_id]
  if (!comp) throw new LahzaError('weftcut_no_root', 'The project has no root composition')
  return comp
}

/** Put one Lahza highlight on the open project's A-roll: imports the source
 *  episode's media (joining an import already in flight), turns an empty
 *  project into a 1080×1920 Reel, appends the clip's kept segments after the
 *  last A-roll layer — each scaled to fill the canvas around Lahza's reframe
 *  focus — and lays the clip's Uzbek words on the caption track with exact
 *  word timing. Every write goes through WeftCut's own tools, so each one is
 *  undoable and shows in the Agent activity as `client`. */
export async function placeHighlight(host: Host, engine: LahzaEngine, args: { episode_id: string; clip_id: string; client?: string }): Promise<PlaceHighlightResult> {
  if (!host.openedProject()) throw new LahzaError('NoProjectOpen', 'Open or create a WeftCut project before placing a Lahza highlight')
  const client = args.client ?? 'Lahza'
  const eid = encodeURIComponent(args.episode_id)
  const episode = await engine.request<LahzaEpisode>('GET', `/v1/episodes/${eid}`)
  if (episode.status !== 'ready') throw new LahzaError('lahza_not_ready', `Episode ${args.episode_id} is ${episode.status}; wait for its analysis to finish`)
  const clips = await engine.request<LahzaClip[]>('GET', `/v1/episodes/${eid}/clips`)
  const clip = clips.find((c) => c.id === args.clip_id)
  if (!clip) throw new LahzaError('lahza_clip_not_found', `Episode ${args.episode_id} has no clip ${args.clip_id}`)
  const { sentences } = await engine.request<{ sentences: LahzaSentence[] }>('GET', `/v1/episodes/${eid}/transcript`)
  // Reframe keys are optional: an engine without a vision model has none and
  // the reel is centre-filled.
  const keyframes = await engine.request<LahzaKeyframe[]>('GET', `/v1/episodes/${eid}/clips/${encodeURIComponent(clip.id)}/keyframes`).catch(() => [] as LahzaKeyframe[])

  let comp = rootComposition(host.actor.snapshot())
  const empty = comp.tracks.every((t) => t.layers.length === 0)
  let canvasChanged = false
  if (empty && (comp.width !== REEL_CANVAS.width || comp.height !== REEL_CANVAS.height)) {
    call(host, client, 'update_composition', { patch: { ...REEL_CANVAS } })
    canvasChanged = true
    comp = rootComposition(host.actor.snapshot())
  }
  const canvas = { width: comp.width, height: comp.height }

  const imported = await host.mediaImporter.ensureImported(episode.media.path, { by: mcpActor(client) })
  comp = rootComposition(host.actor.snapshot())
  const track = comp.tracks.find((t) => t.role === 'ARoll') ?? comp.tracks.find((t) => t.role !== 'Caption')
  if (!track) throw new LahzaError('weftcut_no_track', 'The project has no A-roll track')
  const tStart = track.layers.reduce((end, l) => Math.max(end, l.t_end_us), 0)

  const plan = planReel({ clip, sentences, media: episode.media, canvas, t_start_us: tStart, keyframes })
  const layerIds: string[] = []
  for (const seg of plan.segments) {
    const added = call(host, client, 'add_video_layer', {
      media_id: imported.mediaId, track_id: track.id,
      src_in_us: seg.src_in_us, src_out_us: seg.src_out_us, t_start_us: seg.t_start_us, t_end_us: seg.t_end_us,
    })
    const id = String(added.video_layer_id ?? added.layer_id)
    layerIds.push(id)
    if (seg.transform) call(host, client, 'update_layer_params', { layer_id: id, patch: { kind: 'VideoClip', ...seg.transform } })
  }

  let captionTrack: string | null = null
  if (plan.transcript.segments.length > 0) {
    const before = captionLayerIds(host.actor.snapshot())
    const applied = call(host, client, 'apply_transcripts', { transcripts: [plan.transcript], source_layer_ids: [layerIds[0]] })
    captionTrack = typeof applied.caption_track_id === 'string' ? applied.caption_track_id : null
    // A vertical Reel's bottom third is under the platform's own UI: lift
    // this clip's cues (only these — the user's other captions stay put).
    const added = [...captionLayerIds(host.actor.snapshot())].filter((id) => !before.has(id))
    if (canvas.height > canvas.width && added.length > 0) {
      call(host, client, 'restyle_captions', { layer_ids: added, y: Math.round(canvas.height * REEL_CAPTION_BOTTOM) })
    }
  }

  return {
    media_id: imported.mediaId, track_id: track.id, video_layer_ids: layerIds, caption_track_id: captionTrack,
    cue_count: plan.transcript.segments.length, t_start_us: tStart, t_end_us: tStart + plan.duration_us,
    canvas, canvas_changed: canvasChanged,
  }
}
