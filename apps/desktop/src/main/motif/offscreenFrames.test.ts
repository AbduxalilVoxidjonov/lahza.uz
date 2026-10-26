import { EventEmitter } from 'node:events'
import type { WebContents } from 'electron'
import { describe, expect, it, vi } from 'vitest'
import { OffscreenFrames } from './offscreenFrames'

const fakeContents = () => Object.assign(new EventEmitter(), { stopPainting: vi.fn(), startPainting: vi.fn(), invalidate: vi.fn() })
const texture = (w: number, h = 64) => ({ release: vi.fn(), textureInfo: { codedSize: { width: w, height: h } } })
const fenced = () => vi.fn(async () => {})

describe('OffscreenFrames', () => {
  it('releases unrequested and wrong-size paints and leases only the requested surface', async () => {
    const events = fakeContents()
    const frames = new OffscreenFrames(events as unknown as WebContents)
    const old = texture(128)
    events.emit('paint', { texture: old })
    expect(old.release).toHaveBeenCalledOnce()
    const wanted = frames.capture(128, 64, fenced())
    await Promise.resolve() // the fence settles before painting restarts
    const wrong = texture(64)
    events.emit('paint', { texture: wrong })
    events.emit('paint', {}) // invalidate may return a NativeImage without a texture
    expect(wrong.release).toHaveBeenCalledOnce()
    const right = texture(128)
    events.emit('paint', { texture: right })
    expect(await wanted).toBe(right)
    expect(right.release).not.toHaveBeenCalled() // caller owns it until the GPU copy completes
    expect(events.stopPainting).toHaveBeenCalledOnce()
    expect(events.startPainting).toHaveBeenCalledOnce()
    right.release()
    frames.dispose()
  })

  it('fences a surface once: a new document, a new size or a GPU restart make it unproven again', async () => {
    const events = fakeContents()
    const frames = new OffscreenFrames(events as unknown as WebContents)
    const fence = fenced()
    const lease = async (w: number, h: number) => {
      const wanted = frames.capture(w, h, fence)
      await Promise.resolve(); await Promise.resolve()
      events.emit('paint', { texture: texture(w, h) })
      await wanted
    }
    await lease(128, 64)
    await lease(128, 64)
    expect(fence).toHaveBeenCalledTimes(1) // the proven surface is leased without a readback
    await lease(256, 64)
    expect(fence).toHaveBeenCalledTimes(2) // a new size is a new surface
    events.emit('did-start-navigation', { isMainFrame: true, isSameDocument: true })
    events.emit('did-start-navigation', { isMainFrame: false, isSameDocument: false })
    await lease(256, 64)
    expect(fence).toHaveBeenCalledTimes(2) // same-document and subframe navigations keep the surface
    events.emit('did-start-navigation', { isMainFrame: true, isSameDocument: false })
    await lease(256, 64)
    expect(fence).toHaveBeenCalledTimes(3) // a new document is a new surface
    frames.surfaceChanged()
    await lease(256, 64)
    expect(fence).toHaveBeenCalledTimes(4)
  })

  it('a failed fence leaves the surface unproven and starts no paint', async () => {
    const events = fakeContents()
    const frames = new OffscreenFrames(events as unknown as WebContents)
    await expect(frames.capture(128, 64, async () => { throw new Error('readback failed') })).rejects.toThrow('readback failed')
    expect(events.startPainting).not.toHaveBeenCalled()
    const fence = fenced()
    const wanted = frames.capture(128, 64, fence)
    await Promise.resolve(); await Promise.resolve()
    events.emit('paint', { texture: texture(128) })
    await wanted
    expect(fence).toHaveBeenCalledTimes(1)
  })

  it('rejects a pending capture on host teardown', async () => {
    const events = fakeContents()
    const frames = new OffscreenFrames(events as unknown as WebContents)
    const wanted = frames.capture(128, 64, fenced())
    await Promise.resolve(); await Promise.resolve()
    frames.dispose()
    await expect(wanted).rejects.toThrow('closed')
  })
})
