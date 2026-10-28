// apps/desktop/src/main/mcp/hybridResult.ts
//
// The MCP-side shape of a hybrid tool's answer. `runHybrid` keeps its STRING
// contract — the renderer's IPC wrappers parse it (`renderer/ipc/index.ts`) —
// and this reads the committed record back for the agent, so the two surfaces
// share the write and differ only in how they report it. `after` is the actor
// snapshot once the call has committed, `before` the one it started from.
import type { Project } from '../state/model.js'
import { toolText, type ToolResultJson } from '../state/mcp-commands.js'
import { mediaRecord, toolRecord } from '../state/mcp-results.js'

export function shapeHybridResult(name: string, result: unknown, after: Project, before: Project): ToolResultJson {
  const text = String(result)
  if (name === 'import_media') return toolRecord(importRecord(text, after, before))
  // apply_subtitles / synthesize_speech / auto_split_by_shot / remove_pauses
  // answer a JSON object as a string; anything else stays the text it was.
  try {
    const v = JSON.parse(text) as unknown
    if (v !== null && typeof v === 'object' && !Array.isArray(v)) return toolRecord(v as Record<string, unknown>)
  } catch { /* not JSON */ }
  return toolText(text)
}

/** An import's record, saying when the pool already held the file
 *  (`existing`) or holds its bytes under another path (`same_content_as`). */
function importRecord(id: string, after: Project, before: Project): object {
  const record = mediaRecord(after, id)
  if (!record) return { media_id: id }
  if (before.media_pool[id]) return { ...record, existing: true }
  const hash = after.media_pool[id].file_hash_blake3
  const same = Object.values(after.media_pool).filter((m) => m.id !== id && m.file_hash_blake3 === hash).map((m) => m.id)
  return same.length > 0 ? { ...record, same_content_as: same } : record
}
