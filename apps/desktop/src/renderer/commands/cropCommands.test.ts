import { afterEach, expect, it, vi } from 'vitest';
import { projectSummary, updateLayerParams } from '../ipc';
import { groupLayerFixture, summaryFixture } from '../testing/summaryFixture';
import { useProjectStore } from '../state/projectStore';
import { setLayerSelection, clearLayerSelection } from '../state/selectionStore';
import { beginCrop, endCrop, useCropEditingStore } from '../state/cropEditingStore';
import { resetCrop } from './cropCommands';

vi.mock('../ipc', async original => ({
  ...await original<typeof import('../ipc')>(),
  updateLayerParams: vi.fn(), projectSummary: vi.fn(),
}));

afterEach(() => { endCrop(); clearLayerSelection(); useProjectStore.getState().apply(null); vi.clearAllMocks(); });

it('waits for the crop command publication without reading and applying another snapshot', async () => {
  const layer = groupLayerFixture({ id: 'clip' });
  if (layer.params.kind !== 'CompositionRef') throw new Error('fixture');
  const { composition_id: _id, composition_label: _label, ...transform } = layer.params;
  layer.kind = 'VideoClip';
  layer.params = { ...transform, kind: 'VideoClip', media_id: 'media', media_label: 'video',
    speed: 1, flip_h: false, flip_v: false, fade_in_us: 0, fade_out_us: 0,
    crop: { x: 0.25, y: 0.25, w: 0.5, h: 0.5 } };
  const initial = summaryFixture({ root: { tracks: [{ id: 'track', label: null, kind: 'Video',
    enabled: true, locked: false, muted: false, solo: false, role: null, transient: false, layers: [layer] }] } });
  useProjectStore.getState().apply(initial); setLayerSelection('clip', ['clip']); beginCrop('clip');
  let publish!: () => void;
  vi.mocked(updateLayerParams).mockImplementation(() => new Promise<void>(resolve => {
    publish = () => {
      const next = structuredClone(initial);
      const params = next.compositions[next.root_id]!.tracks[0]!.layers[0]!.params;
      if (params.kind !== 'VideoClip') throw new Error('fixture');
      params.crop = null;
      useProjectStore.getState().apply(next);
      resolve();
    };
  }));
  let done = false;
  const resetting = resetCrop().then(() => { done = true; });
  await Promise.resolve();
  expect(done).toBe(false);
  expect(useCropEditingStore.getState().layerId).toBeNull();
  expect(updateLayerParams).toHaveBeenCalledExactlyOnceWith('clip', { kind: 'VideoClip', crop: null });
  publish(); await resetting;
  expect(projectSummary).not.toHaveBeenCalled();
  expect(useProjectStore.getState().layerById.get('clip')!.params).toMatchObject({ crop: null });
});
