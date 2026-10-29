// apps/desktop/src/main/state/sourceFiles.ts
//
// Whether a pool item's file still holds the bytes it records (ADR 0153).
// Files under Media/ are the app's own and never rewritten once there; a file
// that changed anyway is unavailable, like a missing one, rather than read as
// the item. One stat screens every item: a size that differs settles it, an
// mtime that differs (a project folder copied without its times, a touch) is
// settled by reading the bytes once, in the background and one file at a time.
import type { MediaItem } from './model'

export type SourceState = 'present' | 'missing' | 'changed'

export interface SourceFilesDeps {
  /** A regular file's size and whole-second mtime (native `stat_file`'s
   *  units); null when nothing readable is there. */
  stat(path: string): { size: number; mtimeSecs: number } | null
  /** BLAKE3 hex of a file's contents. */
  hash(path: string): Promise<string>
  /** The bytes were read and are the item's: record the mtime they now have,
   *  so the screen passes again without reading them. */
  confirmed(item: MediaItem, mtimeSecs: number): void
  /** A background read settled a state the screen could not. */
  settled(): void
}

export interface SourceFiles {
  /** What the item's file is now, from a stat. A file whose mtime alone
   *  differs reads as present until its bytes are read; that read starts
   *  here. */
  state(item: MediaItem): SourceState
  /** The same, waiting for that read: what a reader of the bytes asks. */
  settle(item: MediaItem): Promise<SourceState>
}

export function createSourceFiles(deps: SourceFilesDeps): SourceFiles {
  // Settled reads, by the item's record and the file's stat at the read: a
  // file that changes again, or an item that moves or rehashes, is read again.
  const verdicts = new Map<string, 'present' | 'changed'>()
  const reads = new Map<string, Promise<SourceState>>()
  let queue: Promise<unknown> = Promise.resolve()

  function screen(item: MediaItem): { state: SourceState } | { key: string; mtimeSecs: number } {
    const facts = deps.stat(item.path_abs)
    if (facts === null) return { state: 'missing' }
    // Still importing: there is no settled hash to hold.
    if (item.file_hash_blake3.startsWith('pending-')) return { state: 'present' }
    if (facts.size !== item.file_size) return { state: 'changed' }
    if (facts.mtimeSecs === item.file_mtime) return { state: 'present' }
    const key = [item.id, item.path_abs, item.file_hash_blake3, facts.size, facts.mtimeSecs].join('\n')
    const verdict = verdicts.get(key)
    return verdict ? { state: verdict } : { key, mtimeSecs: facts.mtimeSecs }
  }

  function read(item: MediaItem, key: string, mtimeSecs: number): Promise<SourceState> {
    const pending = reads.get(key)
    if (pending) return pending
    const run = async (): Promise<SourceState> => {
      let verdict: 'present' | 'changed'
      // A file that cannot be read now is settled by the next stat.
      try { verdict = (await deps.hash(item.path_abs)) === item.file_hash_blake3 ? 'present' : 'changed' }
      catch { return 'missing' }
      verdicts.set(key, verdict)
      if (verdict === 'present') deps.confirmed(item, mtimeSecs)
      deps.settled()
      return verdict
    }
    const answer = queue.then(run)
    queue = answer.catch(() => {})
    reads.set(key, answer)
    void answer.finally(() => reads.delete(key))
    return answer
  }

  return {
    state(item) {
      const s = screen(item)
      if ('state' in s) return s.state
      void read(item, s.key, s.mtimeSecs)
      return 'present'
    },
    async settle(item) {
      const s = screen(item)
      return 'state' in s ? s.state : read(item, s.key, s.mtimeSecs)
    },
  }
}
