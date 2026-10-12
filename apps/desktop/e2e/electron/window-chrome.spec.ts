import { test, expect, type ElectronApplication } from '@playwright/test'

import { invokeCmd, launchApp, newProject, tmpDir } from './helpers/driver'

// The main window's macOS caption chrome: `titleBarStyle: 'hidden'` keeps the
// OS-drawn traffic lights, and the renderer insets its own titlebars to clear
// them (src/main/index.ts, app.css / startup.css / perf.css). Two behaviours here
// only a real launch can prove, both of which regressed once:
//
//  1. Window appearance. The traffic lights are drawn through the WINDOW's
//     appearance, not the page's. With themeSource left at 'system', a light-mode
//     host drew the INACTIVE buttons in light-chrome grey — invisible against our
//     #0a0a0a caption, so an unfocused window looked like it had no buttons.
//     `color-scheme: dark` cannot fix this: it governs only what Chromium paints.
//
//  2. Inset timing on leaving fullscreen. The inset must be driven by
//     env(titlebar-area-x), which `titleBarOverlay: true` publishes — never by
//     Electron's 'leave-full-screen' event; see the regression guard below for
//     why that event is too late.

const isDarwin = process.platform === 'darwin'

/// Minimal shape of the Window Controls Overlay API (not in the DOM lib).
interface OverlayLike {
  visible: boolean
  addEventListener(type: 'geometrychange', cb: (e: { visible: boolean }) => void): void
}
declare global {
  interface Navigator {
    windowControlsOverlay?: OverlayLike
  }
  interface Window {
    __insetWhenOverlayReturned?: number | null
  }
}

/// The startup screen's title strip — the surface on show at launch, and one of
/// the bars that must clear the traffic lights.
const TITLEBAR = '.startup-titlebar'

function setFullScreen(app: ElectronApplication, on: boolean): Promise<void> {
  return app.evaluate(({ BrowserWindow }, value) => {
    BrowserWindow.getAllWindows()[0]!.setFullScreen(value)
  }, on)
}

test('window appearance is pinned dark, so macOS draws legible traffic lights', async () => {
  const { app } = await launchApp()

  // Asserted on every platform: it is one app-wide setting, and on Win/Linux it
  // still keeps native menus and dialogs in step with the dark UI.
  expect(await app.evaluate(({ nativeTheme }) => nativeTheme.themeSource)).toBe('dark')
  expect(await app.evaluate(({ nativeTheme }) => nativeTheme.shouldUseDarkColors)).toBe(true)

  await app.close()
})

