import { expect, it } from 'vitest';
import { shareSnapshot } from './shareSnapshot';

it('keeps unchanged JSON branches while additions, deletions, order and type changes remain authoritative', () => {
  const before = { nested: { removed: true, stable: { value: 1 } }, values: [1, 2], kind: { n: 3 } };
  const next = { nested: { stable: { value: 1 }, added: false }, values: [2, 1, 3], kind: null };
  const result = shareSnapshot<unknown>(before, next) as typeof next;
  expect(result).toEqual(next);
  expect(result.nested.stable).toBe(before.nested.stable);
  expect(before.nested.removed).toBe(true);
  expect(next.nested.stable).not.toBe(before.nested.stable);
  expect(shareSnapshot(result, structuredClone(result))).toBe(result);
  expect(shareSnapshot<unknown>([1, 2], [1])).toEqual([1]);
  expect(shareSnapshot<unknown>({ 0: 1 }, [1])).toEqual([1]);
});
