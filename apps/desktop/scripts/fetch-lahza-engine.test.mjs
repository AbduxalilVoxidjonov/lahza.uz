import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, writeFileSync, existsSync, rmSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { createServer } from 'node:http'
import { createHash } from 'node:crypto'
import { execFileSync, spawn } from 'node:child_process'

const script = new URL('./fetch-lahza-engine.mjs', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')

function run(args, env) {
  return new Promise(resolve => {
    const p = spawn(process.execPath, [script, ...args], { env: { ...process.env, ...env }, stdio: ['ignore', 'pipe', 'pipe'] })
    let out = ''
    p.stdout.on('data', d => (out += d))
    p.stderr.on('data', d => (out += d))
    p.on('close', code => resolve({ code, out }))
  })
}

test('fetch-lahza-engine: missing config warns (or fails with --required), never silent', async t => {
  const out = mkdtempSync(join(tmpdir(), 'lahza-fetch-'))
  t.after(() => rmSync(out, { recursive: true, force: true }))
  const env = { LAHZA_ENGINE_OUT: out, LAHZA_ENGINE_URL_LINUX_X64: '', LAHZA_ENGINE_SHA256_LINUX_X64: '' }
  const soft = await run(['--os', 'linux', '--arch', 'x64'], env)
  assert.equal(soft.code, 0)
  assert.match(soft.out, /::warning::.*LAHZA_ENGINE_URL_LINUX_X64/)
  const hard = await run(['--os', 'linux', '--arch', 'x64', '--required'], env)
  assert.equal(hard.code, 1)
  assert.match(hard.out, /::error::/)
})

test('fetch-lahza-engine: verifies sha256 and unpacks the bundle', async t => {
  const work = mkdtempSync(join(tmpdir(), 'lahza-fetch-'))
  t.after(() => rmSync(work, { recursive: true, force: true }))
  const src = join(work, 'src')
  mkdirSync(join(src, 'catalog'), { recursive: true })
  writeFileSync(join(src, 'lahza-engine'), 'engine fixture')
  writeFileSync(join(src, 'catalog/catalog.json'), '{}')
  const tgz = join(work, 'bundle.tar.gz')
  execFileSync('tar', ['-czf', 'bundle.tar.gz', '-C', 'src', '.'], { cwd: work })
  const body = readFileSync(tgz)
  const server = createServer((_, res) => res.end(body))
  await new Promise(r => server.listen(0, '127.0.0.1', r))
  t.after(() => server.close())
  // https is required unless LAHZA_ENGINE_ALLOW_HTTP=1 (loopback test server).
  const url = `http://127.0.0.1:${server.address().port}/b.tar.gz`
  const out = join(work, 'out')
  const sha = createHash('sha256').update(body).digest('hex')
  const rejected = await run(['--os', 'linux', '--arch', 'x64'], { LAHZA_ENGINE_OUT: out, LAHZA_ENGINE_URL_LINUX_X64: url, LAHZA_ENGINE_SHA256_LINUX_X64: sha })
  assert.equal(rejected.code, 1)
  assert.match(rejected.out, /https/)
  const ok = await run(['--os', 'linux', '--arch', 'x64'], { LAHZA_ENGINE_OUT: out, LAHZA_ENGINE_URL_LINUX_X64: url, LAHZA_ENGINE_SHA256_LINUX_X64: sha, LAHZA_ENGINE_ALLOW_HTTP: '1' })
  assert.equal(ok.code, 0, ok.out)
  assert.ok(existsSync(join(out, 'linux/lahza-engine')))
  assert.ok(existsSync(join(out, 'linux/catalog/catalog.json')))
  assert.ok(!existsSync(join(out, 'linux/engine-bundle.tar.gz')))
  const bad = await run(['--os', 'linux', '--arch', 'x64'], { LAHZA_ENGINE_OUT: join(work, 'out2'), LAHZA_ENGINE_URL_LINUX_X64: url, LAHZA_ENGINE_SHA256_LINUX_X64: '0'.repeat(64), LAHZA_ENGINE_ALLOW_HTTP: '1' })
  assert.equal(bad.code, 1)
  assert.match(bad.out, /sha256 mismatch/)
  assert.ok(!existsSync(join(work, 'out2/linux')))
})
