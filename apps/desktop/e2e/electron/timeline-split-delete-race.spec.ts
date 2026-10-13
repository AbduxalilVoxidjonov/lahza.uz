import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  importAndPlaceMedia,
  invokeCmd,
  launchApp,
  newProject,
  tmpDir,
  waitForHook, rootSummary,
} from './helpers/driver'

type Layer = {
  id: string
  t_start_us: number
  t_end_us: number
  params: { kind: string }
}

type Summary = {
  tracks: Array<{
    layers: Layer[]
  }>
}

const fixture = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../fixtures/media/test_1080p_30fps.mp4',
)

const videoLayers = (summary: Summary): Layer[] =>
  summary.tracks
    .flatMap((track) => track.layers)
    .filter((layer) => layer.params.kind === 'VideoClip')

const readSummary = (page: Page): Promise<Summary> =>
  rootSummary<Summary>(page)

test('an older summary cannot restore a VideoClip after split-right-delete', async () => {
  const { app, page } = await launchApp()
  try {
    await newProject(page, {
      parentFolder: tmpDir('weftcut-split-delete-race-'),
      name: `split-delete-${Date.now()}`,
      canvas: { width: 640, height: 360, fpsNum: 30, fpsDen: 1 },
    })

    const imported = await importAndPlaceMedia(page, { mediaAbsPath: fixture })
    expect(imported.kind).toBe('Video')
    await waitForHook(page, 'revealLayer')
    await page.evaluate(
      (layerId) => (window as any).__weftcutTest.revealLayer({ layerId }),
      imported.layerId,
    )

    // The block's tooltip leads with the kind's UI name (`kinds.videoclip` →
    // "Video"), not the LayerParams discriminant.
    const blocks = page.locator('.timeline-layer[title^="Video:"]')
    await expect(blocks).toHaveCount(1)
    const originalBox = await blocks.first().boundingBox()
    expect(originalBox).not.toBeNull()
    const original = videoLayers(await readSummary(page))[0]!
    const originalDurationUs = original.t_end_us - original.t_start_us

    // Split through the real UI before holding a read. The publication module
    // deliberately allows only one in-flight read, so a held old read delays
    // the following view barrier rather than starting parallel reads.
    await page.keyboard.press('c')
    await expect(page.locator('.timeline-root-blade')).toHaveCount(1)
    await blocks.first().click({ position: { x: originalBox!.width / 2, y: originalBox!.height / 2 } })
    await expect(blocks).toHaveCount(2)
    await page.keyboard.press('v')
    await expect(page.locator('.timeline-root-blade')).toHaveCount(0)

    // Capture one pre-delete publication. A label commit stands in for any
    // previous edit whose read overlaps deleting the newly split right clip.
    await page.evaluate(() => {
      let release!: () => void
      const released = new Promise<void>((resolve) => {
        release = resolve
      })
      const gate = {
        remaining: 1,
        captured: 0,
        delivered: 0,
        release,
        released,
      }
      ;(globalThis as any).__weftcutSummaryRaceGate = gate
      ;(globalThis as any).__weftcutE2EBackendInvokeInterceptor = async (
        cmd: string,
        args: Record<string, unknown> | undefined,
        next: (
          cmd: string,
          args?: Record<string, unknown>,
        ) => Promise<unknown>,
      ) => {
        if (cmd !== 'project_publication' || gate.remaining === 0) {
          return next(cmd, args)
        }
        gate.remaining -= 1
        const snapshot = await next(cmd, args)
        gate.captured += 1
        await gate.released
        gate.delivered += 1
        return snapshot
      }
    })
    await invokeCmd(page, 'update_layer', {
      layerId: imported.layerId,
      patch: { label: 'summary-race-probe' },
    })
    await page.waitForFunction(
      () => (globalThis as any).__weftcutSummaryRaceGate?.captured === 1,
    )

    const rightIndex = await blocks.evaluateAll((nodes) => {
      const boxes = nodes.map((node, index) => ({
        index,
        x: node.getBoundingClientRect().x,
      }))
      boxes.sort((a, b) => a.x - b.x)
      return boxes.at(-1)!.index
    })
    await blocks.nth(rightIndex).click()
    await page.keyboard.press('Delete')

    await expect
      .poll(async () => videoLayers(await readSummary(page)).length)
      .toBe(1)
    // The old publication is now stale relative to the delete event. Releasing
    // it lets the bounded reader discard it and fetch the newest revision.
    await page.evaluate(() => { (globalThis as any).__weftcutSummaryRaceGate.release() })
    await page.waitForFunction(() => (globalThis as any).__weftcutSummaryRaceGate?.delivered === 1)
    await expect(blocks).toHaveCount(1)
    const cutLayer = videoLayers(await readSummary(page))[0]!
    expect(cutLayer.id).toBe(imported.layerId)
    expect(cutLayer.t_end_us - cutLayer.t_start_us).toBeCloseTo(
      originalDurationUs / 2,
      -4,
    )
    await expect
      .poll(async () => {
        const box = await blocks.first().boundingBox()
        return box!.width / originalBox!.width
      })
      .toBeLessThan(0.65)

    await page.evaluate(
      () =>
        new Promise<void>((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
        ),
    )

    const backendAfterRelease = videoLayers(await readSummary(page))[0]!
    const renderedAfterRelease = await blocks.first().boundingBox()
    expect(backendAfterRelease.t_end_us - backendAfterRelease.t_start_us).toBeCloseTo(
      originalDurationUs / 2,
      -4,
    )
    expect(renderedAfterRelease!.width / originalBox!.width).toBeLessThan(0.65)
  } finally {
    await page
      .evaluate(() => {
        delete (globalThis as any).__weftcutE2EBackendInvokeInterceptor
        delete (globalThis as any).__weftcutSummaryRaceGate
      })
      .catch(() => {})
    await app.close()
  }
})
