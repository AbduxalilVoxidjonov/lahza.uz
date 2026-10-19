// The renderer's taskbar progress request (`renderer/app/useExportFlow.ts`,
// statuses from `renderer/bridge/window.ts` `ProgressBarStatus`) as Electron's
// `BrowserWindow.setProgressBar(progress, { mode })` arguments.
//
// Electron's progress is a fraction: below 0 removes the bar, above 1 is
// indeterminate where the platform has no mode for it. `mode` is honoured on
// Windows only; macOS and Linux read the fraction alone, which is why every
// status also picks a fraction that means the same thing without its mode.
//
// Untrusted input from the renderer: anything malformed clears the bar rather
// than throwing in the IPC handler.

export type TaskbarMode = 'none' | 'normal' | 'indeterminate' | 'error' | 'paused'

export function taskbarProgressArgs(bar: unknown): { progress: number; mode: TaskbarMode } {
  const b = (bar ?? {}) as { status?: unknown; progress?: unknown }
  const percent = typeof b.progress === 'number' && Number.isFinite(b.progress)
    ? Math.min(100, Math.max(0, b.progress))
    : 0
  switch (b.status) {
    case 'normal': return { progress: percent / 100, mode: 'normal' }
    case 'indeterminate': return { progress: 2, mode: 'indeterminate' }
    case 'error': return { progress: percent / 100, mode: 'error' }
    case 'paused': return { progress: percent / 100, mode: 'paused' }
    default: return { progress: -1, mode: 'none' }
  }
}
