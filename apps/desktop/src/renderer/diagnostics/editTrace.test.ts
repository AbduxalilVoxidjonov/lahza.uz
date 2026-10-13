// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { observeEditFrames } from './editTrace';

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('does not attribute a frame timestamp before the edit to post-edit jank', () => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'performance'] });
  const callbacks: FrameRequestCallback[] = [];
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => { callbacks.push(cb); return callbacks.length; });
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  const log = vi.spyOn(console, 'info').mockImplementation(() => {});
  observeEditFrames('edit-00000000-0000-0000-0000-000000000000');
  callbacks.shift()!(-64); // current frame began before pointer release
  callbacks.shift()!(16);
  vi.advanceTimersByTime(2000);
  const result = JSON.parse(String(log.mock.calls[0]![0]).split('[DEBUG-edit-latency] ')[1]!);
  expect(result.maxFrameGapMs).toBe(16);
  expect(result.maxFrameGapOffsetMs).toBe(0);
  expect(result.framesOver50Ms).toBe(0);
});
