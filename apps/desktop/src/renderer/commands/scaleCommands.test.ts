import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AnimTrack, LayerParamsView } from '../ipc';
import { clearGizmoProbe, registerGizmoProbe, type GizmoProbe } from '../preview/gizmoProbeRegistry';
import { setPreviewRenderTarget } from '../state/compositionAnchorStore';
import { setPlayheadTimeUs } from '../state/playheadStore';
import { useProjectStore } from '../state/projectStore';
import { clearLayerSelection, setLayerSelection } from '../state/selectionStore';
import { compositionFixture, groupLayerFixture, summaryFixture } from '../testing/summaryFixture';
import { canScaleLayer, scalePrimaryLayer } from './scaleCommands';

const commit = vi.fn();
const pathCommit = vi.fn();
const emit = vi.fn();
vi.mock('../ipc', async importOriginal => ({ ...await importOriginal<typeof import('../ipc')>(),
  updateLayerParamTracks: (...args: unknown[]) => commit(...args),
  updatePathTransform: (...args: unknown[]) => pathCommit(...args),
  logEmit: (...args: unknown[]) => emit(...args),
}));
const stat = (value: number): AnimTrack<number> => ({ mode: 'Static', value });
let staged = true;
const probe: GizmoProbe = { canvasRect: () => null, textFitOf: () => null,
  naturalSizeOf: () => staged ? { w: 640, h: 360 } : null };

function fixture(params: Record<string, unknown> = {}, locked = false, trackLocked = false) {
  const layer = groupLayerFixture({ id: 'layer', tStartUs: 2_000_000, tEndUs: 4_000_000, locked });
  layer.params = { ...layer.params, kind: 'VideoClip', x: stat(100), y: stat(50), ...params } as unknown as LayerParamsView;
  return summaryFixture({ root: { width: 360, height: 640, duration_us: 4_000_000,
    tracks: [{ id: 'track', kind: 'Video', label: null, enabled: true, locked: trackLocked, muted: false,
      solo: false, role: null, transient: false, layers: [layer] }] },
    groups: [compositionFixture({ id: 'other' })] });
}

beforeEach(() => {
  vi.clearAllMocks();
  staged = true;
  registerGizmoProbe(probe);
  useProjectStore.getState().apply(fixture());
  setPreviewRenderTarget(null);
  setLayerSelection('layer', ['layer']);
  setPlayheadTimeUs(2_511_000);
});
afterEach(() => {
  clearGizmoProbe(probe);
  setPreviewRenderTarget(null);
  clearLayerSelection();
  useProjectStore.getState().apply(null);
});

describe('preview scale commands', () => {
  it('fits and centers in one batch without writing the anchor', async () => {
    await scalePrimaryLayer('fit');
    expect(commit).toHaveBeenCalledTimes(1);
    const entries = Object.fromEntries(commit.mock.calls[0]![1]);
    expect(entries).toEqual({ scale_x: stat(0.5625), scale_y: stat(0.5625), x: stat(180), y: stat(320) });
  });

  it('fills and centers in one batch', async () => {
    await scalePrimaryLayer('fill');
    const entries = Object.fromEntries(commit.mock.calls[0]![1]);
    expect(entries.scale_x).toEqual(stat(640 / 360));
    expect(entries.y).toEqual(stat(320));
  });

  it('restores scales alone even when the layer has not been staged, preserving mirrors', async () => {
    staged = false;
    useProjectStore.getState().apply(fixture({ scale_x: stat(-2), scale_y: stat(3) }));
    await scalePrimaryLayer('original');
    expect(commit).toHaveBeenCalledWith('layer', [['scale_x', stat(-1)], ['scale_y', stat(1)]]);
    expect(pathCommit).not.toHaveBeenCalled();
  });

  it('preserves keyframes and writes at the frame-snapped layer time', async () => {
    const keyed: AnimTrack<number> = { mode: 'Keyframed', extrapolate: { before: 'Hold', after: 'Hold' }, value: [
      { id: 'scale-key', t_us: 0, value: 1, in: { x: 2 / 3, y: 2 / 3, mode: 'Free' },
        out: { x: 1 / 3, y: 1 / 3, mode: 'Free' }, continuity: 'Broken', segment: { kind: 'Linear' } },
    ] };
    useProjectStore.getState().apply(fixture({ scale_x: keyed, scale_y: keyed }));
    await scalePrimaryLayer('fit');
    const entries = Object.fromEntries(commit.mock.calls[0]![1]);
    expect(entries.scale_x.mode).toBe('Keyframed');
    expect(entries.scale_x.value).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: 'scale-key', t_us: 0, value: 1 }),
      expect.objectContaining({ t_us: 500_000, value: 0.5625 }),
    ]));
  });

  it('scales and translates a motion path atomically without replacing it with XY', async () => {
    useProjectStore.getState().apply(fixture({ position: { mode: 'Path', progress: stat(0), path: { nodes: [
      { id: 'node-a', point: { x: 100, y: 50 }, in_handle: { x: 0, y: 0 }, out_handle: { x: 0, y: 0 }, segment: 'Line', tangent_mode: 'Corner' },
      { id: 'node-b', point: { x: 200, y: 150 }, in_handle: { x: 0, y: 0 }, out_handle: { x: 0, y: 0 }, segment: 'Line', tangent_mode: 'Corner' },
    ] } } }));
    await scalePrimaryLayer('fit');
    expect(commit).not.toHaveBeenCalled();
    expect(pathCommit).toHaveBeenCalledWith('layer', 80, 270,
      [['scale_x', stat(0.5625)], ['scale_y', stat(0.5625)]]);
  });

  it('does not create redundant edits', async () => {
    await scalePrimaryLayer('original');
    expect(commit).not.toHaveBeenCalled();
    useProjectStore.getState().apply(fixture({ scale_x: stat(0.5625), scale_y: stat(0.5625), x: stat(180), y: stat(320) }));
    await scalePrimaryLayer('fit');
    expect(commit).not.toHaveBeenCalled();
  });

  it('refuses unstaged fitting without guessing dimensions', async () => {
    staged = false;
    await scalePrimaryLayer('fit');
    expect(commit).not.toHaveBeenCalled();
    expect(emit).toHaveBeenCalledWith(expect.objectContaining({ i18n_key: 'log.scale_layer_unavailable' }));
  });

  it('requires an editable visual selection in the preview composition', async () => {
    for (const kind of ['VideoClip', 'ImageOverlay', 'Motif', 'CompositionRef']) {
      useProjectStore.getState().apply(fixture({ kind }));
      expect(canScaleLayer()).toBe(true);
    }
    for (const kind of ['Text', 'Color', 'Audio']) {
      useProjectStore.getState().apply(fixture({ kind }));
      expect(canScaleLayer()).toBe(false);
    }
    useProjectStore.getState().apply(fixture({}, true));
    expect(canScaleLayer()).toBe(false);
    await scalePrimaryLayer('fit');
    expect(commit).not.toHaveBeenCalled();
    useProjectStore.getState().apply(fixture({}, false, true));
    expect(canScaleLayer()).toBe(false);
    useProjectStore.getState().apply(fixture({}));
    setPreviewRenderTarget('other');
    expect(canScaleLayer()).toBe(false);
    setPreviewRenderTarget(null);
    clearLayerSelection();
    expect(canScaleLayer()).toBe(false);
  });
});
