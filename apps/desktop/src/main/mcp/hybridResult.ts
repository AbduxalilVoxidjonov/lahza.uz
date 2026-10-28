// apps/desktop/src/main/mcp/hybridResult.ts
//
// MCP adapts the import module's explicit outcome and the committed record.
// Other hybrid tools retain their serialized-result contract.
import type { ImportOutcome } from '../state/mediaImport'
import type { Project } from '../state/model.js'
import { toolText, type ToolResultJson } from '../state/mcp-commands.js'
import { mediaRecord, toolRecord } from '../state/mcp-results.js'

export function shapeHybridResult(name: string, result: unknown, after: Project): ToolResultJson {
  if (name === 'import_media') return toolRecord(importRecord(result as ImportOutcome, after))
  const text = String(result)
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
function importRecord(outcome: ImportOutcome, after: Project): object {
  const record = mediaRecord(after, outcome.mediaId)
  if (!record) return { media_id: outcome.mediaId }
  if (outcome.existing) return { ...record, existing: true }
  return outcome.sameContentAs.length > 0 ? { ...record, same_content_as: outcome.sameContentAs } : record
}
