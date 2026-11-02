"""Host-reja koordinata matematikasi render grafi (render/graph.py) bilan bir xil kadr berishining isboti.

Render: crop (x, y, w, h) -> scale=W:H. Chiqish pikseli markazi X -> manba u = x + X * w / W.
Host: qatlam anchor = manba markazi, `pos` ga qo'yiladi, `scale` bilan: u = sw/2 + (X - pos_x) / scale.
"""

from __future__ import annotations

import numpy as np
import pytest

from lahza_engine.hostplan.build import (
    crop_keys_to_transform,
    crop_transform,
    fit_blur_layers,
    layers_for_piece,
)
from lahza_engine.reframe.planner import CropKey, LayoutSegment, crop_rect
from lahza_engine.render.graph import SPLIT_HALF_ASPECT, Piece
from lahza_engine.types import Layout


def _render_coords(x, y, w, h, W, H):
    """Render (crop + scale) bo'yicha har chiqish pikseli markazining manba koordinatasi."""
    X = np.arange(W) + 0.5
    Y = np.arange(H) + 0.5
    return x + X * w / W, y + Y * h / H


def _host_coords(scale_pct, pos_x, pos_y, sw, sh, W, H, rect=None):
    rx, ry, rw, rh = rect or (0, 0, W, H)
    X = np.arange(rx, rx + rw) + 0.5
    Y = np.arange(ry, ry + rh) + 0.5
    s = scale_pct / 100
    return sw / 2 + (X - pos_x) / s, sh / 2 + (Y - pos_y) / s


def _sample(img, u, v):
    iu = np.clip(np.floor(u).astype(int), 0, img.shape[1] - 1)
    iv = np.clip(np.floor(v).astype(int), 0, img.shape[0] - 1)
    return img[np.ix_(iv, iu)]


@pytest.mark.parametrize("cx,cy,zoom", [(0.5, 0.5, 1.0), (0.3, 0.5, 1.0), (0.05, 0.5, 1.0),
                                        (0.7, 0.4, 1.5), (0.95, 0.9, 2.0)])
def test_square_output_is_pixel_identical(cx, cy, zoom):
    """1:1 chiqishda crop nisbati aniq (w == h) - host kadri render kadri bilan piksel-piksel bir xil."""
    sw, sh, W, H = 1920, 1080, 1080, 1080
    rng = np.random.default_rng(1)
    img = rng.integers(0, 255, size=(sh, sw), dtype=np.uint8)
    x, y, w, h = crop_rect(cx, sw, sh, W / H, zoom, cy)
    assert w * H == h * W
    s, px, py = crop_transform(x, y, w, h, sw, sh, (0, 0, W, H))
    ru, rv = _render_coords(x, y, w, h, W, H)
    hu, hv = _host_coords(s, px, py, sw, sh, W, H)
    assert np.allclose(ru, hu) and np.allclose(rv, hv)
    assert np.array_equal(_sample(img, ru, rv), _sample(img, hu, hv))


@pytest.mark.parametrize("cx,zoom", [(0.5, 1.0), (0.2, 1.0), (0.8, 1.3)])
def test_vertical_output_matches_within_rounding(cx, zoom):
    """9:16: gorizontal aniq; vertikal farq faqat crop enini juft songa yaxlitlashdan (<= 0.3%)."""
    sw, sh, W, H = 1920, 1080, 1080, 1920
    x, y, w, h = crop_rect(cx, sw, sh, W / H, zoom)
    s, px, py = crop_transform(x, y, w, h, sw, sh, (0, 0, W, H))
    assert s == pytest.approx(W / w * 100)
    ru, rv = _render_coords(x, y, w, h, W, H)
    hu, hv = _host_coords(s, px, py, sw, sh, W, H)
    assert np.allclose(ru, hu)
    assert np.max(np.abs(rv - hv)) <= 0.003 * h + 1e-6
    # Kadr markazi aynan bir xil manba nuqtasiga tushadi.
    assert sw / 2 + (W / 2 - px) / (s / 100) == pytest.approx(x + w / 2)
    assert sh / 2 + (H / 2 - py) / (s / 100) == pytest.approx(y + h / 2)


