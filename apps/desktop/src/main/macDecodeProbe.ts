import { app, utilityProcess } from 'electron'
import path from 'node:path'
import { createDecodeProbeProcess } from './decodeProbeProcess'
import { reserveResources } from './resources'

export function createMacDecodeProbe() {
  const probe = createDecodeProbeProcess({
    spawn: () => utilityProcess.fork(path.join(import.meta.dirname, 'decodeProbe.js'), [], {
      serviceName: 'WeftCut decode probe', stdio: 'ignore',
    }),
    kill(child) {
      // utilityProcess.kill may send SIGTERM. Native driver calls cannot be
      // relied on to return to JS for graceful shutdown; terminate only the
      // child we still own (pid is cleared by Electron on exit).
      if (child.pid !== undefined) process.kill(child.pid, 'SIGKILL')
    },
    reserve: () => reserveResources(1, 192),
  })
  app.once('before-quit', () => probe.stop())
  return probe
}
