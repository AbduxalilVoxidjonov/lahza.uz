import { spawn as nodeSpawn, type ChildProcess } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import type { LahzaStatus } from '../../shared/lahza'

/** The Lahza engine: a localhost FastAPI sidecar (Lahza Studio) that serves
 *  Uzbek ASR, highlight detection, 9:16 reframe planning and Uzbek karaoke
 *  subtitle export. Started lazily — on the first call that needs it — so an
 *  install without the staged sidecar costs nothing, and stopped with the app.
 *
 *  Its contract: `serve --port 0` prints `LAHZA_READY port=N` on stdout once
 *  listening on 127.0.0.1; every request carries `Authorization: Bearer
 *  <LAHZA_TOKEN>`. `--watch-stdin` and `--parent-pid` make it exit with us even
 *  when we die without running `stop()`. */

export interface LahzaPaths {
  /** The PyInstaller sidecar executable. */
  engine: string
  /** ffmpeg (with libass), ffprobe, llama-server and their libraries. */
  binDir: string
  /** Signed model catalog and its Ed25519 public key. */
  catalog: string
  catalogPubkey: string
}

export class LahzaError extends Error {
  constructor(public readonly code: string, message: string, public readonly status?: number) {
    super(message)
    this.name = 'LahzaError'
  }
}

/** Where the sidecar lives: `WEFTCUT_LAHZA_DIR`, else the packaged
 *  `resources/lahza`, else the dev tree's `resources/lahza/<os>` that
 *  `scripts/stage-lahza-engine.mjs` fills. */
export function resolveLahzaPaths(opts: { packaged: boolean; resourcesPath: string; devRoot: string; env?: NodeJS.ProcessEnv }): LahzaPaths {
  const env = opts.env ?? process.env
  const osDir = process.platform === 'win32' ? 'win' : process.platform === 'darwin' ? 'mac' : 'linux'
  const dir = env.WEFTCUT_LAHZA_DIR
    ?? (opts.packaged ? path.join(opts.resourcesPath, 'lahza') : path.join(opts.devRoot, 'resources/lahza', osDir))
  return {
    engine: path.join(dir, process.platform === 'win32' ? 'lahza-engine.exe' : 'lahza-engine'),
    binDir: path.join(dir, 'bin'),
    catalog: path.join(dir, 'catalog', 'catalog.json'),
    catalogPubkey: path.join(dir, 'catalog', 'catalog.pub'),
  }
}

export interface LahzaEngineDeps {
  paths: LahzaPaths
  spawn?: typeof nodeSpawn
  fetch?: typeof fetch
  exists?: (p: string) => boolean
  readText?: (p: string) => string
  /** How long a start may take before it is called failed. */
  startTimeoutMs?: number
}

const READY = /LAHZA_READY port=(\d+)/

export class LahzaEngine {
  private child: ChildProcess | null = null
  private starting: Promise<number> | null = null
  private port: number | null = null
  private version = ''
  private lastError: string | null = null
  private readonly token = randomBytes(24).toString('hex')
  private readonly spawnFn: typeof nodeSpawn
  private readonly fetchFn: typeof fetch
  private readonly exists: (p: string) => boolean
  private readonly readText: (p: string) => string

  constructor(private readonly deps: LahzaEngineDeps) {
    this.spawnFn = deps.spawn ?? nodeSpawn
    this.fetchFn = deps.fetch ?? fetch
    this.exists = deps.exists ?? fs.existsSync
    this.readText = deps.readText ?? ((p) => fs.readFileSync(p, 'utf8'))
  }

  available(): boolean {
    return this.exists(this.deps.paths.engine)
  }

  status(): LahzaStatus {
    if (!this.available()) return { state: 'unavailable', reason: `Lahza engine not found at ${this.deps.paths.engine}` }
    if (this.port !== null) return { state: 'ready', port: this.port, version: this.version }
    if (this.starting) return { state: 'starting' }
    if (this.lastError) return { state: 'failed', error: this.lastError }
    return { state: 'stopped' }
  }

  /** Start the sidecar if it is not running; resolves with its port. Joins a
   *  start already in flight. */
  ensureStarted(): Promise<number> {
    if (this.port !== null) return Promise.resolve(this.port)
    if (!this.starting) {
      // Through a microtask, so a synchronous throw in launch (an unreadable
      // catalog key, a spawn that throws) fails the start like any other.
      const deadline = Date.now() + (this.deps.startTimeoutMs ?? 60_000)
      this.starting = Promise.resolve().then(() => this.launch()).then(async (port) => {
        // The engine prints its ready line before uvicorn binds, so the port is
        // only published once the server actually answers.
        this.version = (await this.awaitHealth(port, deadline)).version
        this.port = port
        this.lastError = null
        return port
      }).catch((e: unknown) => {
        this.port = null
        this.lastError = e instanceof Error ? e.message : String(e)
        this.kill()
        throw e
      }).finally(() => { this.starting = null })
    }
    return this.starting
  }

