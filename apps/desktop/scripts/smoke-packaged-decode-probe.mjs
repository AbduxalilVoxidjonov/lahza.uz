// Runs after macOS packaging: development Electron does not exercise the app's
// helper signature, asar entry location or co-located addon/dylib resolution.
import { _electron } from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { ownProcessTree, closeProcessTree } from '../e2e/lib/process-cleanup.mjs'

const executablePath = path.resolve(process.argv[2] ?? 'release/mac-arm64/WeftCut.app/Contents/MacOS/WeftCut')
assert.equal(process.platform, 'darwin', 'Packaged VideoToolbox probe smoke requires macOS')
assert.ok(fs.existsSync(executablePath), `Packaged executable missing: ${executablePath}`)
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'weftcut-packaged-probe-'))
let app, tree, timer
try {
  app = await _electron.launch({ executablePath, args: [`--user-data-dir=${profile}`],
    env: { ...process.env, WEFTCUT_SUPPRESS_ELEVATION_NOTICE: '1' }, timeout: 30_000 })
  tree = ownProcessTree(app.process())
  await Promise.race([
    (async () => {
      const page = await app.firstWindow()
      await page.waitForFunction(() => !!window.api?.decodeCap)
      const result = await page.evaluate(() => window.api.decodeCap.probeHw('/nonexistent-probe-fixture.mp4', 'h264::yuv420p:hd'))
      // A native file-open negative proves the module loaded. Startup failure,
      // timeout and absent lane must fail instead of masquerading as fallback.
      assert.equal(result.ok, false)
      assert.equal(result.lane, null)
      assert.equal(result.reason, 'no hw lane passed')
      assert.equal(result.diagnostic?.kind, 'failed')
      assert.ok(result.diagnostic.reason.length > 0)
      const cache = JSON.parse(fs.readFileSync(path.join(profile, 'decode_capability.json'), 'utf8'))
      assert.equal(cache.entries.videotoolbox['h264::yuv420p:hd'].ok, false)
      console.log('Packaged macOS decode probe: native verdict received and host reaped')
    })(),
    new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Packaged decode probe smoke timed out')), 30_000) }),
  ])
} finally {
  clearTimeout(timer)
  try { if (app && tree) await closeProcessTree(tree, () => app.close()) }
  finally { fs.rmSync(profile, { recursive: true, force: true }) }
}
