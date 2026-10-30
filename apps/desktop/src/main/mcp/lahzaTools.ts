import type { CatalogTool } from './mcpCatalog'
import { lahzaService } from '../lahza/registry'
import { LahzaError } from '../lahza/engine'

/** The `lahza_*` tools: Lahza Studio's offline Uzbek pipeline (ASR, highlight
 *  scoring, 9:16 reframe, karaoke-subtitle export) as an MCP surface, served
 *  in TS by the Lahza sidecar. Every tool but `lahza_place_highlight` reads or
 *  writes only Lahza's own library, so they answer with no project open. */

const schema = (properties: Record<string, unknown>, required: string[] = []) => ({ type: 'object', properties, required, additionalProperties: false })
const definition = (name: string, description: string, inputSchema: Record<string, unknown>, readOnlyHint: boolean, idempotentHint: boolean): CatalogTool & { description: string; inputSchema: Record<string, unknown> } => ({
  name, description, inputSchema, annotations: readOnlyHint ? { readOnlyHint: true } : { readOnlyHint: false, destructiveHint: false, idempotentHint },
})
const episodeId = { type: 'string', minLength: 1, description: 'Lahza episode id.' }
const clipId = { type: 'string', minLength: 1, description: 'Clip id from lahza_list_highlights.' }

export const LAHZA_TOOL_DEFS = [
  definition('lahza_status', 'Start the Lahza engine (offline Uzbek ASR + highlights) if needed; return its state, model setup and analyzed episodes.', schema({}), true, true),
  definition('lahza_analyze_video', 'Import a long local video into Lahza and start Uzbek ASR + highlight analysis. Returns { episode_id, job }; poll lahza_get_job.', schema({
    path: { type: 'string', minLength: 1, description: 'Absolute video path.' },
    force_lite: { type: 'boolean', description: 'Skip the local LLM: faster, less semantic.' },
  }, ['path']), false, false),
  definition('lahza_get_job', 'Read a Lahza analyze or export job: status, progress 0..1, stage, error, result.', schema({ job_id: { type: 'string', minLength: 1, description: 'Job id.' } }, ['job_id']), true, true),
  definition('lahza_list_highlights', 'An episode and its highlight clips, best first (source ms, title, kind, score, reason, cuts, hook).', schema({ episode_id: episodeId }, ['episode_id']), true, true),
  definition('lahza_get_transcript', "An episode's Uzbek transcript: sentences with speaker and word timings in source ms.", schema({ episode_id: episodeId }, ['episode_id']), true, true),
  definition('lahza_place_highlight', 'Append a highlight to the A-roll as a reframed 9:16 Reel (an empty project becomes 1080x1920) with word-timed Uzbek captions. Returns layer ids and span.', schema({ episode_id: episodeId, clip_id: clipId }, ['episode_id', 'clip_id']), false, false),
  definition('lahza_export_reel', "Render a highlight with Lahza's exporter: 1080x1920 MP4 with burned-in Uzbek subtitles, SRT, cover. Returns a job.", schema({
    episode_id: episodeId, clip_id: clipId,
    out_dir: { type: 'string', minLength: 1, description: 'Absolute output folder.' },
    orthography: { enum: ['official', 'ascii', 'new'], description: "Apostrophe: oʻ, o' or ö." },
    script: { enum: ['latin', 'cyrillic'], description: 'Subtitle script.' },
  }, ['episode_id', 'clip_id', 'out_dir']), false, false),
]

export const LAHZA_TOOLS: ReadonlySet<string> = new Set(LAHZA_TOOL_DEFS.map((d) => d.name))

/** The Lahza tools that answer with no WeftCut project open. */
export const LAHZA_APP_SCOPE_TOOLS: readonly string[] = LAHZA_TOOL_DEFS.map((d) => d.name).filter((n) => n !== 'lahza_place_highlight')

/** Run one `lahza_*` tool. Throws `LahzaError` (code + message) on refusal. */
export async function runLahzaTool(name: string, args: Record<string, unknown>, client: string | undefined): Promise<Record<string, unknown>> {
  const service = lahzaService()
  if (!service) throw new LahzaError('lahza_unavailable', 'The Lahza engine is not installed in this build')
  const str = (k: string) => {
    const v = args[k]
    if (typeof v !== 'string' || v.length === 0) throw new LahzaError('invalid_params', `${k} must be a nonempty string`)
    return v
  }
  switch (name) {
    case 'lahza_status': {
      const status = service.status()
      if (status.state === 'unavailable') return { status }
      const started = await service.start()
      const [setup, episodes] = await Promise.all([service.setup(), service.episodes()])
      return { status: started, setup, episodes }
    }
    case 'lahza_analyze_video':
      return await service.analyze({ path: str('path'), force_lite: args.force_lite === true })
    case 'lahza_get_job':
      return { job: await service.job(str('job_id')) }
    case 'lahza_list_highlights':
      return await service.highlights(str('episode_id'))
    case 'lahza_get_transcript':
      return await service.transcript(str('episode_id'))
    case 'lahza_place_highlight':
      return { ...await service.place({ episode_id: str('episode_id'), clip_id: str('clip_id'), client }) }
    case 'lahza_export_reel':
      return { job: await service.exportClip({ episode_id: str('episode_id'), clip_id: str('clip_id'), out_dir: str('out_dir'),
        orthography: args.orthography as 'official' | 'ascii' | 'new' | undefined, script: args.script as 'latin' | 'cyrillic' | undefined }) }
    default:
      throw new LahzaError('not_found', `Unknown Lahza tool ${name}`)
  }
}
