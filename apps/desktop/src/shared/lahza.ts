/** Wire types of the Lahza engine (Lahza Studio's offline Uzbek ASR +
 *  highlight sidecar), shared by the main-process service and the Lahza dock
 *  panel. Times from the engine are source-absolute milliseconds. */

export interface LahzaWord { text: string; start_ms: number; end_ms: number; conf?: number | null; speaker?: string | null }
export interface LahzaSentence { id: number | string; start_ms: number; end_ms: number; speaker?: string | null; text: string; words: LahzaWord[] }
export interface LahzaClip {
  id: string; start_ms: number; end_ms: number; title: string; caption?: string; hashtags?: string[]
  kind?: string | null; score: number; reason?: string; status?: string; source?: string
  cuts?: Array<[number, number]>; hook?: { start_ms: number; end_ms: number } | null
}
export interface LahzaKeyframe { t_ms: number; layout: string; cx: number; cy: number; zoom: number; lane?: string; source?: string }
export interface LahzaMedia { duration_ms: number; fps?: number | null; width: number; height: number; path: string }
export interface LahzaEpisode { id: string; title: string; status: string; project_dir?: string; media: LahzaMedia; highlight_mode?: string }

export interface LahzaJob {
  id: string; kind: string; status: 'queued' | 'running' | 'done' | 'failed' | 'cancelled'
  progress: number; stage: string | null; error: string | null; result: unknown; meta?: Record<string, unknown>
}

export type LahzaStatus =
  | { state: 'unavailable'; reason: string }
  | { state: 'stopped' }
  | { state: 'starting' }
  | { state: 'ready'; port: number; version: string }
  | { state: 'failed'; error: string }

export interface PlaceHighlightResult {
  media_id: string
  track_id: string
  video_layer_ids: string[]
  caption_track_id: string | null
  cue_count: number
  t_start_us: number
  t_end_us: number
  canvas: { width: number; height: number }
  canvas_changed: boolean
}

/** What every `lahza:*` IPC channel answers: errors cross as records so the
 *  panel keeps the engine's code, not just Electron's flattened message. */
export type LahzaResult<T> = { ok: true; value: T } | { ok: false; error: { code: string; message: string } }

export interface LahzaApi {
  status(): Promise<LahzaResult<LahzaStatus>>
  start(): Promise<LahzaResult<LahzaStatus>>
  analyze(args: { path: string; force_lite?: boolean }): Promise<LahzaResult<{ episode_id: string; job: LahzaJob }>>
  job(id: string): Promise<LahzaResult<LahzaJob>>
  cancelJob(id: string): Promise<LahzaResult<unknown>>
  episodes(): Promise<LahzaResult<LahzaEpisode[]>>
  highlights(episodeId: string): Promise<LahzaResult<{ episode: LahzaEpisode; clips: LahzaClip[] }>>
  place(episodeId: string, clipId: string): Promise<LahzaResult<PlaceHighlightResult>>
  exportClip(episodeId: string, clipId: string, outDir: string): Promise<LahzaResult<LahzaJob>>
}