test('startup caption keeps its edge inset and groups its actions across layout themes', async () => {
  const { app, page } = await launchApp()
  try {
    await expect(page.locator('.startup-titlebar-actions')).toBeVisible()
    await expect(page.locator('.splash-screen')).toHaveCount(0)
    // E2E is a release-mode build: no notice before a version is known.
    await expect(page.locator('.startup-update-toggle')).toHaveCount(0)
    await app.evaluate(({ ipcMain }) => {
      for (const channel of ['updates:status', 'updates:check']) {
        ipcMain.removeHandler(channel)
        ipcMain.handle(channel, () => ({ phase: 'available', version: '9.9.0' }))
      }
    })
    await expect(page.locator('.startup-update-toggle')).toBeVisible()
    for (const [layout_theme, scale] of [
      ['1080p-standard', 1], ['1080p-wide', 1.1],
      ['2k-standard', 1.2], ['2k-wide', 1.32],
      ['4k-standard', 1.5], ['4k-wide', 1.65],
    ] as const) {
      await invokeCmd(page, 'app_settings_set', { patch: { layout_theme } })
      await expect(page.locator('html')).toHaveAttribute('data-layout-theme', layout_theme)
      const metrics = await page.locator(TITLEBAR).evaluate(bar => {
        const rect = bar.getBoundingClientRect()
        const style = getComputedStyle(bar)
        const update = bar.querySelector('.startup-update-toggle')!.getBoundingClientRect()
        const settings = bar.querySelector('.startup-settings-toggle')!.getBoundingClientRect()
        const report = bar.querySelector('.startup-report-toggle')!.getBoundingClientRect()
        const last = bar.querySelector('.window-controls') ?? bar.querySelector('.startup-locale-toggle')!
        return {
          inset: parseFloat(style.getPropertyValue('--app-chrome-inset')),
          padLeft: parseFloat(style.paddingLeft),
          left: settings.left - rect.left,
          updateGap: update.left - report.right,
          updateText: bar.querySelector('.startup-update-toggle')!.textContent,
          updateBackground: getComputedStyle(bar.querySelector('.startup-update-toggle')!).backgroundColor,
          updateRadius: getComputedStyle(bar.querySelector('.startup-update-toggle')!).borderRadius,
          updateWidth: update.width,
          updateHeight: update.height,
          gap: report.left - settings.right,
          right: rect.right - last.getBoundingClientRect().right,
        }
      })
      expect(metrics.inset).toBe(16)
      // Chromium can round bounding boxes at fractional display scales.
      expect(Math.abs(metrics.left - metrics.padLeft)).toBeLessThan(0.5)
      expect(Math.abs(metrics.updateGap - 8 * scale)).toBeLessThan(0.5)
      expect(metrics.updateText).toBe('')
      expect(metrics.updateBackground).toBe('rgb(37, 99, 235)')
      expect(metrics.updateWidth).toBe(metrics.updateHeight)
      expect(parseFloat(metrics.updateRadius)).toBeGreaterThanOrEqual(metrics.updateWidth / 2)
      expect(Math.abs(metrics.gap - 8 * scale)).toBeLessThan(0.5)
      if (isDarwin) {
        expect(metrics.padLeft).toBeGreaterThan(60)
        expect(Math.abs(metrics.right - metrics.inset)).toBeLessThan(0.5)
      } else {
        expect(metrics.padLeft).toBe(metrics.inset)
        expect(Math.abs(metrics.right)).toBeLessThan(0.5)
      }
    }
    await page.locator(TITLEBAR).screenshot({ path: test.info().outputPath('startup-update-titlebar.png') })
    await page.locator('.startup-update-toggle').click()
    await expect(page.getByRole('dialog', { name: 'A new version is available' })).toBeVisible()
    await expect(page.getByRole('dialog').getByRole('button', { name: 'Download and install' })).toBeEnabled()
  } finally {
    await app.close()
  }
})

