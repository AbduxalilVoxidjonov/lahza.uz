import { EventEmitter } from 'node:events'
import { PassThrough } from 'node:stream'
import { describe, expect, it, vi } from 'vitest'
import { LahzaEngine, LahzaError, resolveLahzaPaths, type LahzaPaths } from './engine'

const paths: LahzaPaths = { engine: '/lahza/lahza-engine', binDir: '/lahza/bin', catalog: '/lahza/catalog/catalog.json', catalogPubkey: '/lahza/catalog/catalog.pub' }

/** A child process double that prints `stdout` once spawned. */
function fakeChild(stdout: string | null) {
  const child = Object.assign(new EventEmitter(), {
    stdout: new PassThrough(), stderr: new PassThrough(), stdin: new PassThrough(),
    exitCode: null as number | null, kill: vi.fn(),
  })
  if (stdout !== null) setTimeout(() => child.stdout.write(stdout), 0)
  return child
}

const json = (status: number, body: unknown) => ({ ok: status < 400, status, text: async () => JSON.stringify(body) })

describe('LahzaEngine', () => {
  it('is unavailable without the staged executable, and never spawns', async () => {
    const spawn = vi.fn()
    const engine = new LahzaEngine({ paths, spawn: spawn as never, exists: () => false })
    expect(engine.status()).toEqual({ state: 'unavailable', reason: expect.stringContaining('/lahza/lahza-engine') })
    await expect(engine.ensureStarted()).rejects.toMatchObject({ code: 'lahza_unavailable' })
    expect(spawn).not.toHaveBeenCalled()
  })

  it('starts once, reads the ready port, and authorizes every request', async () => {
    const child = fakeChild('booting\nLAHZA_READY port=47611\n')
    const spawn = vi.fn(() => child)
    const fetch = vi.fn(async (url: string) => json(200, url.endsWith('/v1/health') ? { version: '0.2.4', ok: true } : [{ id: 'p1', name: 'WeftCut' }]))
    const engine = new LahzaEngine({ paths, spawn: spawn as never, fetch: fetch as never, exists: () => true, readText: () => ' PUBKEY \n' })

    const [a, b] = await Promise.all([engine.ensureStarted(), engine.ensureStarted()])
    expect(a).toBe(47611)
    expect(b).toBe(47611)
    expect(spawn).toHaveBeenCalledTimes(1)
    const [exe, args, opts] = spawn.mock.calls[0] as unknown as [string, string[], { env: NodeJS.ProcessEnv }]
    expect(exe).toBe(paths.engine)
    expect(args).toEqual(['serve', '--port', '0', '--watch-stdin', '--parent-pid', String(process.pid)])
    expect(opts.env).toMatchObject({ LAHZA_ATTACH: '0', LAHZA_BIN_DIR: paths.binDir, LAHZA_CATALOG: paths.catalog, LAHZA_CATALOG_PUBKEY: 'PUBKEY' })
    expect(opts.env.LAHZA_TOKEN).toMatch(/^[0-9a-f]{48}$/)
    expect(engine.status()).toEqual({ state: 'ready', port: 47611, version: '0.2.4' })

    await engine.request('GET', '/v1/projects')
    const [url, init] = fetch.mock.calls.at(-1) as unknown as [string, RequestInit]
    expect(url).toBe('http://127.0.0.1:47611/v1/projects')
    expect((init.headers as Record<string, string>).Authorization).toBe(`Bearer ${opts.env.LAHZA_TOKEN}`)
  })

  it('waits for the server to bind after the ready line (it is printed before uvicorn listens)', async () => {
    let calls = 0
    const fetch = vi.fn(async () => {
      calls += 1
      if (calls <= 2) throw new TypeError('fetch failed')
      return json(200, { version: '0.2.4' })
    })
    const engine = new LahzaEngine({ paths, spawn: (() => fakeChild('LAHZA_READY port=5\n')) as never, fetch: fetch as never, exists: () => true, readText: () => 'k' })
    const pending = engine.ensureStarted()
    // Not ready until health answers: no request may reach an unbound port.
    expect(engine.status()).toEqual({ state: 'starting' })
    await expect(pending).resolves.toBe(5)
    expect(calls).toBe(3)
    expect(engine.status()).toEqual({ state: 'ready', port: 5, version: '0.2.4' })
  })

  it('gives up with a timeout when the server never binds', async () => {
    const fetch = vi.fn(async () => { throw new TypeError('fetch failed') })
    const engine = new LahzaEngine({ paths, spawn: (() => fakeChild('LAHZA_READY port=5\n')) as never, fetch: fetch as never, exists: () => true, readText: () => 'k', startTimeoutMs: 300 })
    await expect(engine.ensureStarted()).rejects.toMatchObject({ code: 'lahza_start_timeout' })
    expect(engine.status()).toMatchObject({ state: 'failed' })
  })

  it('surfaces an engine refusal with its code and message', async () => {
    const fetch = vi.fn(async (url: string) => url.endsWith('/v1/health')
      ? json(200, { version: '0.2.4' })
      : json(415, { detail: { code: 'unsupported_codec', message: 'AV1 is not supported' } }))
    const engine = new LahzaEngine({ paths, spawn: (() => fakeChild('LAHZA_READY port=1\n')) as never, fetch: fetch as never, exists: () => true, readText: () => 'k' })
    const err = await engine.request('POST', '/v1/media:import', {}).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(LahzaError)
    expect(err).toMatchObject({ code: 'unsupported_codec', status: 415, message: expect.stringContaining('AV1 is not supported') })
  })

  it('a child that exits before ready fails the start with its stderr', async () => {
    const child = fakeChild(null)
    setTimeout(() => { child.stderr.write('ModuleNotFoundError: x\n'); setTimeout(() => child.emit('exit', 1), 0) }, 0)
    const engine = new LahzaEngine({ paths, spawn: (() => child) as never, exists: () => true, readText: () => 'k' })
    await expect(engine.ensureStarted()).rejects.toMatchObject({ code: 'lahza_exited', message: expect.stringContaining('ModuleNotFoundError') })
    expect(engine.status()).toMatchObject({ state: 'failed' })
  })
})

describe('resolveLahzaPaths', () => {
  it('prefers WEFTCUT_LAHZA_DIR, then the packaged resources', () => {
    const exe = process.platform === 'win32' ? 'lahza-engine.exe' : 'lahza-engine'
    expect(resolveLahzaPaths({ packaged: true, resourcesPath: '/res', devRoot: '/dev', env: { WEFTCUT_LAHZA_DIR: '/custom' } }).engine.replace(/\\/g, '/')).toBe(`/custom/${exe}`)
    expect(resolveLahzaPaths({ packaged: true, resourcesPath: '/res', devRoot: '/dev', env: {} }).catalog.replace(/\\/g, '/')).toBe('/res/lahza/catalog/catalog.json')
  })
})
