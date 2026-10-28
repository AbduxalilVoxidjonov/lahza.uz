import { describe, expect, it } from 'vitest'
import { rasterSize, svgIntrinsicSize } from './svgRaster'
import { createActor } from './state/actor'
import { seededGen } from './state/ids'
import { ensureImported, type MediaImportDeps } from './state/mediaImport'
import { blankProject } from './state/model'

describe('SVG on import', () => {
  it('reads an SVG\'s own size from width and height, else its viewBox', () => {
    expect(svgIntrinsicSize('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300px">')).toEqual({ width: 400, height: 300 })
    expect(svgIntrinsicSize('<?xml version="1.0"?>\n<svg viewBox="0 0 900 760" width="100%">')).toEqual({ width: 900, height: 760 })
    expect(svgIntrinsicSize('<svg width="10cm" height="5cm" viewBox="0,0,200,100">')).toEqual({ width: 200, height: 100 })
    expect(svgIntrinsicSize('<svg>')).toBeNull()
    expect(svgIntrinsicSize('<html></html>')).toBeNull()
  })

  it('draws the long edge at 2048', () => {
    expect(rasterSize({ width: 900, height: 760 })).toEqual({ width: 2048, height: 1729 })
    expect(rasterSize({ width: 100, height: 400 })).toEqual({ width: 512, height: 2048 })
  })

  it('imports the PNG an SVG becomes, and refuses an SVG where nothing can draw it', async () => {
    const probed: string[] = []
    const idGen = seededGen()
    const actor = createActor({ initial: blankProject(idGen, 'SVG import'), idGen })
    const unexpected = async (): Promise<never> => { throw new Error('An unsuccessful SVG import must not reach this stage') }
    const deps: MediaImportDeps = {
      statPath: () => ({ kind: 'file', readable: true }),
      compute: {
        probeMedia: async (p: string) => { probed.push(p); throw new Error('stop') },
        hashMediaSource: unexpected,
      },
      enqueueDerivatives: unexpected,
      enqueueWorkspaceCopy: unexpected,
      workspaceDir: () => null,
      actor,
    }
    await expect(ensureImported('/w/brain.SVG', deps)).rejects.toThrow(/is an SVG, which this host cannot draw/)
    await expect(ensureImported('/w/brain.svg', { ...deps, rasterizeSvg: async () => '/cache/svg-import/k/brain.png' })).rejects.toThrow(/probing \/cache\/svg-import\/k\/brain.png failed/)
    expect(probed).toEqual(['/cache/svg-import/k/brain.png'])
    await expect(ensureImported('/w/bad.svg', { ...deps, rasterizeSvg: async () => { throw new Error('not an SVG this app can draw') } })).rejects.toThrow(/drawing \/w\/bad.svg failed: not an SVG/)
    expect(actor.snapshot().media_pool).toEqual({})
  })
})