test.describe('macOS traffic-light inset @serial', () => {
  // Traffic lights and the overlay env vars exist only on macOS; elsewhere the
  // window is fully frameless and the renderer draws its own caption buttons.
  test.skip(!isDarwin, 'macOS-only window chrome')

  test('titlebar clears the buttons, and re-insets as fullscreen exit BEGINS', async () => {
    const { app, page } = await launchApp()
    await page.waitForSelector(TITLEBAR)

    const measure = (selector: string) =>
      page.evaluate((sel) => {
        const el = document.querySelector(sel)!
        const cs = getComputedStyle(el)
        return {
          overlayVisible: navigator.windowControlsOverlay?.visible,
          padLeft: parseFloat(cs.paddingLeft),
          padRight: parseFloat(cs.paddingRight),
          inset: parseFloat(cs.getPropertyValue('--app-chrome-inset')),
          height: parseFloat(cs.height),
        }
      }, selector)

    // Enabled by `titleBarOverlay: true`; without it there are no env vars and
    // every inset below silently collapses to its fallback.
    expect(await page.evaluate(() => !!navigator.windowControlsOverlay)).toBe(true)

    const normal = await measure(TITLEBAR)
    expect(normal.overlayVisible).toBe(true)
    // Chromium's own safe-content edge — ~86px for our trafficLightPosition.
    // Asserted as a floor, not a constant: it is the OS's number, not ours.
    expect(normal.padLeft).toBeGreaterThan(60)
    expect(normal.padRight).toBe(normal.inset)
    // The strip must CONTAIN the button band or the buttons hang onto content.
    expect(normal.height).toBeGreaterThanOrEqual(34)

    // The green stoplight must offer NATIVE fullscreen. Guards a trap that had
    // already sprung: the geometry restore passed `fullscreen: false` on every
    // normal launch, and Electron reads that as "disable the fullscreen button",
    // degrading the green button to a plain zoom (src/main/index.ts).
    expect(
      await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0]!.isFullScreenable()),
    ).toBe(true)

    const buttonsBefore = await app.evaluate(({ BrowserWindow }) =>
      BrowserWindow.getAllWindows()[0]!.getWindowButtonPosition(),
    )

    // Fullscreen hides the traffic lights, but keeps the shared caption inset.
    await setFullScreen(app, true)
    await page.waitForFunction(() => navigator.windowControlsOverlay?.visible === false)
    const fullscreen = await measure(TITLEBAR)
    expect(fullscreen.inset).toBeGreaterThan(0)
    expect(fullscreen.padLeft).toBe(fullscreen.inset)
    expect(fullscreen.padRight).toBe(fullscreen.inset)

    // --- arm the capture BEFORE triggering the exit, so there is no race between
    // installing the listener and the transition starting.
    await page.evaluate(() => {
      window.__insetWhenOverlayReturned = null
      navigator.windowControlsOverlay!.addEventListener('geometrychange', (e) => {
        if (!e.visible || window.__insetWhenOverlayReturned != null) return
        window.__insetWhenOverlayReturned = parseFloat(
          getComputedStyle(document.querySelector('.startup-titlebar')!).paddingLeft,
        )
      })
    })

    await setFullScreen(app, false)
    await page.waitForFunction(() => window.__insetWhenOverlayReturned != null)

    // THE regression guard. Chromium restores the traffic-light area at the
    // START of the exit animation while 'leave-full-screen' fires only once it
    // has FINISHED, so this value is read the instant the buttons come back —
    // before that event. An IPC-driven inset would still be reporting the
    // fullscreen value (the shared inset) here, which is exactly the frame
    // where the title overlaps the buttons.
    const insetOnReturn = await page.evaluate(() => window.__insetWhenOverlayReturned)
    expect(insetOnReturn).toBeGreaterThan(60)

    // The custom traffic-light position must survive the roundtrip. Older Electron
    // reset it on fullscreen exit, which would need a re-apply on the way out.
    const buttonsAfter = await app.evaluate(({ BrowserWindow }) =>
      BrowserWindow.getAllWindows()[0]!.getWindowButtonPosition(),
    )
    expect(buttonsAfter).toEqual(buttonsBefore)

    await app.close()
  })

  test('buttons sit vertically centred in every caption bar', async () => {
    const { app, page } = await launchApp()
    await page.waitForSelector(TITLEBAR)

    // The centring invariant. The buttons occupy a 14px band starting at
    // trafficLightPosition.y, and Chromium reports env(titlebar-area-height) as
    // 2y + 14 — so the band's centre is exactly half that env value, and a bar
    // is centred if and only if its own height EQUALS the env value. Bars that
    // size themselves to env (startup strip, agent row) satisfy it by
    // construction; .app-header has an intrinsic content-driven height, so
    // trafficLightPosition.y in src/main/index.ts has to match it. When this
    // fails, that y is the thing to recompute: y = (barHeight - 14) / 2.
    const centred = (selector: string) =>
      page.evaluate((sel) => {
        const el = document.querySelector(sel)!
        const overlay = (
          navigator as { windowControlsOverlay?: { getTitlebarAreaRect(): DOMRect } }
        ).windowControlsOverlay!.getTitlebarAreaRect()
        return { barHeight: el.getBoundingClientRect().height, bandHeight: overlay.height }
      }, selector)

    const startup = await centred(TITLEBAR)
    // Sub-pixel tolerance only: a whole-point y cannot always hit a fractional
    // bar height exactly, but anything past 1px reads as visibly off-centre.
    expect(Math.abs(startup.barHeight - startup.bandHeight)).toBeLessThanOrEqual(1)

    await newProject(page, {
      parentFolder: tmpDir('weftcut-caption-'),
      name: 'Caption',
      canvas: { width: 1920, height: 1080, fpsNum: 30, fpsDen: 1 },
    })
    await page.waitForSelector('.app-header')
    const header = await centred('.app-header')
    expect(Math.abs(header.barHeight - header.bandHeight)).toBeLessThanOrEqual(1)

    await app.close()
  })
})