def test_keys_follow_render_camera_path_including_clamp():
    """Render har kadrda crop_rect(lerp(cx)) (clamp bilan) hisoblaydi; host kalitlari orasidagi chiziqli
    interpolyatsiya shu yo'ldan <= 2.5 manba px (render x ni butun/juft songa yaxlitlaydi) farq qiladi - kadr chetida ham."""
    sw, sh, W, H = 1920, 1080, 1080, 1920
    keys = [CropKey(0, 0.0, cut=True), CropKey(1000, 0.6), CropKey(2000, 1.0)]
    tks = crop_keys_to_transform(keys, sw, sh, W / H, (0, 0, W, H))
    assert len(tks) > len(keys)  # clamp chegaralarida qo'shimcha kalitlar
    ts = np.array([k.t for k in tks])
    xs = np.array([k.pos_x for k in tks])
    for t_ms in range(0, 2001, 20):
        t = t_ms / 1000
        cx = 0.6 * t if t <= 1.0 else 0.6 + 0.4 * (t - 1.0)
        x, y, w, h = crop_rect(cx, sw, sh, W / H, 1.0)
        _, px_render, _ = crop_transform(x, y, w, h, sw, sh, (0, 0, W, H))
        px_host = float(np.interp(t, ts, xs))
        assert abs(px_host - px_render) <= 2.5 * W / w, (t, px_host, px_render)


def test_cut_makes_previous_key_hold():
    tks = crop_keys_to_transform([CropKey(0, 0.3, cut=True), CropKey(500, 0.35), CropKey(800, 0.8, cut=True)],
                                 1920, 1080, 9 / 16, (0, 0, 1080, 1920))
    assert [k.interp for k in tks] == ["linear", "hold", "linear"]
    assert tks[2].t == pytest.approx(0.8)


def test_constant_zoom_per_piece_like_render():
    tks = crop_keys_to_transform([CropKey(0, 0.5, zoom=1.5, cut=True), CropKey(400, 0.5, zoom=2.0)],
                                 1920, 1080, 9 / 16, (0, 0, 1080, 1920))
    assert len({k.scale_pct for k in tks}) == 1
    _, _, w, _ = crop_rect(0.5, 1920, 1080, 9 / 16, 1.5)
    assert tks[0].scale_pct == pytest.approx(1080 / w * 100, rel=1e-4)


def test_fit_blur_layers():
    bg, main = fit_blur_layers(1920, 1080, 1080, 1920)
    assert bg.role == "bg" and main.role == "main"
    assert bg.keys[0].scale_pct == pytest.approx(1920 / 1080 * 100, rel=1e-4)  # balandlik to'ladi
    assert main.keys[0].scale_pct == pytest.approx(1080 / 1920 * 100, rel=1e-4)  # en sig'adi (render: scale=W:-2)
    assert (main.keys[0].pos_x, main.keys[0].pos_y) == (540, 960)
    assert bg.effects[0].kind == "gaussian_blur" and not main.effects


def test_split_layers_fill_their_halves():
    sw, sh, W, H = 1920, 1080, 1080, 1920
    seg = LayoutSegment(0, 2000, Layout.SPLIT, keys=[CropKey(0, 0.25, cut=True)],
                        keys_b=[CropKey(0, 0.75, cut=True)])
    piece = Piece(0, 2000, 0, 2000, seg)
    top, bottom = layers_for_piece(piece, sw, sh, W, H)
    assert top.crop_rect == (0, 0, 1080, 960) and bottom.crop_rect == (0, 960, 1080, 960)
    assert pytest.approx(SPLIT_HALF_ASPECT) == W / (H // 2)
    for layer, cx, rect in ((top, 0.25, top.crop_rect), (bottom, 0.75, bottom.crop_rect)):
        x, y, w, h = crop_rect(cx, sw, sh, SPLIT_HALF_ASPECT)
        k = layer.keys[0]
        ru, rv = _render_coords(x, y, w, h, rect[2], rect[3])
        hu, hv = _host_coords(k.scale_pct, k.pos_x, k.pos_y, sw, sh, W, H, rect)
        assert np.allclose(ru, hu, atol=1e-3)
        assert np.max(np.abs(rv - hv)) <= 0.003 * h + 1e-3
