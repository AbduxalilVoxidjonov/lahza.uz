import { test } from 'node:test'
import assert from 'node:assert/strict'
import { verifyHardwareEvidence, hardwareRequired, windowsSoftwareOnly, linuxHardwareAbsent } from './hardware-evidence.mjs'
const hw = { sourceKind: 'native-gpu', hwLane: 'videotoolbox', hwDiagnostic: null, hwFallbackCount: 0 }
const sw = { ...hw, sourceKind: 'sw', hwLane: null }

test('auto cannot hide a VAAPI failure behind the absence of NVIDIA', () => {
  const intel = { inventory_reason: null, devices: [{ vendor_id: 0x8086, render_nodes: ['/dev/dri/renderD128'] }] }
  assert.equal(linuxHardwareAbsent(intel), true)
  assert.equal(linuxHardwareAbsent(intel, true), false)
  assert.equal(linuxHardwareAbsent({ inventory_reason: null, devices: [] }, true), true)
  assert.equal(linuxHardwareAbsent({ inventory_reason: 'unknown', devices: [] }, true), false)
  assert.equal(linuxHardwareAbsent({ inventory_reason: null, devices: [{ vendor_id: null }] }), false)
})
test('only a named hardware lane with intact history passes', () => {
  assert.equal(verifyHardwareEvidence(hw, 'videotoolbox'), null)
  assert.throws(() => verifyHardwareEvidence(hw, 'nvdec'))
  assert.throws(() => verifyHardwareEvidence({ sourceKind: 'native-gpu', hwLane: 'videotoolbox' }, 'videotoolbox'))
})
test('optional confirmed unavailability skips, while mandatory hardware fails', () => {
  const absent = { ...sw, hwDiagnostic: { kind: 'unavailable', reason: 'no advertised hardware lane' } }
  assert.equal(verifyHardwareEvidence(absent, 'videotoolbox'), 'no advertised hardware lane')
  assert.throws(() => verifyHardwareEvidence(absent, 'videotoolbox', { required: true }))
  assert.throws(() => verifyHardwareEvidence({ ...absent, hwFallbackCount: undefined }, 'videotoolbox'))
})

test('only an affirmative software-only Windows inventory permits an environment skip', () => {
  const software = { vendorId: 0x1414, deviceId: 0x008c }
  assert.equal(windowsSoftwareOnly({ gpuDevice: [software] }), true)
  for (const info of [null, {}, { gpuDevice: [] }, { gpuDevice: [{}] },
    { gpuDevice: [{ vendorId: 0x1414, deviceId: 0 }] },
    { gpuDevice: [software, { vendorId: 0x10de, deviceId: 1 }] }]) {
    assert.equal(windowsSoftwareOnly(info), false)
  }
})
for (const reason of ['timeout', 'probe-exited', 'resource-busy', 'probe-busy', 'probe IPC failed', 'unknown']) {
  test(`${reason} can never become a clean skip`, () => {
    assert.throws(() => verifyHardwareEvidence({ ...sw, hwDiagnostic: { kind: 'failed', reason } }, 'videotoolbox'), /failed/)
  })
}
test('an unexplained software path fails closed', () => {
  assert.throws(() => verifyHardwareEvidence(sw, 'videotoolbox'))
})
test('post-sampling hardware recovery cannot erase an intervening fallback', () => {
  assert.throws(() => verifyHardwareEvidence({ ...hw, hwFallbackCount: 1 }, 'videotoolbox', { before: hw }), /fell back/)
  assert.throws(() => verifyHardwareEvidence({ ...sw, hwDiagnostic: { kind: 'unavailable', reason: 'gone' } }, 'videotoolbox', { before: hw }))
})
test('macOS baseline formats are mandatory; ProRes can be explicitly required', () => {
  assert.equal(hardwareRequired('videotoolbox', 'h264', 'darwin'), true)
  assert.equal(hardwareRequired('videotoolbox', 'hevc10', 'darwin'), true)
  assert.equal(hardwareRequired('videotoolbox', 'prores', 'darwin'), false)
  assert.equal(hardwareRequired('videotoolbox', 'prores', 'darwin', 'videotoolbox-prores'), true)
  assert.throws(() => hardwareRequired('videotoolbox', 'h264', 'darwin', 'videotoolbox-h246'))
})
