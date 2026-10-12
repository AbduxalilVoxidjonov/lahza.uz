import { untestedAcceleration, type HardwareAccelerationDiagnostics, type HardwareDiagnostics } from '../shared/hardware-diagnostics';

export interface HardwareDiagnosticsDependencies {
  inventory(): Promise<HardwareDiagnostics>;
  chromium(): HardwareDiagnostics['chromium'];
  probe(devices: HardwareDiagnostics['devices'], publish: (result: HardwareAccelerationDiagnostics) => void): Promise<HardwareAccelerationDiagnostics>;
  stop(): void;
  now?: () => number;
}

/** Share one inventory/probe across windows. Polling never runs codec probes. */
export function createHardwareDiagnosticsService(deps: HardwareDiagnosticsDependencies) {
  const now = deps.now ?? Date.now;
  let inventory: HardwareDiagnostics | undefined;
  let inventoryTask: Promise<HardwareDiagnostics> | undefined;
  let probeTask: Promise<HardwareAccelerationDiagnostics> | undefined;
  let acceleration = untestedAcceleration();
  let generation = 0;
  let stopped = false;
  const read = async (refresh = false): Promise<HardwareDiagnostics> => {
    if (!inventory || refresh || now() - inventory.sampled_at >= 10_000) {
      if (!inventoryTask) {
        const version = generation;
        inventoryTask = deps.inventory().then(result => {
          if (version === generation) inventory = result;
          return result;
        }).finally(() => { inventoryTask = undefined; });
      }
      const result = await inventoryTask;
      return { ...result, chromium: deps.chromium(), acceleration };
    }
    return { ...inventory, chromium: deps.chromium(), acceleration };
  };
  return {
    read,
    invalidate() { generation++; inventory = undefined; acceleration = untestedAcceleration(); },
    probe(): Promise<HardwareAccelerationDiagnostics> {
      if (probeTask) return probeTask;
      if (stopped) return Promise.resolve({ ...untestedAcceleration(), status: 'failed', reason: 'probe-failed' });
      acceleration = { ...untestedAcceleration(), status: 'running', sampled_at: now() };
      probeTask = read().then(async snapshot => {
        if (stopped) throw new Error('Hardware diagnostics stopped');
        const version = generation;
        const result = await deps.probe(snapshot.devices, result => { if (version === generation) acceleration = result; });
        if (version === generation) acceleration = result;
        return acceleration;
      })
        .catch(error => {
          const reason = (error as { hardwareReason?: HardwareAccelerationDiagnostics['reason'] })?.hardwareReason ?? 'probe-failed';
          acceleration = { ...acceleration, status: 'failed', reason, sampled_at: now() };
          return acceleration;
        }).finally(() => { probeTask = undefined; });
      return probeTask;
    },
    stop() { stopped = true; deps.stop(); },
  };
}
