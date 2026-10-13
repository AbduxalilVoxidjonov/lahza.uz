// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { ROOT_ID, summaryFixture } from '../testing/summaryFixture';
import { useProjectStore } from './projectStore';
import { useAnchorFrame } from './playheadProjection';

afterEach(cleanup);

it('does not rerender the timeline clock on marker edits, but updates on fps changes', () => {
  const initial = summaryFixture({ root: { markers: [{ id: 'm', t_us: 0, end_t_us: null,
    label: '', note: '', color_hint: '#ffffff', anchor_layer: null, anchor_src_us: null, hibernating: false }] } });
  useProjectStore.getState().apply(initial);
  let renders = 0;
  const hook = renderHook(() => { renders++; return useAnchorFrame(ROOT_ID); });
  const before = hook.result.current;
  const moved = structuredClone(initial);
  moved.compositions[ROOT_ID]!.markers[0]!.t_us = 1_000_000;
  act(() => useProjectStore.getState().apply(moved));
  expect(renders).toBe(1);
  expect(hook.result.current).toBe(before);
  const faster = structuredClone(moved); faster.compositions[ROOT_ID]!.fps_num = 60;
  act(() => useProjectStore.getState().apply(faster));
  expect(hook.result.current?.fpsNum).toBe(60);
  expect(renders).toBe(2);
});
