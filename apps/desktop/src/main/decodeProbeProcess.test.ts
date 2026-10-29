import { EventEmitter } from 'node:events'
import { spawn as spawnChild } from 'node:child_process'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createDecodeProbeProcess } from './decodeProbeProcess'

class Child extends EventEmitter {
  pid = 123
  postMessage = vi.fn()
}
function fixture() {
  vi.useFakeTimers()
  const child = new Child()
  const release = vi.fn()
  const spawn = vi.fn(() => child)
  const kill = vi.fn()
  const reserve = vi.fn(() => release)
  const probe = createDecodeProbeProcess({ spawn, kill, reserve, timeoutMs: 100, reapMs: 20 })
  return { probe, child, release, spawn, kill, reserve }
}
const request = { path: '/fixture.mp4', lane: 'videotoolbox' as const, device: null }
afterEach(() => vi.useRealTimers())

describe('isolated decode probe lifetime', () => {
  it('waits for exit before returning a verdict and releasing admission', async () => {
    const f = fixture()
    const done = vi.fn()
    const pending = f.probe.probe(request).then(done)
    f.child.emit('message', { type: 'ready' })
    expect(f.child.postMessage).toHaveBeenCalledWith(request)
    f.child.emit('message', { type: 'result', verdict: { ok: true, reason: null } })
    await Promise.resolve()
    expect(done).not.toHaveBeenCalled()
    expect(f.release).not.toHaveBeenCalled()
    f.child.emit('exit', 0)
    await pending
    expect(done).toHaveBeenCalledWith({ ok: true, reason: null })
    expect(f.release).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(200)
    expect(f.kill).not.toHaveBeenCalled()
  })

  it('times out even before ready, ignores late success, and retains admission until reaped', async () => {
    const f = fixture()
    const pending = f.probe.probe(request)
    await vi.advanceTimersByTimeAsync(100)
    expect(f.kill).toHaveBeenCalledWith(f.child)
    f.child.emit('message', { type: 'result', verdict: { ok: true, reason: null } })
    await vi.advanceTimersByTimeAsync(20)
    expect(await pending).toEqual({ ok: false, reason: 'timeout', cacheable: false })
    expect(f.release).not.toHaveBeenCalled()
    expect(f.probe.unavailableReason).toBe('timeout')
    expect(await f.probe.probe(request)).toMatchObject({ ok: false, cacheable: false })
    expect(f.spawn).toHaveBeenCalledTimes(1)
    f.child.emit('exit', 9)
    expect(f.release).toHaveBeenCalledTimes(1)
  })

  it('a blocked synchronous probe cannot postpone the parent deadline', async () => {
    const f = fixture()
    const pending = f.probe.probe(request)
    f.child.emit('message', { type: 'ready' })
    await vi.advanceTimersByTimeAsync(100)
    f.child.emit('exit', 9)
    expect(await pending).toMatchObject({ reason: 'timeout', cacheable: false })
    expect(f.release).toHaveBeenCalledTimes(1)
  })

  it('crash after a result is transient, not a cached positive', async () => {
    const f = fixture()
    const pending = f.probe.probe(request)
    f.child.emit('message', { type: 'result', verdict: { ok: true, reason: null } })
    f.child.emit('exit', 1)
    expect(await pending).toMatchObject({ ok: false, reason: 'probe-exited', cacheable: false })
    expect(f.release).toHaveBeenCalledTimes(1)
  })

  it('stopping terminates the active child and prevents new work', async () => {
    const f = fixture()
    const pending = f.probe.probe(request)
    f.probe.stop()
    expect(f.kill).toHaveBeenCalledTimes(1)
    f.child.emit('exit', 9)
    expect(await pending).toMatchObject({ reason: 'stopped', cacheable: false })
    expect(await f.probe.probe(request)).toMatchObject({ reason: 'stopped' })
    expect(f.release).toHaveBeenCalledTimes(1)
  })

  it('busy admission does not persist or disable hardware for the session', async () => {
    const f = fixture()
    f.reserve.mockImplementation(() => { throw new Error('capacity') })
    const busy = f.probe.probe(request)
    await vi.advanceTimersByTimeAsync(4_000)
    expect(await busy).toMatchObject({ reason: 'resource-busy', cacheable: false })
    expect(f.probe.unavailableReason).toBeNull()
    expect(f.spawn).not.toHaveBeenCalled()
    f.reserve.mockImplementation(() => f.release)
    const pending = f.probe.probe(request)
    await vi.waitFor(() => expect(f.spawn).toHaveBeenCalledOnce())
    f.child.emit('message', { type: 'result', verdict: { ok: false, reason: 'unsupported' } })
    f.child.emit('exit', 0)
    expect(await pending).toEqual({ ok: false, reason: 'unsupported' })
    expect(f.probe.unavailableReason).toBeNull()
  })

  // First open of an H.264 and an HEVC source at once: one probe running is
  // no answer about the other format, so the second waits its turn.
  it('runs a probe asked for during another after it, not as a busy refusal', async () => {
    const f = fixture()
    const children = [new Child(), new Child()]
    f.spawn.mockImplementation(() => children[f.spawn.mock.calls.length - 1])
    const hevc = { ...request, path: '/fixture-hevc.mp4' }
    const first = f.probe.probe(request)
    const second = f.probe.probe(hevc)
    await vi.waitFor(() => expect(f.spawn).toHaveBeenCalledOnce())
    children[0].emit('message', { type: 'ready' })
    children[0].emit('message', { type: 'result', verdict: { ok: true, reason: null } })
    await vi.advanceTimersByTimeAsync(10)
    expect(f.spawn).toHaveBeenCalledOnce()
    children[0].emit('exit', 0)
    expect(await first).toEqual({ ok: true, reason: null })
    await vi.waitFor(() => expect(f.spawn).toHaveBeenCalledTimes(2))
    children[1].emit('message', { type: 'ready' })
    expect(children[1].postMessage).toHaveBeenCalledWith(hevc)
    children[1].emit('message', { type: 'result', verdict: { ok: true, reason: null } })
    children[1].emit('exit', 0)
    expect(await second).toEqual({ ok: true, reason: null })
    expect(f.release).toHaveBeenCalledTimes(2)
  })

  it('answers a waiting probe at once when the one before it disabled probing', async () => {
    const f = fixture()
    const first = f.probe.probe(request)
    const second = f.probe.probe(request)
    await vi.advanceTimersByTimeAsync(120)
    expect(await first).toMatchObject({ reason: 'timeout' })
    // The first child is never reaped; the second caller is still answered.
    expect(await second).toMatchObject({ ok: false, reason: 'timeout', cacheable: false })
    expect(f.spawn).toHaveBeenCalledOnce()
  })

  it('waits for temporary import contention before launching one hardware probe', async () => {
    const f = fixture()
    f.reserve.mockImplementationOnce(() => { throw new Error('import owns CPU') })
    const pending = f.probe.probe(request)
    await Promise.resolve()
    expect(f.spawn).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(50)
    expect(f.spawn).toHaveBeenCalledTimes(1)
    f.child.emit('message', { type: 'result', verdict: { ok: true, reason: null } })
    f.child.emit('exit', 0)
    expect(await pending).toEqual({ ok: true, reason: null })
  })

  it('shutdown cancels admission waiting without spawning or leaking a timer', async () => {
    const f = fixture()
    f.reserve.mockImplementation(() => { throw new Error('busy') })
    const pending = f.probe.probe(request)
    f.probe.stop()
    expect(await pending).toMatchObject({ reason: 'stopped', cacheable: false })
    await vi.advanceTimersByTimeAsync(5_000)
    expect(f.spawn).not.toHaveBeenCalled()
    expect(f.reserve).toHaveBeenCalledTimes(1)
  })

  it('releases a reservation when spawn throws', async () => {
    const f = fixture()
    f.spawn.mockImplementationOnce(() => { throw new Error('spawn failed') })
    expect(await f.probe.probe(request)).toMatchObject({ reason: 'probe-start-failed', cacheable: false })
    expect(f.release).toHaveBeenCalledTimes(1)
  })

  it('terminates a child whose PID arrives after the startup deadline', async () => {
    const f = fixture()
    const pending = f.probe.probe(request)
    await vi.advanceTimersByTimeAsync(100)
    f.child.emit('spawn')
    expect(f.kill).toHaveBeenCalledTimes(2)
    f.child.emit('exit', 9)
    expect(await pending).toMatchObject({ reason: 'timeout' })
  })
})

