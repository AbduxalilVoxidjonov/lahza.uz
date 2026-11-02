"""Audio'ni o'zimizning LGPL FFmpeg orqali float32 PCM massivga dekod qilish (ADR-0015).

faster-whisper fayl yo'li berilganda audio'ni PyAV (`av`) bilan o'qiydi. PyPI'dagi PyAV
g'ildiraklari GPL libx264/libx265 bilan statik yig'ilgan FFmpeg'ni o'z ichiga oladi, shuning
uchun ASR'ga har doim tayyor numpy massiv beriladi: dekodni `find_tool("ffmpeg")` topgan
alohida LGPL FFmpeg jarayoni bajaradi (ADR-0004), Python jarayoniga FFmpeg kutubxonasi yuklanmaydi.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from lahza_engine.media.tools import find_tool

WHISPER_SAMPLE_RATE = 16_000


class AudioDecodeError(RuntimeError):
    pass


def decode_pcm_f32(
    src: str | os.PathLike[str],
    sample_rate: int = WHISPER_SAMPLE_RATE,
    *,
    ffmpeg: str | os.PathLike[str] | None = None,
    timeout: float | None = 300,
) -> np.ndarray:
    """Birinchi audio oqimni mono, `sample_rate` Hz, float32 [-1, 1] massivga dekod qiladi.

    Shell'siz, argumentlar massivi bilan (NFR-08). Xato bo'lsa `AudioDecodeError`.
    """
    exe = Path(ffmpeg) if ffmpeg is not None else find_tool("ffmpeg")
    args = [
        str(exe), "-nostdin", "-hide_banner", "-v", "error",
        "-i", str(src),
        "-map", "0:a:0", "-vn", "-sn", "-dn",
        "-ac", "1", "-ar", str(int(sample_rate)),
        "-acodec", "pcm_f32le", "-f", "f32le", "pipe:1",
    ]
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    try:
        proc = subprocess.run(args, capture_output=True, timeout=timeout, check=False, **kwargs)
    except subprocess.TimeoutExpired as exc:
        raise AudioDecodeError(f"audio dekodi vaqt chegarasidan oshdi: {src}") from exc
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()[-2000:]
        raise AudioDecodeError(f"ffmpeg audio'ni dekod qila olmadi ({proc.returncode}): {err}")
    raw = proc.stdout
    usable = len(raw) - len(raw) % 4
    return np.frombuffer(raw[:usable], dtype="<f4").astype(np.float32, copy=True)
