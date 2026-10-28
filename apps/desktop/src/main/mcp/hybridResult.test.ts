import type { ImportOutcome } from '../state/mediaImport'
import { describe, it, expect } from 'vitest'
import { seededGen } from '../state/ids'
import { blankProject, type MediaItem, type Project } from '../state/model'
import { mediaItemTemplate } from '../state/mutations/media'
import { shapeImportResult } from './hybridResult'

const A = '00000000-0000-0000-0000-0000000000aa'
const B = '00000000-0000-0000-0000-0000000000bb'

function pool(...items: MediaItem[]): Project {
  const p = blankProject(seededGen(), 'h')
  for (const item of items) p.media_pool[item.id] = item
  return p
}
const item = (id: string, hash: string, path_abs = `C:/proj/Media/${id}.mp4`): MediaItem =>
  ({ ...mediaItemTemplate(id, 'Video', 4_000_000), file_hash_blake3: hash, path_abs })
const record = (after: Project, outcome: ImportOutcome) =>
  shapeImportResult(outcome, after).structuredContent as Record<string, unknown>

describe('shapeImportResult', () => {
  it('says nothing more for a new file with content of its own', () => {
    const r = record(pool(item(A, 'h1')), { mediaId: A, disposition: 'added', existing: false, sameContentAs: [] })
    expect(r.media_id).toBe(A)
    expect(r).not.toHaveProperty('existing')
    expect(r).not.toHaveProperty('same_content_as')
  })

  it('marks an item the pool held before the call as existing', () => {
    const held = pool(item(A, 'h1'))
    expect(record(held, { mediaId: A, disposition: 'reused', existing: true, sameContentAs: [] }).existing).toBe(true)
  })

  it('says when the held item was pointed at this file because its own was gone', () => {
    const r = record(pool(item(A, 'h1', 'D:/backup.mp4')), { mediaId: A, disposition: 'relinked', existing: true, sameContentAs: [] })
    expect(r).toMatchObject({ existing: true, relinked: true })
    expect(record(pool(item(A, 'h1')), { mediaId: A, disposition: 'reused', existing: true, sameContentAs: [] })).not.toHaveProperty('relinked')
  })

  it('names the items that already hold the same bytes under another path', () => {
    const r = record(pool(item(B, 'h1'), item(A, 'h1')), { mediaId: A, disposition: 'added', existing: false, sameContentAs: [B] })
    expect(r.same_content_as).toEqual([B])
    expect(r).not.toHaveProperty('existing')
  })
})
