/// Message of the rejection a QUEUED motif capture receives when a newer
/// request carrying the same coalesce key replaces it
/// (`main/motif/capture.ts` — the serial capture chain). Crosses the IPC
/// boundary as a plain message (error classes don't survive it), so renderer
/// callers match on this string to tell "superseded — not a failure" from a
/// real capture error.
export const CAPTURE_SUPERSEDED_MESSAGE = 'motif capture superseded by a newer request'

/// A bounded CDP step (page load, ready probe, setup, frame, screenshot) ran
/// past its deadline. Main-process only: the class identity lets the capture
/// host and the capture service tell "the renderer hung" from "the Motif's
/// script threw" and from "the shared-texture transport failed", three
/// failures with three different recoveries (`main/motif/capture.ts`).
export class MotifCaptureTimeoutError extends Error {
  constructor(ms: number, label: string) {
    super(`motif capture timed out after ${ms}ms: ${label}`)
    this.name = 'MotifCaptureTimeoutError'
  }
}
