// apps/desktop/src/main/state/importSource.ts
//
// Where an import's source already stands: the pool item whose file or bytes
// it is, or a place under the project's Media/ folder, where the import copy
// would have put it. Pure but for the injected file key and realpath;
// `platform` picks the path rules, so a test on Linux can speak Windows paths.
import path from 'node:path'
import type { MediaItem } from './model'

/** The folder the import copy writes into (native `jobs/import.rs` MEDIA_DIR). */
const MEDIA_DIR = 'Media'
/** The probe's provisional hash (native `media_item_from_metadata`). */
const PENDING_HASH = 'pending-'

const pathLib = (platform: NodeJS.Platform) => (platform === 'win32' ? path.win32 : path.posix)

/** Which file a path names: two paths name one file exactly when their keys
 *  are equal. Null when nothing is there. */
export type FileKey = (p: string) => string | null

/** The key when the host can tell no file identity: the resolved real path,
 *  as spelled. Never folded for case or Unicode normalization: whether two
 *  spellings are one file is the volume's call (NTFS holds an NFC and an NFD
 *  `café.mp4` side by side), and only a stat can ask it. */
export function spelledKey(realPath: (p: string) => string, platform: NodeJS.Platform): FileKey {
  return (p) => pathLib(platform).resolve(realPath(p))
}

/** The pool item whose file `source` is: a link, another spelling or the
 *  source of a copy still in flight all match, provided the probe's size and
 *  modification time still match the item. File identity alone survives an
 *  overwrite; a changed fingerprint must go through content matching instead.
 *  A pooled file that is gone matches nothing. */
export function pooledItemFor(
  pool: Record<string, MediaItem>, source: string, fileKey: FileKey,
  found: Pick<MediaItem, 'file_size' | 'file_mtime'>,
): MediaItem | null {
  const key = fileKey(source)
  if (key === null) return null
  for (const item of Object.values(pool)) {
    if (item.file_size === found.file_size && item.file_mtime === found.file_mtime && fileKey(item.path_abs) === key) return item
  }
  return null
}

/** Whether a pool item of `size` bytes has its content hash yet, so hashing a
 *  source of that size could find it. A copy into Media/ replaces the item's
 *  path, so its bytes are what is left to match the source by. */
export function hashedItemOfSize(pool: Record<string, MediaItem>, size: number): boolean {
  return Object.values(pool).some((m) => m.file_size === size && !m.file_hash_blake3.startsWith(PENDING_HASH))
}

/** The pool item holding these bytes, once both hashes are real. */
export function pooledItemWithHash(pool: Record<string, MediaItem>, hash: string): MediaItem | null {
  return Object.values(pool).find((m) => m.file_hash_blake3 === hash) ?? null
}

/** `source`'s path relative to the project folder when it already sits under
 *  the project's Media/ folder, else null. A folder is Media/ when it is the
 *  same folder, however the two paths spell it. */
export function mediaFolderPath(
  workspaceDir: string, source: string,
  realPath: (p: string) => string, fileKey: FileKey, platform: NodeJS.Platform,
): string | null {
  const lib = pathLib(platform)
  const media = fileKey(lib.join(workspaceDir, MEDIA_DIR))
  if (media === null) return null
  const file = realPath(source)
  for (let dir = lib.dirname(file); ; dir = lib.dirname(dir)) {
    if (fileKey(dir) === media) return lib.join(MEDIA_DIR, lib.relative(dir, file))
    if (lib.dirname(dir) === dir) return null
  }
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
