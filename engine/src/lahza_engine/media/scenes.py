"""Sahna (kamera) kesimlarini aniqlash - FFmpeg `scdet` filtri (TZ 8-bo'lim).

PySceneDetect o'rniga: qo'shimcha bog'liqliksiz, xuddi shu "kadrlar farqi" yondashuvi.
`scdet` bo'lmagan yig'malarda `select='gt(scene,T)'` + `showinfo` ishlatiladi.
Reframe kesimda kamera yo'lini qayta boshlaydi (planner: Observation.shot_cut).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from lahza_engine.media.tools import find_tool, run

DEFAULT_THRESHOLD = 10.0
"""scdet bo'yicha 0..100 shkalada (select uchun /100). R0: Reframe-Eval to'plamida tanlanadi."""
MIN_GAP_MS = 500
"""Bundan yaqin kesimlar bitta deb hisoblanadi (chaqnash, o'tish effekti)."""

_SCDET_RE = re.compile(r"lavfi\.scd\.time:\s*([0-9.]+)")
_SHOWINFO_RE = re.compile(r"pts_time:\s*([0-9.]+)")


def scene_cut_args(
    ffmpeg: str, src: str | os.PathLike[str], start_ms: int, end_ms: int, threshold: float,
    use_scdet: bool,
) -> list[str]:
    detector = (f"scdet=threshold={threshold:g}" if use_scdet
                else f"select='gt(scene,{threshold / 100:g})',showinfo")
    return [
        ffmpeg, "-hide_banner", "-nostats", "-v", "info",
        "-ss", f"{start_ms / 1000:.3f}", "-t", f"{(end_ms - start_ms) / 1000:.3f}",
        "-i", str(src), "-an", "-sn", "-vf", f"scale=320:-2,{detector}", "-f", "null", "-",
    ]


def parse_scene_times(stderr: str, use_scdet: bool) -> list[float]:
    rx = _SCDET_RE if use_scdet else _SHOWINFO_RE
    return [float(m.group(1)) for m in rx.finditer(stderr)]


def detect_scene_cuts(
    src: str | os.PathLike[str] | Path,
    start_ms: int,
    end_ms: int,
    threshold: float = DEFAULT_THRESHOLD,
    timeout_s: float | None = 600,
) -> list[int]:
    """[start_ms, end_ms] oralig'idagi sahna kesimlari, MANBA vaqtida (ms), o'sish tartibida."""
    from lahza_engine.render.capabilities import has_filter

    if end_ms <= start_ms:
        return []
    ffmpeg = str(find_tool("ffmpeg"))
    use_scdet = has_filter(ffmpeg, "scdet")
    r = run(scene_cut_args(ffmpeg, src, start_ms, end_ms, threshold, use_scdet), timeout=timeout_s)
    if r.returncode != 0:
        return []
    out: list[int] = []
    for t in sorted(parse_scene_times(r.stderr, use_scdet)):
        ms = start_ms + int(round(t * 1000))
        if ms <= start_ms or ms >= end_ms:
            continue
        if out and ms - out[-1] < MIN_GAP_MS:
            continue
        out.append(ms)
    return out
