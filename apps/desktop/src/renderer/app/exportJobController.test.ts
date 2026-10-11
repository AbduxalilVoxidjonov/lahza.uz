import { beforeEach, expect, it, vi } from 'vitest';
import type { TFunction } from 'i18next';
import { createExportJobController } from './exportJobController';

const mock = vi.hoisted(() => ({
  listeners: new Map<string, (event: { payload: unknown }) => void>(),
  invoke: vi.fn(), summary: vi.fn(),
}));
vi.mock('@/bridge/ipc', () => ({ invoke: mock.invoke }));
vi.mock('@/bridge/events', () => ({
listen: async (name: string, callback: (event: { payload: unknown }) => void) => {
    mock.listeners.set(name, callback);
    return () => { mock.listeners.delete(name); };
  }
}));
vi.mock('../ipc', () => ({ projectSummary: mock.summary }));
vi.mock('./exportRunner', () => ({ createExportRunner: () => ({ state: () => null, discard: async () => { }, run: async () => { }, retry: async () => { } }) }));

beforeEach(() => { mock.listeners.clear(); mock.invoke.mockReset(); mock.summary.mockReset(); });
const controller = () => createExportJobController({
  previewRef: { current: null }, proxyStateRef: { current: new Map() }, decodeProbeMemo: { current: new Map() },
  t: vi.fn() as unknown as TFunction, onState: vi.fn(), onBegin: vi.fn(),
});

it('renews readiness after a workspace replacement without requiring the editor to remount', async () => {
  let generation = 1;
  mock.invoke.mockImplementation(async channel => channel === 'export_job_session' ? { root_id: 'root', generation } : undefined);
  mock.summary.mockResolvedValue({ root_id: 'root' });
  const c = controller(); await c.mount();
  expect(mock.invoke).toHaveBeenCalledWith('export_job_ready', expect.objectContaining({ generation: 1 }));
  mock.listeners.get('project:workspace-changing')!({ payload: {} });
  generation = 2;
  mock.listeners.get('export:session_ready')!({ payload: {} });
  await vi.waitFor(() => expect(mock.invoke).toHaveBeenCalledWith('export_job_ready', expect.objectContaining({ generation: 2 })));
  await c.dispose();
});

it('subscribes before hydration and recovers if mounting races an in-flight project open', async () => {
  let opening = true;
  mock.invoke.mockImplementation(async channel => {
    if (channel === 'export_job_session') {
      expect(mock.listeners.has('export:run')).toBe(true);
      if (opening) throw new Error('project_busy');
      return { root_id: 'new-root', generation: 3 };
    }
  });
  mock.summary.mockResolvedValue({ root_id: 'new-root' });
  const log = vi.spyOn(console, 'error').mockImplementation(() => { });
  const c = controller();
  try {
    await c.mount(); opening = false;
    mock.listeners.get('export:session_ready')!({ payload: {} });
    await vi.waitFor(() => expect(mock.invoke).toHaveBeenCalledWith('export_job_ready', expect.objectContaining({ root_id: 'new-root', generation: 3 })));
  } finally { await c.dispose(); log.mockRestore(); }
});
