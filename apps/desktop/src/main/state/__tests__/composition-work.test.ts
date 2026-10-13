import { afterEach, describe, expect, it, vi } from 'vitest'
import { createActor } from '../actor'
import { seededGen } from '../ids'
import { blankProject, rootComposition } from '../model'
import * as helpers from '../mutations/helpers'

afterEach(() => vi.restoreAllMocks())

describe('composition envelope work', () => {
  it('canvas-only edits do not scan content in any history snapshot', () => {
    const idGen = seededGen()
    const initial = blankProject(idGen, 'canvas-work')
    const actor = createActor({ initial, idGen })
    const track = rootComposition(initial).tracks[0].id
    for (let i = 0; i < 12; i++) {
      expect(actor.dispatch('add_layer', { track, kind: 'color', t_start_us: i * 1_000_000, t_end_us: (i + 1) * 1_000_000 }).ok).toBe(true)
    }
    const before = actor.historyStatus()
    const autofit = vi.spyOn(helpers, 'applyDurationAutofit')
    expect(actor.dispatch('set_composition', { width: 1280, height: 720 }).ok).toBe(true)
    expect(autofit.mock.calls.length).toBe(0)
    expect(actor.historyStatus()).toEqual(before)
    for (let i = 12; i >= 0; i--) {
      const c = rootComposition(actor.snapshot())
      expect([c.width, c.height]).toEqual([1280, 720])
      if (i > 0) expect(c.duration_us).toBe(i * 1_000_000)
      expect(c.duration_pinned).toBe(false)
      if (i > 0) expect(actor.dispatch('undo', {}).ok).toBe(true)
    }
  })
})
