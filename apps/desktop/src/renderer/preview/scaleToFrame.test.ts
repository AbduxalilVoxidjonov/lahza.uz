import { describe, expect, it } from 'vitest';
import { layerQuad, type LayerQuadInput } from './gizmoGeometry';
import { quadAabb } from './previewSnap';
import { scaleToFrame } from './scaleToFrame';

const base: LayerQuadInput = { x: 213, y: -45, naturalW: 640, naturalH: 360,
  scaleX: 1, scaleY: 1, anchorX: 0.5, anchorY: 0.5, rotationDeg: 0, };

describe('scaleToFrame', () => {
  it('fits a landscape source in a portrait frame without clipping', () => {
    const result = scaleToFrame(base, 360, 640, 'fit')!;
    expect(result.scaleX).toBe(360 / 640);
    expect(result.scaleY).toBe(result.scaleX);
    expect(result.x).toBeCloseTo(180);
    expect(result.y).toBeCloseTo(320);
  });

  it('fills a portrait frame without leaving gaps', () => {
    const result = scaleToFrame(base, 360, 640, 'fill')!;
    expect(result.scaleX).toBe(640 / 360);
    expect(result.y).toBeCloseTo(320);
    expect(result.x).toBeCloseTo(180);
  });

  it.each([0, 31, 90, 137])('fits cropped, mirrored content at %s degrees with an off-center anchor', rotationDeg => {
    const frame = { ...base, rotationDeg, anchorX: 0.1, anchorY: 0.8, scaleX: -2, scaleY: 0.7,
      flipX: true, visibleRect: { x: 0.3, y: 0.1, w: 0.4, h: 0.8 } };
    const result = scaleToFrame(frame, 1280, 720, 'fit')!;
    const box = quadAabb(layerQuad({ ...frame, ...result }))!;
    expect(box.left).toBeGreaterThanOrEqual(-1e-7);
    expect(box.top).toBeGreaterThanOrEqual(-1e-7);
    expect(box.right).toBeLessThanOrEqual(1280 + 1e-7);
    expect(box.bottom).toBeLessThanOrEqual(720 + 1e-7);
    expect((box.left + box.right) / 2).toBeCloseTo(640);
    expect((box.top + box.bottom) / 2).toBeCloseTo(360);
    expect(result.scaleX / result.scaleY).toBeCloseTo(frame.scaleX / frame.scaleY);
    expect(Math.max((box.right - box.left) / 1280, (box.bottom - box.top) / 720)).toBeCloseTo(1);
  });

  it.each([0, 31, 90, 137])('covers every composition corner when filling at %s degrees', rotationDeg => {
    const frame = { ...base, rotationDeg, anchorX: 0.1, anchorY: 0.8, scaleX: -2, scaleY: 0.7,
      flipX: true, visibleRect: { x: 0.3, y: 0.1, w: 0.4, h: 0.8 } };
    const result = scaleToFrame(frame, 1280, 720, 'fill')!;
    const [a, b, , d] = layerQuad({ ...frame, ...result });
    const ux = b.x - a.x, uy = b.y - a.y, vx = d.x - a.x, vy = d.y - a.y;
    for (const p of [{ x: 0, y: 0 }, { x: 1280, y: 0 }, { x: 1280, y: 720 }, { x: 0, y: 720 }]) {
      const u = ((p.x - a.x) * ux + (p.y - a.y) * uy) / (ux * ux + uy * uy);
      const v = ((p.x - a.x) * vx + (p.y - a.y) * vy) / (vx * vx + vy * vy);
      expect(u).toBeGreaterThanOrEqual(-1e-7);
      expect(u).toBeLessThanOrEqual(1 + 1e-7);
      expect(v).toBeGreaterThanOrEqual(-1e-7);
      expect(v).toBeLessThanOrEqual(1 + 1e-7);
    }
  });

  it('rejects unknown, collapsed and non-finite geometry', () => {
    expect(scaleToFrame({ ...base, scaleX: 0 }, 1280, 720, 'fill')).toBeNull();
    expect(scaleToFrame({ ...base, naturalW: NaN }, 1280, 720, 'fit')).toBeNull();
    expect(scaleToFrame(base, 0, 720, 'fit')).toBeNull();
  });
});
