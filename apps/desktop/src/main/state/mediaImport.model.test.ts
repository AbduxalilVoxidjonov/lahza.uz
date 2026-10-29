// The import contract, checked against a model file system rather than against
// the cases found so far: whatever happened to the files before, the item an
// import answers holds, at its own path, the bytes the source held.
import { describe, expect, it } from 'vitest'
import fc from 'fast-check'
import { createActor } from './actor'
import { seededGen } from './ids'
import { blankProject, type MediaItem } from './model'
import { mediaItemTemplate } from './mutations/media'
import { createMediaImporter, type MediaImportDeps } from './mediaImport'
import { applyWorkspacePathsEvent } from './jobs-writeback'

const PROJECT = '/proj'
/** Outside files an import may name, and copies the workspace copy writes. */
const PATHS = ['/footage/a.mp4', '/footage/b.mp4', '/backup/a.mp4', '/proj/Media/in-place.mp4'] as const
/** Files something outside the app may change: the copies too. */
const WRITABLE = [...PATHS, '/proj/Media/copy-1.mp4', '/proj/Media/copy-2.mp4'] as const
/** Contents, as their hashes. Two share a size, so a size alone matches both. */
const CONTENTS = ['x'.repeat(64), 'y'.repeat(64), 'z'.repeat(64)] as const
const SIZE: Record<string, number> = { [CONTENTS[0]]: 1000, [CONTENTS[1]]: 1000, [CONTENTS[2]]: 2000 }

type File = { content: string; mtime: number }
type Op =
  | { kind: 'import'; path: string }
  | { kind: 'write'; path: string; content: string; keepMtime: boolean }
  | { kind: 'delete'; path: string }
  | { kind: 'copy' }

const op: fc.Arbitrary<Op> = fc.oneof(
  { arbitrary: fc.record({ kind: fc.constant('import' as const), path: fc.constantFrom(...PATHS) }), weight: 3 },
  fc.record({ kind: fc.constant('write' as const), path: fc.constantFrom(...WRITABLE), content: fc.constantFrom(...CONTENTS), keepMtime: fc.boolean() }),
  fc.record({ kind: fc.constant('delete' as const), path: fc.constantFrom(...WRITABLE) }),
  { arbitrary: fc.constant({ kind: 'copy' as const }), weight: 2 },
)

/** A project host over a file system it shares with the test: the probe and
 *  the hash read the files as they are, and the workspace copy, queued until a
 *  `copy` op runs it, writes one and reports through the real write-back. */
