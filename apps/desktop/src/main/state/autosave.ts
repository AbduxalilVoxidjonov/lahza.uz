// apps/desktop/src/main/state/autosave.ts
//
// Auto-save subscriber + periodic Backups/ snapshots. Per docs/data-model.md the
// workspace is the truth: every actor commit eventually lands on disk as
// project.json, no explicit Save. Serialization itself belongs to
// persistence.ts — this module only decides *when* to write. Pure + injected
// (fs / clock / timer / workspace-dir) so the debounce, interval, and gc are
// deterministic in tests. Wired by ts-actor-host: subscribed at backend
// bring-up; project_save → forceFlush.
import type { ActorHandle, ChangeEvent } from './actor'
import type { Project } from './model'
import { PROJECT_FILE } from './persistence'
import { currentEditTrace, measureEditStage, runEditTrace } from '../../shared/editTrace'

/** Quiet window before a write — a 10-event drag coalesces into one. */
const DEBOUNCE_MS = 500
/** Snapshot cadence: a copy to Backups/ once either threshold trips. */
const SNAPSHOT_EVERY_COMMITS = 50
const SNAPSHOT_EVERY_MS = 5 * 60 * 1000
/** Backups/ beyond this many newest files are gc'd after each snapshot. */
const RETAIN_SNAPSHOTS = 20
export const BACKUPS_DIR = 'Backups'

export interface AutosaveFs {
  writeFile(path: string, text: string): void
  exists(path: string): boolean
  copyFile(src: string, dest: string): void
  mkdirp(dir: string): void
  readdir(dir: string): string[]
  rm(path: string): void
}

export interface AutosaveDeps {
  actor: Pick<ActorHandle, 'subscribe' | 'snapshot'>
  fs: AutosaveFs
  /** workspace.current() — null in the blank-boot window before Save As / Open. */
  workspaceDir: () => string | null
  join: (...parts: string[]) => string
  /** serializeProjectToJson (persistence.ts) — injected to keep this module pure. */
  serialize: (p: Project) => string
  now?: () => Date
  debounceMs?: number
  setTimer?: (fn: () => void, ms: number) => ReturnType<typeof setTimeout>
  clearTimer?: (h: ReturnType<typeof setTimeout>) => void
}

export interface AutosaveController {
  start(): void
  forceFlush(): Promise<void>
  stop(): void
}

export function createAutosave(deps: AutosaveDeps): AutosaveController {
  const now = deps.now ?? (() => new Date())
  const debounceMs = deps.debounceMs ?? DEBOUNCE_MS
  const setTimer = deps.setTimer ?? ((fn, ms) => setTimeout(fn, ms))
  const clearTimer = deps.clearTimer ?? ((h) => clearTimeout(h))

  let unsubscribe: (() => void) | null = null
  let pending: ReturnType<typeof setTimeout> | null = null
  let commitsSinceSnapshot = 0
  let lastSnapshotAtMs = now().getTime()
  let pendingTraceId: string | undefined
  let traceScheduledAt = 0

  /** ISO-8601, no colons/dashes/dots — sorts lexicographically == chronologically
   *  (Windows-filename-safe). */
  function stamp(): string {
    return now().toISOString().replace(/[-:.]/g, '')
  }

  function persist(ws: string): void {
    const json = measureEditStage('serialize', () => deps.serialize(deps.actor.snapshot()))
    currentEditTrace()?.fact('jsonChars', json.length)
    measureEditStage('write_file', () => deps.fs.writeFile(deps.join(ws, PROJECT_FILE), json))
  }

  function takeSnapshot(ws: string): void {
    const src = deps.join(ws, PROJECT_FILE)
    if (!deps.fs.exists(src)) return // defensive: nothing to copy yet
    const backups = deps.join(ws, BACKUPS_DIR)
    try {
      deps.fs.mkdirp(backups)
      deps.fs.copyFile(src, deps.join(backups, `${stamp()}.json`))
      gcSnapshots(backups)
    } catch { /* best-effort; a setTimeout-callback throw would be an unhandled rejection */ }
  }

  function gcSnapshots(backups: string): void {
    const names = deps.fs.readdir(backups).filter((n) => n.endsWith('.json'))
    names.sort((a, b) => (a < b ? 1 : a > b ? -1 : 0)) // descending: newest (largest) first
    for (const stale of names.slice(RETAIN_SNAPSHOTS)) {
      try { deps.fs.rm(deps.join(backups, stale)) } catch { /* logged-only in prod; ignore */ }
    }
  }

  /** Debounced write: persist, then snapshot if the commit/time threshold passed. */
  function flushDebounced(): void {
    pending = null
    const traceId = pendingTraceId
    pendingTraceId = undefined
    runEditTrace(traceId, 'main.autosave', () => {
      if (traceId) currentEditTrace()?.fact('timerLateMs', Math.max(0, performance.now() - traceScheduledAt - debounceMs))
      flushDebouncedInner()
    })
  }

  function flushDebouncedInner(): void {
    const ws = deps.workspaceDir()
    if (ws === null) return // no workspace yet — edits stay dirty for the next cycle
    persist(ws)
    // One per debounce CYCLE (a flurry coalesced into one quiet-window write),
    // NOT per raw actor commit.
    commitsSinceSnapshot += 1
    if (commitsSinceSnapshot >= SNAPSHOT_EVERY_COMMITS || now().getTime() - lastSnapshotAtMs >= SNAPSHOT_EVERY_MS) {
      measureEditStage('backup_and_gc', () => takeSnapshot(ws))
      commitsSinceSnapshot = 0
      lastSnapshotAtMs = now().getTime()
    }
  }

  function onChange(_e: ChangeEvent): void {
    if (pending !== null) clearTimer(pending)
    // A coalesced save belongs to its latest edit; never attribute a later,
    // untraced edit to the previous drag. IDs are session-only, never persisted.
    pendingTraceId = currentEditTrace()?.id
    if (pendingTraceId) traceScheduledAt = performance.now()
    pending = setTimer(flushDebounced, debounceMs)
  }

  return {
    start() {
      if (unsubscribe) return
      unsubscribe = deps.actor.subscribe(onChange)
    },
    /** Flush + snapshot right now, skipping the debounce (Cmd-S / quit gate). The
     *  force path always snapshots and resets the counters. */
    async forceFlush(): Promise<void> {
      if (pending !== null) { clearTimer(pending); pending = null }
      const traceId = pendingTraceId
      pendingTraceId = undefined
      runEditTrace(traceId, 'main.force_save', () => {
        const ws = deps.workspaceDir()
        if (ws === null) return
        persist(ws)
        measureEditStage('backup_and_gc', () => takeSnapshot(ws))
        commitsSinceSnapshot = 0
        lastSnapshotAtMs = now().getTime()
      })
    },
    stop() {
      pendingTraceId = undefined
      if (pending !== null) { clearTimer(pending); pending = null }
      if (unsubscribe) { unsubscribe(); unsubscribe = null }
    },
  }
}
