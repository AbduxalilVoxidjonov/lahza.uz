import { afterEach, describe, expect, it, vi } from 'vitest'
import { currentEditTrace, EditTrace, EDIT_TRACE_PREFIX, measureEditStage, runEditTrace } from './editTrace'

afterEach(() => vi.restoreAllMocks())

describe('temporary edit timing scopes', () => {
  it('measures nested stages with a monotonic clock and restores scope after failure', () => {
    let now = 0
    vi.spyOn(performance, 'now').mockImplementation(() => now)
    const log = vi.spyOn(console, 'info').mockImplementation(() => {})
    const error = new Error('test refusal')
    expect(() => runEditTrace('outer', 'main.command', () => {
      measureEditStage('recipe', () => { now += 10 })
      try { runEditTrace('inner', 'nested', () => { now += 5; throw error }) } catch { /* intentional */ }
      expect(currentEditTrace()?.id).toBe('outer')
      measureEditStage('validate', () => { now += 7; throw error })
    })).toThrow(error)
    expect(currentEditTrace()).toBeUndefined()
    const result = JSON.parse(String(log.mock.calls[1]![0]).slice(EDIT_TRACE_PREFIX.length + 1))
    expect(result).toMatchObject({ traceId: 'outer', durationMs: 22, ok: false,
      spans: [{ stage: 'recipe', durationMs: 10, ok: true }, { stage: 'validate', durationMs: 7, ok: false }] })
  })

  it('is silent when disabled and a failing diagnostic sink cannot reject edits', () => {
    const log = vi.spyOn(console, 'info').mockImplementation(() => { throw new Error('sink') })
    expect(runEditTrace(undefined, 'off', () => measureEditStage('work', () => 42))).toBe(42)
    expect(log).not.toHaveBeenCalled()
    expect(runEditTrace('on', 'on', () => 42)).toBe(42)
    expect(currentEditTrace()).toBeUndefined()
  })

  it('bounds recorded spans', () => {
    const log = vi.spyOn(console, 'info').mockImplementation(() => {})
    const trace = new EditTrace('bounded', 'test')
    for (let i = 0; i < 100; i++) trace.measure('nested', () => {})
    trace.report()
    expect(JSON.parse(String(log.mock.calls[0]![0]).slice(EDIT_TRACE_PREFIX.length + 1)).spans).toHaveLength(64)
  })
})