function host(workspace: boolean) {
  const files = new Map<string, File>()
  let clock = 1, ids = 0, copies = 0
  const queued: { mediaId: string; source: string }[] = []
  /** Every hash an item has held once real: none may ever change. */
  const settled = new Map<string, string>()
  const idGen = seededGen()
  const actor = createActor({ initial: blankProject(idGen, 'h'), idGen, clock: () => '<TS>' })
  const read = (p: string) => {
    const f = files.get(p)
    if (!f) throw new Error(`ENOENT ${p}`)
    return f
  }
  const deps: MediaImportDeps = {
    actor,
    compute: {
      async probeMedia(p) {
        const f = read(p)
        const id = `00000000-0000-0000-0000-${String(++ids).padStart(12, '0')}`
        const item: MediaItem = { ...mediaItemTemplate(id, 'Video', 1_000_000), path_abs: p,
          file_hash_blake3: `pending-${id}`, file_size: SIZE[f.content], file_mtime: f.mtime }
        return JSON.stringify(item)
      },
      async hashMediaSource(p) { return read(p).content },
    },
    enqueueDerivatives: async () => {},
    enqueueWorkspaceCopy: async (mediaId, source) => { queued.push({ mediaId, source }) },
    workspaceDir: () => (workspace ? PROJECT : null),
    statPath: (p) => (files.has(p) ? { kind: 'file', readable: true } : p === `${PROJECT}/Media` && workspace ? { kind: 'directory', readable: true } : null),
    fileKey: (p) => (files.has(p) || p === `${PROJECT}/Media` ? p : null),
    platform: 'linux',
  }
  const importer = createMediaImporter(deps)
  return {
    actor,
    async run(o: Op): Promise<void> {
      if (o.kind === 'write') {
        // An overwrite may keep the second-resolution mtime it had.
        const before = files.get(o.path)
        files.set(o.path, { content: o.content, mtime: o.keepMtime && before ? before.mtime : ++clock })
        return
      }
      if (o.kind === 'delete') { files.delete(o.path); return }
      if (o.kind === 'copy') {
        // As the native copy does: copy whatever the source holds NOW under
        // Media/, hash what it wrote, and report through the write-back.
        const job = queued.shift()
        const f = job && files.get(job.source)
        if (!job || !f) return
        const rel = `Media/copy-${++copies}.mp4`
        files.set(`${PROJECT}/${rel}`, { ...f, mtime: ++clock })
        applyWorkspacePathsEvent(actor, { media_id: job.mediaId, path_abs: `${PROJECT}/${rel}`, path_rel: rel,
          file_hash_blake3: f.content, file_size: SIZE[f.content], file_mtime: clock }, undefined, p => files.delete(p))
        return
      }
      const source = files.get(o.path)
      if (!source) return
      const { mediaId } = await importer.ensureImported(o.path)
      const item = actor.snapshot().media_pool[mediaId]
      expect(item.file_hash_blake3, `${mediaId} records the source's bytes`).toBe(source.content)
      expect(files.get(item.path_abs)?.content, `${mediaId}'s file ${item.path_abs} holds the source's bytes`).toBe(source.content)
    },
    /** No item's real hash ever changes: its layers, derivatives and cached
     *  answers all name those bytes. */
    checkSettled(): void {
      for (const m of Object.values(actor.snapshot().media_pool)) {
        if (m.file_hash_blake3.startsWith('pending-')) continue
        expect(m.file_hash_blake3, `${m.id} keeps the bytes it was settled with`).toBe(settled.get(m.id) ?? m.file_hash_blake3)
        settled.set(m.id, m.file_hash_blake3)
      }
    },
  }
}

describe('ensureImported against a model file system', () => {
  it.each([true, false])('answers an item whose own file holds the source bytes (workspace: %s)', async (workspace) => {
    await fc.assert(fc.asyncProperty(fc.array(op, { maxLength: 14 }), async (ops) => {
      const h = host(workspace)
      for (const o of ops) { await h.run(o); h.checkSettled() }
    }), { numRuns: 2000 })
  })

  // The audit's case, kept as a named example of the property above.
  it('does not answer an item whose file was overwritten when its backup is imported', async () => {
    const h = host(true)
    await h.run({ kind: 'write', path: '/footage/a.mp4', content: CONTENTS[0], keepMtime: false })
    await h.run({ kind: 'import', path: '/footage/a.mp4' })
    await h.run({ kind: 'copy' })
    const [copy] = Object.values(h.actor.snapshot().media_pool).map(m => m.path_abs)
    await h.run({ kind: 'write', path: copy, content: CONTENTS[1], keepMtime: true })
    await h.run({ kind: 'write', path: '/backup/a.mp4', content: CONTENTS[0], keepMtime: false })
    await h.run({ kind: 'import', path: '/backup/a.mp4' })
  })
  // Reproduced in the app: the source re-exported under its own name while
  // its copy waited behind others.
  it('keeps an item on its recorded bytes when its source changes before the copy', async () => {
    const h = host(true)
    await h.run({ kind: 'write', path: '/footage/a.mp4', content: CONTENTS[0], keepMtime: false })
    await h.run({ kind: 'import', path: '/footage/a.mp4' })
    h.checkSettled()
    await h.run({ kind: 'write', path: '/footage/a.mp4', content: CONTENTS[1], keepMtime: false })
    await h.run({ kind: 'copy' })
    h.checkSettled()
    expect(Object.values(h.actor.snapshot().media_pool)[0].path_abs).toBe('/footage/a.mp4')
  })
})
