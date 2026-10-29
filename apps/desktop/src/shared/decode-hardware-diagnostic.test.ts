import { describe, expect, it } from 'vitest'
import { hardwareProbeDiagnostic } from './decode-hardware-diagnostic'
describe('hardware probe evidence classification', () => {
  it('accepts only the native probe’s observed software-frame verdict as unavailability', () => {
    const reason = 'decoder produced YUV420P, not the hw surface (hardware decode unavailable)'
    expect(hardwareProbeDiagnostic(reason)).toEqual({ kind: 'unavailable', reason })
    expect(hardwareProbeDiagnostic(reason, true).kind).toBe('failed')
  })
  it.each(['timeout', 'driver unsupported', 'file not found', 'no frame decoded', null])('does not turn %s into an environmental skip', reason => {
    expect(hardwareProbeDiagnostic(reason).kind).toBe('failed')
  })
})
