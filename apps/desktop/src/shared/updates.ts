export type UpdateStatus = {
  phase: 'disabled' | 'idle' | 'checking' | 'current' | 'available' | 'downloading' | 'ready' | 'restarting' | 'error'
  version?: string
  percent?: number
}

export type UpdateRestartResult = 'restarting' | 'not-ready' | 'save-failed'
export type UpdateDownloadResult = 'ready' | 'not-ready' | 'download-failed'
/** null means a normal launch; { path: null } restores the start screen. */
export type UpdateResume = { path: string | null } | null