it('recovers from a real child blocked in a synchronous call while the parent stays responsive', async () => {
  vi.useRealTimers()
  let child: ReturnType<typeof spawnChild> | undefined
  const release = vi.fn()
  let entered!: () => void
  const blocked = new Promise<void>(resolve => { entered = resolve })
  const probe = createDecodeProbeProcess({
    spawn() {
      child = spawnChild(process.execPath, ['-e', `
        process.on('message', () => {
          process.send({ type: 'entered' });
          Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0);
        });
        process.send({ type: 'ready' });
      `], { stdio: ['ignore', 'ignore', 'ignore', 'ipc'], windowsHide: true })
      child.on('message', (m: any) => { if (m.type === 'entered') entered() })
      return Object.assign(child, { postMessage: (m: unknown) => child!.send!(m as object) })
    },
    kill: () => { child!.kill('SIGKILL') }, reserve: () => release,
    timeoutMs: 2_000, reapMs: 1_000,
  })
  try {
    const result = probe.probe(request)
    await Promise.race([blocked, result.then(() => { throw new Error('Child exited before entering the blocking call') })])
    expect(await new Promise(resolve => setTimeout(() => resolve('responsive'), 10))).toBe('responsive')
    expect(await result).toMatchObject({ reason: 'timeout', cacheable: false })
    await vi.waitFor(() => expect(release).toHaveBeenCalledTimes(1))
    expect(child!.exitCode !== null || child!.signalCode !== null).toBe(true)
  } finally { probe.stop(); child?.kill('SIGKILL') }
}, 8_000)
