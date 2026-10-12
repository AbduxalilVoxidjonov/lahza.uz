import { describe, expect, it } from "vitest";

import { anchorOr, anchorPivot, DEFAULT_ANCHOR } from "./anchorPivot";

/// Where the four corners of a `texW×texH` quad land once Pixi applies
/// `world = position + R·S·(local − pivot)`. The assertions below are about
/// RENDERED geometry, not about the intermediate pivot/position pair — that is
/// the invariant is scaling and rotation around the stored Position.
function worldCorners(
  r: { pivotX: number; pivotY: number; posX: number; posY: number },
  texW: number,
  texH: number,
  scaleX: number,
  scaleY: number,
  angleDeg = 0,
): Array<[number, number]> {
  const rad = (angleDeg * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  const map = (lx: number, ly: number): [number, number] => {
    const dx = (lx - r.pivotX) * scaleX;
    const dy = (ly - r.pivotY) * scaleY;
    return [r.posX + dx * cos - dy * sin, r.posY + dx * sin + dy * cos];
  };
  return [map(0, 0), map(texW, 0), map(texW, texH), map(0, texH)];
}

const base = {
  x: 100,
  y: 50,
  anchorX: 0.5,
  anchorY: 0.5,
  texW: 200,
  texH: 100,
};

describe("anchorPivot", () => {
  it("puts the pivot on the anchor in local (texture) space", () => {
    const r = anchorPivot(base);
    expect(r.pivotX).toBe(100);
    expect(r.pivotY).toBe(50);
  });

  it("scales around the stored anchor position", () => {
    for (const s of [0.25, 1, 2.5]) {
      const r = anchorPivot(base);
      const [tl] = worldCorners(r, base.texW, base.texH, s, s);
      expect(tl).toEqual([100 - 100 * s, 50 - 50 * s]);
    }
  });

  it("keeps the anchor fixed for non-uniform scale", () => {
    const r = anchorPivot(base);
    const [tl] = worldCorners(r, base.texW, base.texH, 3, 0.5);
    expect(tl).toEqual([-200, 25]);
  });

  it("mirrors a flip in place instead of moving the box", () => {
    // flip_h ⇒ the sprite renders at negative scale_x. The box must still
    // occupy the same centered footprint.
    const r = anchorPivot(base);
    const xs = worldCorners(r, base.texW, base.texH, -1, 1).map(([cx]) => cx);
    expect(Math.min(...xs)).toBe(0);
    expect(Math.max(...xs)).toBe(200);
  });

  it("rotates about the anchor, not the top-left", () => {
    const r = anchorPivot(base);
    const corners = worldCorners(r, base.texW, base.texH, 1, 1, 180);
    // 180° about the center swaps opposite corners: the box is unmoved.
    const xs = corners.map(([cx]) => cx);
    const ys = corners.map(([, cy]) => cy);
    expect(Math.min(...xs)).toBeCloseTo(0, 9);
    expect(Math.max(...xs)).toBeCloseTo(200, 9);
    expect(Math.min(...ys)).toBeCloseTo(0, 9);
    expect(Math.max(...ys)).toBeCloseTo(100, 9);
  });

  it("degrades to the old pivot-less transform at anchor (0, 0)", () => {
    const r = anchorPivot({ ...base, anchorX: 0, anchorY: 0});
    expect(r).toEqual({ pivotX: 0, pivotY: 0, posX: 100, posY: 50 });
  });

  it("lands at (x, y) before the first frame binds (EMPTY texture)", () => {
    for (const tex of [null, 0]) {
      const r = anchorPivot({ ...base, texW: tex, texH: tex });
      expect(r).toEqual({ pivotX: 0, pivotY: 0, posX: 100, posY: 50 });
    }
  });

  // An absent anchor coalesces to DEFAULT_ANCHOR, not to 0 — see `anchorOr`.
  it("coalesces an absent anchor to the stored default, not to zero", () => {
    for (const absent of [undefined, Number.NaN]) {
      expect(
        anchorPivot({ ...base, anchorX: absent, anchorY: absent }),
      ).toEqual(anchorPivot({ ...base, anchorX: 0.5, anchorY: 0.5 }));
    }
    expect(anchorOr(undefined)).toBe(DEFAULT_ANCHOR);
    expect(anchorOr(0)).toBe(0);
  });

});
