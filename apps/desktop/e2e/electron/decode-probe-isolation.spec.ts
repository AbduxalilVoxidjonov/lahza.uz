import { expect, test } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { launchApp, tmpDir, newProject, importAndPlaceMedia, driveExport } from './helpers/driver'
import { verifyHardwareEvidence } from '../lib/hardware-evidence.mjs'

test('macOS probe timeout preserves IPC, reaps its host and leaves the capability cache unchanged', async () => {
  test.skip(process.platform !== 'darwin', 'VideoToolbox probe isolation')
  test.setTimeout(90_000)
  const userDataDir = tmpDir('weftcut-probe-profile-')
  const host = path.join(tmpDir('weftcut-probe-host-'), 'blocked.cjs')
  fs.writeFileSync(host, `
    process.parentPort.once('message', () => {
      process.parentPort.postMessage({ type: 'entered' });
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0);
    });
    process.parentPort.postMessage({ type: 'ready' });
  `)
  const { app, page } = await launchApp({ userDataDir })
  try {
    await app.evaluate(({ utilityProcess }, fixture) => {
      const fork = utilityProcess.fork.bind(utilityProcess)
      const state = { launched: 0, entered: false, exited: false }
      ;(globalThis as any).__probeState = state
      utilityProcess.fork = ((entry: string, args: string[], options: any) => {
        if (!entry.endsWith('decodeProbe.js')) return fork(entry, args, options)
        state.launched++
        const child = fork(fixture, args, options)
        child.on('message', m => { if (m.type === 'entered') state.entered = true })
        child.once('exit', () => { state.exited = true })
        return child
      }) as typeof utilityProcess.fork
    }, host)
    const before = await page.evaluate(() => window.api.resources.status())
    await page.evaluate(() => {
      ;(window as any).__probeResult = null
      void window.api.decodeCap.probeHw('/synthetic.mp4', 'h264::yuv420p:hd')
        .then(result => { (window as any).__probeResult = result })
    })
    await expect.poll(() => app.evaluate(() => (globalThis as any).__probeState.entered)).toBe(true)
    // Both main's timer and renderer->main IPC run while the host is blocked.
    expect(await app.evaluate(() => new Promise(resolve => setTimeout(() => resolve('alive'), 20)))).toBe('alive')
    await page.evaluate(() => window.api.resources.status())
    await expect.poll(() => page.evaluate(() => (window as any).__probeResult), { timeout: 10_000 })
      .toMatchObject({ ok: false, lane: null, reason: 'timeout' })
    await expect.poll(() => app.evaluate(() => (globalThis as any).__probeState.exited)).toBe(true)
    await expect.poll(async () => (await page.evaluate(() => window.api.resources.status())).reserved_mib).toBe(before.reserved_mib)
    const cacheFile = path.join(userDataDir, 'decode_capability.json')
    const cache = fs.existsSync(cacheFile) ? JSON.parse(fs.readFileSync(cacheFile, 'utf8')) : {}
    expect(cache.entries?.videotoolbox).toBeUndefined()
    expect(await page.evaluate(() => window.api.decodeCap.probeHw('/another.mp4', 'hevc::yuv420p:uhd')))
      .toMatchObject({ ok: false, reason: 'timeout' })
    expect(await app.evaluate(() => (globalThis as any).__probeState.launched)).toBe(1)

    // Exercise the real fallback and a subsequent export in the same session.
    await newProject(page, { parentFolder: tmpDir('weftcut-probe-project-'), name: 'Probe recovery',
      canvas: { width: 1920, height: 1080, fpsNum: 30, fpsDen: 1 } })
    const { layerId } = await importAndPlaceMedia(page, { mediaAbsPath: path.resolve('e2e/fixtures/media/test_1080p_30fps_6s.mp4') })
    await page.waitForFunction(id => {
      try { return (window as any).__weftcutTest.activeClipProbe(id)?.spriteBound }
      catch { return false } // The React preview bridge is mounted asynchronously.
    }, layerId)
    const evidence = await page.evaluate(id => (window as any).__weftcutTest.activeClipProbe(id), layerId)
    expect(evidence).toMatchObject({ sourceKind: 'sw', hwLane: null, hwDiagnostic: { kind: 'failed', reason: 'timeout' } })
    // Product recovery remains successful, but the SAME evidence used by the
    // hardware conformance gates must fail, never skip or claim a HW pass.
    expect(() => verifyHardwareEvidence(evidence, 'videotoolbox')).toThrow(/Hardware probe\/session failed/)
    const result = await driveExport(page, { outputAbsPath: path.join(tmpDir('weftcut-probe-export-'), 'out.mp4'),
      settings: { hwAccel: 'software', decodeEngine: 'ffmpeg', audio: { include: false } } }, { hook: 'exportTimeline' })
    expect(result.done.ok, result.done.error).toBe(true)
  } finally { await app.close() }
})

test('macOS disposable probe loads the shipped addon and returns a native verdict', async () => {
  test.skip(process.platform !== 'darwin', 'VideoToolbox probe isolation')
  const { app, page } = await launchApp()
  try {
    // Missing file returns a native negative without invoking the VM's codec
    // driver: this checks host entry/module/dylib loading deterministically.
    const result = await page.evaluate(() => window.api.decodeCap.probeHw('/nonexistent-probe-fixture.mp4', 'h264::yuv420p:hd'))
    expect(result).toMatchObject({ ok: false, lane: null, reason: 'no hw lane passed' })
    expect(await page.evaluate(() => window.api.decodeCap.probeHw('/nonexistent-probe-fixture.mp4', 'h264::yuv420p:hd')))
      .toEqual(result)
  } finally { await app.close() }
})
