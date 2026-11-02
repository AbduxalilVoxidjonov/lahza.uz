// CI counterpart of stage-lahza-engine.mjs: instead of staging from a lahza.uz
// checkout, download an already-staged engine bundle (a .tar.gz of the contents of
// resources/lahza/<os>/: lahza-engine[.exe], bin/, catalog/, manifest.json) from a
// pinned URL, verify its sha256 and unpack it into resources/lahza/<os>.
//
//   node scripts/fetch-lahza-engine.mjs [--os mac|win|linux] [--arch arm64|x64] [--required]
//
// Configuration comes from the environment (repo variables, never hardcoded):
//   LAHZA_ENGINE_URL_<OS>_<ARCH>      e.g. LAHZA_ENGINE_URL_MAC_ARM64
//   LAHZA_ENGINE_SHA256_<OS>_<ARCH>   hex sha256 of the .tar.gz
// <OS> is MAC|WIN|LINUX, <ARCH> is ARM64|X64.
//
// Missing config is never silent: without --required (or LAHZA_ENGINE_REQUIRED=1)
// it prints a ::warning:: and exits 0 so the installer is built engine-less;
// with it, it exits 1. A configured but unreachable URL or a hash mismatch is
// always an error.
import { createHash } from 'node:crypto'
import { chmodSync, existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { join, dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'

const here = dirname(fileURLToPath(import.meta.url))
const desktop = resolve(here, '..')

function flag(name) {
  const i = process.argv.indexOf(name)
  return i > 0 ? process.argv[i + 1] : undefined
}
const osDir = flag('--os') ?? (process.platform === 'win32' ? 'win' : process.platform === 'darwin' ? 'mac' : 'linux')
const arch = flag('--arch') ?? process.arch
const required = process.argv.includes('--required') || process.env.LAHZA_ENGINE_REQUIRED === '1'
const outRoot = process.env.LAHZA_ENGINE_OUT ?? join(desktop, 'resources/lahza')

if (!['mac', 'win', 'linux'].includes(osDir)) fail(`unknown --os ${osDir}`)
const suffix = `${osDir.toUpperCase()}_${arch === 'arm64' ? 'ARM64' : 'X64'}`
const urlVar = `LAHZA_ENGINE_URL_${suffix}`
const shaVar = `LAHZA_ENGINE_SHA256_${suffix}`
const url = process.env[urlVar]?.trim()
const expected = process.env[shaVar]?.trim().toLowerCase()

function fail(msg) {
  console.error(`::error::[fetch-lahza-engine] ${msg}`)
  process.exit(1)
}

if (!url || !expected) {
  const msg = `no engine bundle for ${osDir}/${arch}: set repository variables ${urlVar} and ${shaVar} (see docs/releases.md). This build has NO Lahza engine.`
  if (required) fail(msg)
  console.log(`::warning::[fetch-lahza-engine] ${msg}`)
  process.exit(0)
}
// LAHZA_ENGINE_ALLOW_HTTP exists only so the unit test can use a loopback server.
if (!/^https:\/\//.test(url) && process.env.LAHZA_ENGINE_ALLOW_HTTP !== '1') fail(`${urlVar} must be an https:// URL`)
if (!/^[0-9a-f]{64}$/.test(expected)) fail(`${shaVar} must be 64 hex characters`)

const res = await fetch(url, { redirect: 'follow' }).catch(e => fail(`download failed: ${e.message}`))
if (!res.ok) fail(`download failed: HTTP ${res.status} for ${url}`)
const buf = Buffer.from(await res.arrayBuffer())
const actual = createHash('sha256').update(buf).digest('hex')
if (actual !== expected) fail(`sha256 mismatch for ${urlVar}: expected ${expected}, got ${actual}`)

const dest = join(outRoot, osDir)
rmSync(dest, { recursive: true, force: true })
mkdirSync(dest, { recursive: true })
const archive = 'engine-bundle.tar.gz'
writeFileSync(join(dest, archive), buf)
// Relative archive name + cwd: a drive-letter path would be read as host:path by GNU tar on Windows.
execFileSync('tar', ['-xzf', archive], { cwd: dest, stdio: 'inherit' })
rmSync(join(dest, archive))

const exe = osDir === 'win' ? 'lahza-engine.exe' : 'lahza-engine'
if (!existsSync(join(dest, exe))) fail(`bundle has no ${exe} at its top level (pack the contents of resources/lahza/${osDir}, not the folder)`)
if (osDir !== 'win') chmodSync(join(dest, exe), 0o755)
console.log(`[fetch-lahza-engine] ${osDir}/${arch}: ${buf.length} bytes, sha256 ${actual} -> ${dest}`)