  private launch(): Promise<number> {
    const { paths } = this.deps
    if (!this.available()) return Promise.reject(new LahzaError('lahza_unavailable', `Lahza engine not found at ${paths.engine}. Run scripts/stage-lahza-engine.mjs.`))
    const env: NodeJS.ProcessEnv = { ...process.env, LAHZA_TOKEN: this.token, LAHZA_ATTACH: '0', LAHZA_DEV: '0',
      LAHZA_BIN_DIR: paths.binDir, LAHZA_CATALOG: paths.catalog }
    delete env.ELECTRON_RUN_AS_NODE
    if (this.exists(paths.catalogPubkey)) env.LAHZA_CATALOG_PUBKEY = this.readText(paths.catalogPubkey).trim()
    const child = this.spawnFn(paths.engine, ['serve', '--port', '0', '--watch-stdin', '--parent-pid', String(process.pid)],
      { env, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true })
    this.child = child
    return new Promise<number>((resolve, reject) => {
      let out = '', err = ''
      const timer = setTimeout(() => done(new LahzaError('lahza_start_timeout', `Lahza engine did not report ready${err ? `: ${err.trim().slice(-400)}` : ''}`)),
        this.deps.startTimeoutMs ?? 60_000)
      const done = (e: Error | null, port?: number) => {
        clearTimeout(timer)
        child.stdout?.off('data', onOut)
        if (e) reject(e)
        else resolve(port!)
      }
      const onOut = (chunk: Buffer) => {
        out += chunk.toString()
        const m = READY.exec(out)
        if (m) done(null, Number(m[1]))
      }
      child.stdout?.on('data', onOut)
      child.stderr?.on('data', (chunk: Buffer) => { err = (err + chunk.toString()).slice(-4000) })
      child.once('error', (e) => done(new LahzaError('lahza_spawn_failed', e.message)))
      child.once('exit', (code) => {
        if (this.child === child) { this.child = null; this.port = null }
        done(new LahzaError('lahza_exited', `Lahza engine exited (code ${code})${err ? `: ${err.trim().slice(-400)}` : ''}`))
      })
    })
  }

  /** Poll `GET /v1/health` until the server answers or the start deadline
   *  passes. A refused connection is the not-yet-bound server and is retried;
   *  an HTTP answer other than 200 (a wrong token) fails at once. */
  private async awaitHealth(port: number, deadline: number): Promise<{ version: string }> {
    let delay = 50
    for (;;) {
      if (this.child === null) throw new LahzaError('lahza_exited', 'Lahza engine exited before it answered')
      try {
        const res = await this.fetchFn(`http://127.0.0.1:${port}/v1/health`, { headers: { Authorization: `Bearer ${this.token}` } })
        if (!res.ok) throw new LahzaError('lahza_health_failed', `Lahza engine health check answered HTTP ${res.status}`, res.status)
        return JSON.parse(await res.text()) as { version: string }
      } catch (e) {
        if (e instanceof LahzaError) throw e
        if (Date.now() + delay > deadline) throw new LahzaError('lahza_start_timeout', `Lahza engine did not answer on port ${port}: ${e instanceof Error ? e.message : String(e)}`)
      }
      await new Promise((r) => setTimeout(r, delay))
      delay = Math.min(delay * 2, 500)
    }
  }

  /** One authorized JSON call against the running engine, starting it first. */
  async request<T>(method: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE', route: string, body?: unknown): Promise<T> {
    const port = this.port ?? await this.ensureStarted()
    const res = await this.fetchFn(`http://127.0.0.1:${port}${route}`, {
      method,
      headers: { Authorization: `Bearer ${this.token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    const text = await res.text()
    const json = text ? JSON.parse(text) as unknown : null
    if (!res.ok) {
      const detail = (json as { detail?: unknown } | null)?.detail
      const message = typeof detail === 'string' ? detail
        : detail && typeof detail === 'object' && 'message' in detail ? String((detail as { message: unknown }).message)
        : `HTTP ${res.status}`
      const code = detail && typeof detail === 'object' && 'code' in detail ? String((detail as { code: unknown }).code) : 'lahza_http_error'
      throw new LahzaError(code, `Lahza ${method} ${route}: ${message}`, res.status)
    }
    return json as T
  }

  stop(): void {
    this.kill()
    this.port = null
  }

  private kill(): void {
    const child = this.child
    this.child = null
    if (!child) return
    // Closing stdin is the engine's own shutdown signal (--watch-stdin); the
    // kill is the backstop for a wedged process.
    child.stdin?.end()
    setTimeout(() => { if (child.exitCode === null) child.kill() }, 3000).unref?.()
  }
}
