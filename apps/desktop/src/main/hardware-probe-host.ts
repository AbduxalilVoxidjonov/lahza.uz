import { runHardwareProbe, type HardwareProbeRequest } from './hardwareProbe';
import { createRequire } from 'node:module';

const native = createRequire(import.meta.url)('@weftcut/core') as { linuxHardwareProbeProcessGroup?: () => boolean };
const grouped = native.linuxHardwareProbeProcessGroup?.() === true;
process.parentPort.postMessage({ type: 'ready', grouped });

function finish(message: object, code: number) {
  // Exit only after the parent has received the result; process.exit can
  // otherwise discard the last IPC message and look like a failed probe.
  process.parentPort.once('message', () => process.exit(code));
  process.parentPort.postMessage(message);
}

process.parentPort.once('message', event => {
  if (!grouped) { finish({ type: 'failed', reason: 'component-unavailable' }, 1); return; }
  void runHardwareProbe(event.data as HardwareProbeRequest,
    result => process.parentPort.postMessage({ type: 'progress', result }))
    .then(result => finish({ type: 'complete', result }, 0))
    .catch(error => finish({ type: 'failed', detail: String(error).slice(0, 512) }, 1));
});
