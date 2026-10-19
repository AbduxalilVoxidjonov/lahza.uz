import { describe, expect, it } from 'vitest'
import { taskbarProgressArgs } from './taskbarProgress'

describe('taskbarProgressArgs', () => {
  it('maps each export status to a fraction and a mode', () => {
    expect(taskbarProgressArgs({ status: 'normal', progress: 42 })).toEqual({ progress: 0.42, mode: 'normal' })
    expect(taskbarProgressArgs({ status: 'indeterminate' })).toEqual({ progress: 2, mode: 'indeterminate' })
    expect(taskbarProgressArgs({ status: 'error', progress: 100 })).toEqual({ progress: 1, mode: 'error' })
    expect(taskbarProgressArgs({ status: 'paused', progress: 10 })).toEqual({ progress: 0.1, mode: 'paused' })
    expect(taskbarProgressArgs({ status: 'none' })).toEqual({ progress: -1, mode: 'none' })
  })

  it('clamps the percentage', () => {
    expect(taskbarProgressArgs({ status: 'normal', progress: 250 }).progress).toBe(1)
    expect(taskbarProgressArgs({ status: 'normal', progress: -5 }).progress).toBe(0)
    expect(taskbarProgressArgs({ status: 'normal', progress: Number.NaN }).progress).toBe(0)
  })

  it('clears the bar for malformed input instead of throwing', () => {
    for (const bad of [undefined, null, 'normal', { status: 'bogus' }, { progress: 50 }]) {
      expect(taskbarProgressArgs(bad)).toEqual({ progress: -1, mode: 'none' })
    }
  })
})
