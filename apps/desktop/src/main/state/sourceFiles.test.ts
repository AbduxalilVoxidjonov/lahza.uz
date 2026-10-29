import { describe, expect, it, vi } from 'vitest'
import { createSourceFiles } from './sourceFiles'
import { mediaItemTemplate } from './mutations/media'
import type { MediaItem } from './model'

const HASH = 'a'.repeat(64)
const item = (over: Partial<MediaItem> = {}): MediaItem => ({
  ...mediaItemTemplate('00000000-0000-0000-0000-0000000000aa', 'Video', 1_000_000),
  path_abs: '/p/Media/x.mp4', file_hash_blake3: HASH, file_size: 100, file_mtime: 50, ...over,
})

function fixture(file: { size: number; mtimeSecs: number } | null, bytes = HASH) {
  const deps = {
    stat: vi.fn(() => file),
    hash: vi.fn(async () => bytes),
    confirmed: vi.fn(),
    settled: vi.fn(),
  }
  return { deps, files: createSourceFiles(deps) }
}

describe('source file state', () => {
  it('is present when size and mtime are as recorded, without reading the bytes', async () => {
    const { deps, files } = fixture({ size: 100, mtimeSecs: 50 })
    expect(files.state(item())).toBe('present')
    expect(await files.settle(item())).toBe('present')
    expect(deps.hash).not.toHaveBeenCalled()
  })

  it('is missing when nothing is there', () => {
    expect(fixture(null).files.state(item())).toBe('missing')
  })

  it('is changed at once when the size differs', () => {
    const { deps, files } = fixture({ size: 101, mtimeSecs: 50 })
    expect(files.state(item())).toBe('changed')
    expect(deps.hash).not.toHaveBeenCalled()
  })

  it('does not judge an item still importing', () => {
    expect(fixture({ size: 7, mtimeSecs: 1 }).files.state(item({ file_hash_blake3: 'pending-x' }))).toBe('present')
  })

  // A project folder copied without its times: every mtime differs, the
  // bytes do not. Read once, recorded, and never flagged.
  it('reads the bytes once when only the mtime differs, and records the new mtime', async () => {
    const { deps, files } = fixture({ size: 100, mtimeSecs: 99 })
    expect(files.state(item())).toBe('present')
    expect(await files.settle(item())).toBe('present')
    expect(deps.hash).toHaveBeenCalledOnce()
    expect(deps.confirmed).toHaveBeenCalledWith(item(), 99)
    expect(deps.settled).toHaveBeenCalledOnce()
  })

  it('is changed once the read finds other bytes of the same size', async () => {
    const { deps, files } = fixture({ size: 100, mtimeSecs: 99 }, 'b'.repeat(64))
    expect(await files.settle(item())).toBe('changed')
    expect(files.state(item())).toBe('changed')
    expect(deps.confirmed).not.toHaveBeenCalled()
    expect(deps.hash).toHaveBeenCalledOnce()
  })

  it('reads one file at a time', async () => {
    let release!: () => void
    const { deps, files } = fixture({ size: 100, mtimeSecs: 99 })
    deps.hash.mockImplementationOnce(() => new Promise<string>(resolve => { release = () => resolve(HASH) }))
    const first = files.settle(item())
    const second = files.settle(item({ id: '00000000-0000-0000-0000-0000000000bb', path_abs: '/p/Media/y.mp4' }))
    await Promise.resolve()
    expect(deps.hash).toHaveBeenCalledOnce()
    release()
    expect(await first).toBe('present')
    expect(await second).toBe('present')
    expect(deps.hash).toHaveBeenCalledTimes(2)
  })
})
