import { expect, test } from '@playwright/test'
import path from 'node:path'
import { invokeCmd, launchApp, newProject, tmpDir, waitForHook } from './helpers/driver'

const canvas = { width: 640, height: 360, fpsNum: 30, fpsDen: 1 }

test('accepted renderer commands publish before returning and mutation callbacks do not fetch twice', async () => {
  const { app, page } = await launchApp()
  try {
    const parent = tmpDir('weftcut-publication-')
    await newProject(page, { parentFolder: parent, name: 'publication', canvas })
    await waitForHook(page, 'publishedCommand')
    await page.waitForFunction(() => (window as any).__weftcutTest.projectStoreSummary() !== null)
    await page.evaluate(() => {
      ;(globalThis as any).__publicationReads = 0
      ;(globalThis as any).__weftcutE2EBackendInvokeInterceptor = async (cmd: string, args: unknown, next: any) => {
        if (cmd === 'project_publication') (globalThis as any).__publicationReads++
        return next(cmd, args)
      }
    })

    const added = await page.evaluate(async () => {
      const result = await (window as any).__weftcutTest.publishedCommand({
        command: 'add_marker', args: { tUs: 1_000_000, label: 'Published' }, afterMutation: true,
      })
      // Read synchronously at the command's return, without a polling helper.
      return { value: result.value, marker: result.summary.compositions[result.summary.root_id].markers[0],
        reads: (globalThis as any).__publicationReads }
    })
    expect(added.marker).toMatchObject({ id: added.value, label: 'Published' })
    expect(added.reads).toBe(1)
    const before = await invokeCmd<any>(page, 'project_publication')

    const reopened = await page.evaluate(async (dir) => {
      await (window as any).__weftcutTest.publishedCommand({ command: 'project_save' })
      return (window as any).__weftcutTest.publishedCommand({ command: 'project_open', args: { path: dir }, afterMutation: true })
    }, path.join(parent, 'publication'))
    const after = await invokeCmd<any>(page, 'project_publication')
    expect(after.version.session).toBeGreaterThan(before.version.session)
    expect(reopened.summary.project_id).toBe(before.summary.project_id)
    expect(reopened.summary.compositions[reopened.summary.root_id].markers[0].id).toBe(added.value)

    const closed = await page.evaluate(() => (window as any).__weftcutTest.publishedCommand({ command: 'project_close' }))
    expect(closed.summary).toBeNull()
    const closedView = await invokeCmd<any>(page, 'project_publication')
    expect(closedView.summary).toBeNull()
    expect(closedView.version.session).toBeGreaterThan(after.version.session)
  } finally { await app.close() }
})

test('a delayed old publication never applies while the newer event waits for its bounded read', async () => {
  const { app, page } = await launchApp()
  try {
    await newProject(page, { parentFolder: tmpDir('weftcut-publication-race-'), name: 'race', canvas })
    await waitForHook(page, 'publishedCommand')
    await page.waitForFunction(() => (window as any).__weftcutTest.projectStoreSummary() !== null)
    const markerId = await page.evaluate(async () => (await (window as any).__weftcutTest.publishedCommand({
      command: 'add_marker', args: { tUs: 1_000_000, label: 'Original' },
    })).value)
    await page.evaluate(() => {
      const gate = { captured: 0, active: 0, peak: 0, release: [] as Array<() => void> }
      ;(globalThis as any).__publicationRace = gate
      ;(globalThis as any).__weftcutE2EBackendInvokeInterceptor = async (cmd: string, args: unknown, next: any) => {
        if (cmd !== 'project_publication') return next(cmd, args)
        gate.active++
        gate.peak = Math.max(gate.peak, gate.active)
        const result = await next(cmd, args)
        gate.captured++
        await new Promise<void>(resolve => { gate.release.push(resolve) })
        gate.active--
        return result
      }
    })
    await invokeCmd(page, 'update_marker', { markerId, patch: { label: 'Stale' } })
    await page.waitForFunction(() => (globalThis as any).__publicationRace.captured === 1)
    await invokeCmd(page, 'update_marker', { markerId, patch: { label: 'Newest' } })
    // Let the real project:changed event reach the renderer before returning
    // the held snapshot. The marker label remains the last applied version.
    await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
    await page.evaluate(() => (globalThis as any).__publicationRace.release[0]())
    await page.waitForFunction(() => (globalThis as any).__publicationRace.captured === 2)
    const during = await page.evaluate(() => {
      const s = (window as any).__weftcutTest.projectStoreSummary()
      return { label: s.compositions[s.root_id].markers[0].label, peak: (globalThis as any).__publicationRace.peak }
    })
    expect(during).toEqual({ label: 'Original', peak: 1 })
    await page.evaluate(() => (globalThis as any).__publicationRace.release[1]())
    await expect.poll(() => page.evaluate(() => {
      const s = (window as any).__weftcutTest.projectStoreSummary()
      return s.compositions[s.root_id].markers[0].label
    })).toBe('Newest')
  } finally { await app.close() }
})
