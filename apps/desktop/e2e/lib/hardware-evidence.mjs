/** Returns a documented skip reason only for affirmative unavailability.
 * All other software paths are failures, never hardware coverage. `before`
 * is the pre-sampling snapshot; check again after pixel/SSIM measurements. */
export function verifyHardwareEvidence(current, lane, { required = false, before } = {}) {
  if (!current) throw new Error('Hardware evidence missing: no active clip')
  const details = JSON.stringify(current)
  if (current.hwFallbackCount > 0 || (before && current.hwFallbackCount !== before.hwFallbackCount))
    throw new Error(`Hardware decode fell back during the session: ${details}`)
  if (current.hwDiagnostic?.kind === 'failed')
    throw new Error(`Hardware probe/session failed: ${details}`)
  if (current.sourceKind === 'native-gpu' && current.hwLane === lane) {
    if (current.hwFallbackCount !== 0) throw new Error(`Hardware fallback history missing: ${details}`)
    return null
  }
  if (!required && !before && current.sourceKind === 'sw' && current.hwLane === null
      && current.hwDiagnostic?.kind === 'unavailable') return current.hwDiagnostic.reason
  throw new Error(`Required hardware lane ${lane} did not remain engaged: ${details}`)
}

export function hardwareRequired(lane, codec, platform, requiredVariants = '') {
  const allowed = new Set(['nvdec-h264', 'vaapi-h264', 'd3d11va-h264', 'videotoolbox-h264', 'videotoolbox-hevc10', 'videotoolbox-prores'])
  const selected = requiredVariants.split(',').map(x => x.trim()).filter(Boolean)
  for (const item of selected) if (!allowed.has(item)) throw new Error(`Unknown WEFTCUT_REQUIRE_HW_VARIANTS value: ${item}`)
  return selected.includes(`${lane}-${codec}`)
    || (platform === 'darwin' && lane === 'videotoolbox' && ['h264', 'hevc10'].includes(codec))
}
