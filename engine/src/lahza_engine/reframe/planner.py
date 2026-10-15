"""Reframe rejasi: aktiv spiker -> layout segmentlari -> silliq kamera yo'li (TZ 8-bo'lim).

Kirish - analiz chastotasidagi (masalan 5 fps) kuzatuvlar, vaqtlari KLIP (chiqish) vaqtida:
    Observation(t_ms, faces=[Box...], active_index | None, shot_cut: bool)
Chiqish - klip (chiqish) vaqtidagi layout segmentlari va crop kalit kadrlari.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lahza_engine.config import ReframeConfig
from lahza_engine.reframe.faces import Box
from lahza_engine.reframe.filters import OneEuroFilter, clamp_speed
from lahza_engine.types import Layout


@dataclass
class Observation:
    t_ms: int
    faces: list[Box] = field(default_factory=list)
    active_index: int | None = None  # ASD + diarizatsiya birlashmasi natijasi
    shot_cut: bool = False
    overlap_speech: bool = False
    speaker: str | None = None  # diarizatsiya bo'yicha shu daqiqadagi spiker (bo'lsa)


@dataclass
class CropKey:
    t_ms: int
    cx: float  # normallashgan markaz (0..1)
    cy: float = 0.5
    zoom: float = 1.0
    cut: bool = False  # True: oldingi kalitdan keskin kesim (interpolyatsiya qilinmaydi)


@dataclass
class LayoutSegment:
    start_ms: int
    end_ms: int
    layout: Layout
    keys: list[CropKey] = field(default_factory=list)
    # SPLIT uchun ikkinchi (pastki) kadr markazi
    keys_b: list[CropKey] = field(default_factory=list)


SPLIT_SWITCH_WINDOW_MS = 10_000
SPLIT_MIN_SWITCHES = 3
"""R0: "tez almashinuv" = oxirgi 10 s ichida >= 3 spiker almashuvi (Reframe-Eval'da tanlanadi)."""


def decide_layout(obs: Observation, recent_switches: int) -> Layout:
    if not obs.faces:
        return Layout.FIT_BLUR
    if len(obs.faces) >= 2 and (obs.overlap_speech or recent_switches >= SPLIT_MIN_SWITCHES):
        return Layout.SPLIT
    return Layout.FOCUS


def _hold_layouts(
    raw: list[tuple[int, Layout]], min_hold_ms: int, duration_ms: int | None = None
) -> list[tuple[int, Layout]]:
    """Layout tez-tez almashmasin: min_hold_ms dan qisqa bo'laklar qo'shnisiga yutiladi.

    Eng qisqa bo'lakdan boshlab, uzunroq qo'shnisiga qo'shiladi (yuz bir lahzaga yo'qolsa
    FIT_BLUR "miltillamaydi"). Birinchi bo'lak har doim 0 dan boshlanadi.
    """
    if not raw:
        return []
    runs: list[list] = []
    for t, lay in raw:
        if not runs or runs[-1][1] != lay:
            runs.append([t, lay])
    runs[0][0] = 0
    end_total = duration_ms if duration_ms is not None else max(raw[-1][0], runs[-1][0])

    def dur(i: int) -> int:
        end = runs[i + 1][0] if i + 1 < len(runs) else end_total
        return end - runs[i][0]

    while len(runs) > 1:
        short = [i for i in range(len(runs)) if dur(i) < min_hold_ms]
        if not short:
            break
        i = min(short, key=dur)
        if i == 0 or (i < len(runs) - 1 and dur(i + 1) > dur(i - 1)):
            runs[i + 1][0] = runs[i][0]  # keyingisi oldinga cho'ziladi
        del runs[i]
        merged: list[list] = []
        for r in runs:
            if merged and merged[-1][1] == r[1]:
                continue
            merged.append(r)
        runs = merged
    return [(int(t), lay) for t, lay in runs]


def _switch_times(obs: list[Observation], cfg: ReframeConfig) -> list[int]:
    """Spiker almashgan vaqtlar: diarizatsiya bo'lsa - u bo'yicha, aks holda faol yuz sakrashi.

    Sahna kesimidagi sakrash almashuv hisoblanmaydi (kamera almashgan, spiker emas).
    """
    out: list[int] = []
    if any(o.speaker for o in obs):
        last: str | None = None
        for o in obs:
            if o.speaker:
                if last is not None and o.speaker != last:
                    out.append(o.t_ms)
                last = o.speaker
        return out
    last_cx: float | None = None
    for o in obs:
        if o.active_index is not None and o.active_index < len(o.faces):
            cx = o.faces[o.active_index].cx
            if last_cx is not None and not o.shot_cut and abs(cx - last_cx) > cfg.cut_threshold:
                out.append(o.t_ms)
            last_cx = cx
    return out


def plan(
    observations: list[Observation],
    duration_ms: int,
    cfg: ReframeConfig,
) -> list[LayoutSegment]:
    if not observations:
        return [LayoutSegment(0, duration_ms, Layout.FIT_BLUR)]
    obs = sorted(observations, key=lambda o: o.t_ms)

    # 1) Har kuzatuv uchun xom layout.
    switches = _switch_times(obs, cfg)
    raw: list[tuple[int, Layout]] = []
    for o in obs:
        recent = sum(1 for s in switches if 0 <= o.t_ms - s <= SPLIT_SWITCH_WINDOW_MS)
        raw.append((o.t_ms, decide_layout(o, recent)))
    held = _hold_layouts(raw, cfg.min_layout_hold_ms, duration_ms)

    # 2) Segmentlar.
    segments: list[LayoutSegment] = []
    for i, (t, lay) in enumerate(held):
        start = 0 if i == 0 else t
        end = held[i + 1][0] if i + 1 < len(held) else duration_ms
        if end > start:
            segments.append(LayoutSegment(start, end, lay))

    # 3) Har segment uchun kamera yo'li.
    for seg in segments:
        seg_obs = [o for o in obs if seg.start_ms <= o.t_ms < seg.end_ms]
        if seg.layout is Layout.FOCUS:
            seg.keys = _camera_path(seg_obs, seg.start_ms, cfg, pick="active")
        elif seg.layout is Layout.SPLIT:
            seg.keys = _camera_path(seg_obs, seg.start_ms, cfg, pick="left")
            seg.keys_b = _camera_path(seg_obs, seg.start_ms, cfg, pick="right")
    return segments


def _target(o: Observation, pick: str) -> float | None:
    if not o.faces:
        return None
    if pick == "left":
        return min(o.faces, key=lambda b: b.cx).cx
    if pick == "right":
        return max(o.faces, key=lambda b: b.cx).cx
    if o.active_index is not None and o.active_index < len(o.faces):
        return o.faces[o.active_index].cx
    return max(o.faces, key=lambda b: b.w * b.h).cx


def _camera_path(
    obs: list[Observation], seg_start_ms: int, cfg: ReframeConfig, pick: str
) -> list[CropKey]:
    """O'lik zona + One-Euro + tezlik chegarasi; spiker almashsa yoki sahna kesilsa - keskin kesim."""
    f = OneEuroFilter(cfg.one_euro_min_cutoff, cfg.one_euro_beta)
    keys: list[CropKey] = []
    cur: float | None = None
    last_t: float | None = None
    for o in obs:
        tgt = _target(o, pick)
        if tgt is None:
            continue
        t = o.t_ms / 1000
        rel = o.t_ms - seg_start_ms
        if cur is None or o.shot_cut or abs(tgt - cur) > cfg.cut_threshold:
            cur = tgt
            f.reset(tgt, t)
            keys.append(CropKey(rel, cur, cut=True))
            last_t = t
            continue
        if abs(tgt - cur) < cfg.dead_zone:
            tgt = cur
        smoothed = f(tgt, t)
        dt = t - (last_t if last_t is not None else t)
        cur = clamp_speed(cur, smoothed, dt, cfg.max_speed_per_s) if dt > 0 else smoothed
        last_t = t
        keys.append(CropKey(rel, cur))
    if not keys:
        keys.append(CropKey(0, 0.5, cut=True))
    return keys


def crop_rect(
    cx: float, src_w: int, src_h: int, out_aspect: float = 9 / 16, zoom: float = 1.0,
    cy: float = 0.5,
) -> tuple[int, int, int, int]:
    """Manba kadridagi crop (x, y, w, h) - juft sonlar, kadr ichida."""
    h = int(src_h / max(1.0, zoom))
    w = int(h * out_aspect)
    if w > src_w:
        w = src_w
        h = int(w / out_aspect)
    w -= w % 2
    h -= h % 2
    x = int(cx * src_w - w / 2)
    x = max(0, min(src_w - w, x))
    x -= x % 2
    y = int(cy * src_h - h / 2)
    y = max(0, min(src_h - h, y))
    y -= y % 2
    return x, y, w, h


# --- Kalit kadrlar jadvali (reframe_keyframes) bilan almashinuv -------------------------------


@dataclass
class Keyframe:
    """`reframe_keyframes` qatori: t_ms - chiqish vaqti, cx/cy normallashgan, lane 'a'|'b'."""

    t_ms: int
    layout: Layout
    cx: float | None = None
    cy: float | None = None
    zoom: float = 1.0
    lane: str = "a"


MANUAL_CUT_GAP_MS = 250
"""Shu oraliqdan yaqin va cut_threshold dan katta sakrash - keskin kesim (pan emas)."""


def _lane_keys(kfs: list[Keyframe], start: int, end: int, cut_threshold: float) -> list[CropKey]:
    inside = [k for k in kfs if start <= k.t_ms < end]
    before = [k for k in kfs if k.t_ms < start]
    if before and (not inside or inside[0].t_ms > start):
        inside.insert(0, Keyframe(start, before[-1].layout, before[-1].cx, before[-1].cy,
                                  before[-1].zoom, before[-1].lane))
    keys: list[CropKey] = []
    for k in inside:
        cx = 0.5 if k.cx is None else k.cx
        cy = 0.5 if k.cy is None else k.cy
        rel = k.t_ms - start
        cut = not keys or (rel - keys[-1].t_ms <= MANUAL_CUT_GAP_MS
                           and abs(cx - keys[-1].cx) > cut_threshold)
        keys.append(CropKey(rel, cx, cy, k.zoom, cut=cut))
    return keys


def layouts_from_keyframes(
    keyframes: list[Keyframe], duration_ms: int, cut_threshold: float = 0.25
) -> list[LayoutSegment]:
    """Kalit kadrlardan layout segmentlari. Layout yoki zoom o'zgargan joyda yangi segment
    boshlanadi (render bo'lagida crop o'lchami doimiy - ADR-0009). Birinchi segment 0 dan."""
    a = sorted((k for k in keyframes if k.lane == "a"), key=lambda k: k.t_ms)
    b = sorted((k for k in keyframes if k.lane == "b"), key=lambda k: k.t_ms)
    if not a:
        return [LayoutSegment(0, duration_ms, Layout.FIT_BLUR)]
    bounds: list[tuple[int, Layout, float]] = []
    for k in a:
        if k.t_ms >= duration_ms:
            break
        zoom = round(k.zoom, 3) if k.layout in (Layout.FOCUS, Layout.MANUAL) else 1.0
        if not bounds or bounds[-1][1] != k.layout or bounds[-1][2] != zoom:
            bounds.append((max(0, k.t_ms) if bounds else 0, k.layout, zoom))
    segs: list[LayoutSegment] = []
    for i, (start, lay, _zoom) in enumerate(bounds):
        end = bounds[i + 1][0] if i + 1 < len(bounds) else duration_ms
        if end <= start:
            continue
        seg = LayoutSegment(start, end, lay)
        if lay is not Layout.FIT_BLUR:
            seg.keys = _lane_keys(a, start, end, cut_threshold)
        if lay is Layout.SPLIT:
            seg.keys_b = _lane_keys(b, start, end, cut_threshold) if b else []
        segs.append(seg)
    return segs


def keyframes_from_layouts(segments: list[LayoutSegment]) -> list[Keyframe]:
    """Avtomatik reja -> jadval qatorlari (UI ko'rsatishi uchun). (lane, t_ms) takrorlanmaydi."""
    rows: dict[tuple[str, int], Keyframe] = {}
    for seg in segments:
        if seg.layout is Layout.FIT_BLUR or not seg.keys:
            rows[("a", seg.start_ms)] = Keyframe(seg.start_ms, seg.layout)
            continue
        for lane, keys in (("a", seg.keys), ("b", seg.keys_b)):
            if not keys:
                continue
            first = keys[0]
            rows[(lane, seg.start_ms)] = Keyframe(seg.start_ms, seg.layout, first.cx, first.cy,
                                                  first.zoom, lane)
            for k in keys:
                t = seg.start_ms + k.t_ms
                if seg.start_ms <= t < seg.end_ms:
                    rows[(lane, t)] = Keyframe(t, seg.layout, k.cx, k.cy, k.zoom, lane)
    return sorted(rows.values(), key=lambda k: (k.lane, k.t_ms))


def key_at(keys: list[CropKey], rel_ms: int) -> CropKey:
    """Segment ichidagi rel_ms paytdagi kamera holati (kesim bo'lmasa chiziqli interpolyatsiya)."""
    if not keys:
        return CropKey(0, 0.5, cut=True)
    prev = keys[0]
    for k in keys:
        if k.t_ms > rel_ms:
            if k.cut or k.t_ms == prev.t_ms or prev.t_ms > rel_ms:
                break
            r = (rel_ms - prev.t_ms) / (k.t_ms - prev.t_ms)
            return CropKey(0, prev.cx + (k.cx - prev.cx) * r, prev.cy + (k.cy - prev.cy) * r,
                           prev.zoom, cut=True)
        prev = k
    return CropKey(0, prev.cx, prev.cy, prev.zoom, cut=True)
