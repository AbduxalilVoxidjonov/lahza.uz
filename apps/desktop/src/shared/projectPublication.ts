/** Renderer publication identity, scoped to one main-process lifetime.
 * A session changes when the workspace is replaced (even by the same project).
 * Revision advances on every published actor change, including undo and jobs.
 * Neither number is a persisted project version or a history cursor. */
export interface ProjectVersion { session: number; revision: number }

/** A complete, atomically versioned projection. Null means actually closed. */
export interface ProjectPublication<T> { version: ProjectVersion; summary: T | null }

/** Existing command value plus a view barrier. A receipt may include concurrent
 * commits completed while an async operation ran; it never claims persistence. */
export interface PublishedResult<T> { value: T; publication: ProjectVersion | null }
