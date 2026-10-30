import type { LahzaEngine } from './engine'
import { LahzaError } from './engine'
import { placeHighlight } from './place'
import type { LahzaClip, LahzaEpisode, LahzaJob, LahzaSentence, LahzaStatus, PlaceHighlightResult } from '../../shared/lahza'
import type { TsActorHost } from '../state/ts-actor-host'

/** The Lahza operations WeftCut offers — one surface behind both the Lahza
 *  dock panel (IPC) and the `lahza_*` MCP tools, so a person and an agent
 *  reach the same engine the same way. */

/** Every Lahza episode imported from WeftCut lives in this Lahza project, so
 *  they stay together in Lahza Studio's library too. */
export const LAHZA_PROJECT_NAME = 'WeftCut'

export interface AnalyzeArgs { path: string; title?: string; focus?: string; num_speakers?: number; force_lite?: boolean }
export interface ExportArgs {
  episode_id: string; clip_id: string; out_dir: string
  orthography?: 'official' | 'ascii' | 'new'; script?: 'latin' | 'cyrillic'
  platform?: 'instagram_reels' | 'youtube_shorts' | 'youtube_video' | 'custom'; allow_no_subs?: boolean
}

const enc = encodeURIComponent

export class LahzaService {
  private projectId: Promise<string> | null = null

  constructor(private readonly engine: LahzaEngine, private readonly host: () => TsActorHost | null) {}

  status(): LahzaStatus { return this.engine.status() }

  async start(): Promise<LahzaStatus> {
    await this.engine.ensureStarted()
    return this.engine.status()
  }

  /** First-run model setup state (`GET /v1/setup`). Installing models is
   *  Lahza Studio's own onboarding: it is a multi-GB download the user
   *  consents to there, never one an agent starts. */
  setup(): Promise<unknown> { return this.engine.request('GET', '/v1/setup') }

  private lahzaProject(): Promise<string> {
    if (!this.projectId) {
      this.projectId = (async () => {
        const projects = await this.engine.request<Array<{ id: string; name: string }>>('GET', '/v1/projects')
        const found = projects.find((p) => p.name === LAHZA_PROJECT_NAME)
        if (found) return found.id
        return (await this.engine.request<{ id: string }>('POST', '/v1/projects', { name: LAHZA_PROJECT_NAME })).id
      })().catch((e: unknown) => { this.projectId = null; throw e })
    }
    return this.projectId
  }

  /** Import a long video into Lahza and start its analysis (VAD → Uzbek ASR →
   *  alignment → diarization → highlight scoring). Answers at once with the
   *  episode and the analysis job; poll `job()` until it is done. */
  async analyze(args: AnalyzeArgs): Promise<{ episode_id: string; job: LahzaJob }> {
    if (typeof args.path !== 'string' || args.path.length === 0) throw new LahzaError('invalid_params', 'path must be an absolute path to a local video')
    const project_id = await this.lahzaProject()
    return this.engine.request('POST', '/v1/media:import', { project_id, ...args })
  }

  job(id: string): Promise<LahzaJob> { return this.engine.request('GET', `/v1/jobs/${enc(id)}`) }
  cancelJob(id: string): Promise<unknown> { return this.engine.request('POST', `/v1/jobs/${enc(id)}:cancel`) }

  async episodes(): Promise<LahzaEpisode[]> {
    return this.engine.request('GET', `/v1/projects/${enc(await this.lahzaProject())}/episodes`)
  }

  /** The episode and its highlight candidates, best first. */
  async highlights(episodeId: string): Promise<{ episode: LahzaEpisode; clips: LahzaClip[] }> {
    const [episode, clips] = await Promise.all([
      this.engine.request<LahzaEpisode>('GET', `/v1/episodes/${enc(episodeId)}`),
      this.engine.request<LahzaClip[]>('GET', `/v1/episodes/${enc(episodeId)}/clips`),
    ])
    return { episode, clips: [...clips].sort((a, b) => b.score - a.score) }
  }

  transcript(episodeId: string): Promise<{ sentences: LahzaSentence[] }> {
    return this.engine.request('GET', `/v1/episodes/${enc(episodeId)}/transcript`)
  }

  /** Accept, reject or retitle a highlight in Lahza's own record. */
  updateClip(episodeId: string, clipId: string, patch: { title?: string; status?: string; start_ms?: number; end_ms?: number }): Promise<LahzaClip> {
    return this.engine.request('PATCH', `/v1/episodes/${enc(episodeId)}/clips/${enc(clipId)}`, patch)
  }

  /** Render a finished Reel with Lahza's own exporter: 1080×1920 MP4 with
   *  burned-in Uzbek karaoke subtitles, plus SRT/VTT, caption text and cover. */
  exportClip(args: ExportArgs): Promise<LahzaJob> {
    const { episode_id, clip_id, ...body } = args
    if (typeof body.out_dir !== 'string' || body.out_dir.length === 0) throw new LahzaError('invalid_params', 'out_dir must be an absolute folder path')
    return this.engine.request('POST', `/v1/episodes/${enc(episode_id)}/clips/${enc(clip_id)}:export`, body)
  }

  /** Put a highlight on the open WeftCut timeline (see `placeHighlight`). */
  place(args: { episode_id: string; clip_id: string; client?: string }): Promise<PlaceHighlightResult> {
    const host = this.host()
    if (!host) throw new LahzaError('weftcut_not_ready', 'The editor is not started yet')
    return placeHighlight(host, this.engine, args)
  }

  stop(): void { this.engine.stop() }
}
