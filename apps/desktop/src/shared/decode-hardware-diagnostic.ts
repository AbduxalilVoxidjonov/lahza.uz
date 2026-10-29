/** Session evidence, not a user preference or a project property. Unknown
 * failures must never be presented as proof that hardware is unsupported. */
export interface DecodeHardwareDiagnostic {
  kind: 'unavailable' | 'failed'
  reason: string
}

export function hardwareProbeDiagnostic(reason: string | null, transient = false): DecodeHardwareDiagnostic {
  // This exact message is emitted by our native one-frame probe only after
  // decoding a SOFTWARE frame. Do not classify arbitrary driver/file errors
  // by fuzzy words such as "unsupported" or "not found".
  const softwareFrame = /^decoder produced .+, not the hw surface \(hardware decode unavailable\)$/.test(reason ?? '')
  return { kind: !transient && softwareFrame ? 'unavailable' : 'failed', reason: reason ?? 'hardware probe returned no diagnostic' }
}
