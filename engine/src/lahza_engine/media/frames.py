"""Vizual tahlil uchun kadrlar oqimi: ffmpeg -> xom RGB (kichraytirilgan, past fps)."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import numpy as np

from lahza_engine.media.tools import find_tool


def iter_frames(
    src: Path, start_ms: int, end_ms: int, fps: float = 5.0, width: int = 640, src_w: int = 1920,
    src_h: int = 1080,
) -> Iterator[tuple[int, np.ndarray]]:
    """(t_ms manba vaqtida, RGB kadr [H, W, 3]) juftliklari."""
    height = int(round(width * src_h / src_w / 2) * 2)
    ffmpeg = str(find_tool("ffmpeg"))
    cmd = [
        ffmpeg, "-v", "error", "-ss", f"{start_ms / 1000:.3f}", "-t", f"{(end_ms - start_ms) / 1000:.3f}",
        "-i", str(src), "-vf", f"fps={fps},scale={width}:{height}", "-f", "rawvideo",
        "-pix_fmt", "rgb24", "-",
    ]
    frame_bytes = width * height * 3
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:
        assert proc.stdout is not None
        i = 0
        while True:
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            t = start_ms + int(i * 1000 / fps)
            yield t, np.frombuffer(buf, dtype=np.uint8).reshape(height, width, 3)
            i += 1
