import { expect, it, vi } from 'vitest';
import { createHardwareDiagnosticsService } from './hardwareDiagnosticsService';
import { untestedAcceleration, type HardwareDiagnostics } from '../shared/hardware-diagnostics';

function fixture() {
  let time = 100;
  const snapshot: HardwareDiagnostics = { platform: 'linux', sampled_at: time, devices: [], render_device_id: null,
    inventory_reason: null, chromium: { compositing: 'enabled', rasterization: 'enabled', video_decode: 'enabled', video_encode: 'disabled_software' }, acceleration: untestedAcceleration() };
  const inventory = vi.fn(async () => ({ ...snapshot, sampled_at: time }));
  const probe = vi.fn(async (): Promise<ReturnType<typeof untestedAcceleration>> => ({ ...untestedAcceleration(), status: 'complete' }));
  const stop = vi.fn();
  const service = createHardwareDiagnosticsService({ inventory, probe, stop, chromium: () => snapshot.chromium, now: () => time });
  return { service, inventory, probe, stop, advance: () => { time += 10_001; } };
}
it('polls lightweight inventory with expiry and never probes media automatically', async () => {
  const f = fixture(); await f.service.read(); await f.service.read();
  expect(f.inventory).toHaveBeenCalledTimes(1); expect(f.probe).not.toHaveBeenCalled();
  f.advance(); await f.service.read(); expect(f.inventory).toHaveBeenCalledTimes(2);
});
it('coalesces explicit tests from multiple windows and permits rerunning after completion', async () => {
  const f = fixture(); const first = f.service.probe(); const second = f.service.probe();
  expect(first).toBe(second); await first;
  expect(f.probe).toHaveBeenCalledTimes(1); await f.service.probe(); expect(f.probe).toHaveBeenCalledTimes(2);
});
it('can retry a failed inventory request and invalidates on GPU changes', async () => {
  const f = fixture(); f.inventory.mockRejectedValueOnce(new Error('GPU query failed'));
  await expect(f.service.read()).rejects.toThrow('GPU query failed');
  await f.service.read(); f.service.invalidate(); await f.service.read(); expect(f.inventory).toHaveBeenCalledTimes(3);
});
it('keeps the reason for a failed probe and stops the child on shutdown', async () => {
  const f = fixture(); f.probe.mockRejectedValueOnce(Object.assign(new Error('deadline'), { hardwareReason: 'timeout' }));
  expect(await f.service.probe()).toMatchObject({ status: 'failed', reason: 'timeout' });
  f.service.stop(); expect(f.stop).toHaveBeenCalledTimes(1);
});

it('does not start a probe after shutdown while its inventory is still pending', async () => {
  const f = fixture();
  const snapshot = await f.inventory();
  let resolve!: (value: HardwareDiagnostics) => void;
  f.inventory.mockImplementationOnce(() => new Promise(done => { resolve = done; }));
  const task = f.service.probe(); f.service.stop(); resolve(snapshot);
  expect(await task).toMatchObject({ status: 'failed' });
  expect(f.probe).not.toHaveBeenCalled();
});

it('discards results when the graphics environment changes during a probe', async () => {
  const f = fixture(); let resolve!: (value: ReturnType<typeof untestedAcceleration>) => void;
  f.probe.mockImplementationOnce(() => new Promise(done => { resolve = done; }));
  const task = f.service.probe();
  await vi.waitFor(() => expect(f.probe).toHaveBeenCalled());
  f.service.invalidate(); resolve({ ...untestedAcceleration(), status: 'complete' });
  expect(await task).toMatchObject({ status: 'idle', sampled_at: null });
});
