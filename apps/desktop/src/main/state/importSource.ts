// apps/desktop/src/main/state/importSource.ts
//
// Where an import's source already stands: the pool item whose file it is, or
// a place under the project's Media/ folder, where the import copy would have
// put it. Pure but for the injected realpath; `platform` picks the path rules,
// so a test on Linux can speak Windows paths.
import path from 'node:path'
import type { MediaItem } from './model'

/** The folder the import copy writes into (native `jobs/import.rs` MEDIA_DIR). */
const MEDIA_DIR = 'Media'

const pathLib = (platform: NodeJS.Platform) => (platform === 'win32' ? path.win32 : path.posix)

/** One spelling per file: resolved, and folded for case and Unicode
 *  normalization on the platforms whose default volumes ignore both. */
function pathKey(p: string, platform: NodeJS.Platform): string {
  const resolved = pathLib(platform).resolve(p)
  return platform === 'win32' || platform === 'darwin' ? resolved.normalize('NFC').toLowerCase() : resolved
}

/** The pool item whose file `source` is. Both sides go through realpath, so a
 *  link, another spelling or the source of a copy still in flight all match. */
export function pooledItemFor(
  pool: Record<string, MediaItem>, source: string,
  realPath: (p: string) => string, platform: NodeJS.Platform,
): MediaItem | null {
  const key = pathKey(realPath(source), platform)
  for (const item of Object.values(pool)) if (pathKey(realPath(item.path_abs), platform) === key) return item
  return null
}

/** `source`'s path relative to the project folder when it already sits under
 *  the project's Media/ folder, else null. */
export function mediaFolderPath(
  workspaceDir: string, source: string,
  realPath: (p: string) => string, platform: NodeJS.Platform,
): string | null {
  const lib = pathLib(platform)
  const media = realPath(lib.join(workspaceDir, MEDIA_DIR))
  const file = realPath(source)
  const folded = lib.relative(pathKey(media, platform), pathKey(file, platform))
  if (folded === '' || folded === '..' || folded.startsWith(`..${lib.sep}`) || lib.isAbsolute(folded)) return null
  // The file's own spelling when the two agree past the fold; the folded one
  // names the same file on the volumes that fold.
  const exact = lib.relative(media, file)
  return lib.join(MEDIA_DIR, exact.startsWith('..') ? folded : exact)
}

/** `source` as an absolute path: a relative one is read from the project
 *  folder. Null when it is relative and no project is open. A Windows path
 *  counts as absolute on every host: no one means `C:/clip.mp4` relative to a
 *  folder, and on POSIX it names nothing and is refused as missing. */
export function absoluteSource(workspaceDir: string | null, source: string, platform: NodeJS.Platform): string | null {
  const lib = pathLib(platform)
  if (lib.isAbsolute(source) || path.win32.isAbsolute(source)) return source
  return workspaceDir === null ? null : lib.join(workspaceDir, source)
}
