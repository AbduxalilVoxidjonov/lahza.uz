import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, writeFileSync, copyFileSync, symlinkSync, readlinkSync, existsSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { execFileSync } from 'node:child_process'

test('staged engine keeps relative runtime symlinks portable for signing', { skip: process.platform === 'win32' }, t => {
  const root = mkdtempSync(join(tmpdir(), 'lahza-stage-'))
  t.after(() => rmSync(root, { recursive: true, force: true }))
  const scripts = join(root, 'apps/desktop/scripts')
  const source = join(root, 'source')
  const binaries = join(source, 'app/src-tauri/binaries')
  const bin = join(source, 'app/src-tauri/resources/bin')
  const catalog = join(source, 'build/sidecar/catalog')
  for (const dir of [scripts, binaries, bin, catalog]) mkdirSync(dir, { recursive: true })
  copyFileSync(new URL('./stage-lahza-engine.mjs', import.meta.url), join(scripts, 'stage-lahza-engine.mjs'))
  const arch = process.arch === 'arm64' ? 'aarch64' : 'x86_64'
  const triple = process.platform === 'darwin' ? `${arch}-apple-darwin` : `${arch}-unknown-linux-gnu`
  writeFileSync(join(binaries, `lahza-engine-${triple}`), 'engine fixture')
  writeFileSync(join(bin, 'libexample.1.dylib'), 'library fixture')
  symlinkSync('libexample.1.dylib', join(bin, 'libexample.dylib'))
  writeFileSync(join(catalog, 'catalog.json'), '{}')
  execFileSync(process.execPath, [join(scripts, 'stage-lahza-engine.mjs'), '--from', source])
  const staged = join(root, 'apps/desktop/resources/lahza', process.platform === 'darwin' ? 'mac' : 'linux')
  assert.equal(readlinkSync(join(staged, 'bin/libexample.dylib')), 'libexample.1.dylib')
  rmSync(source, { recursive: true, force: true })
  assert.ok(existsSync(join(staged, 'bin/libexample.dylib')), 'link must still resolve after the source checkout is removed')
})
