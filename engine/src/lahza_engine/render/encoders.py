"""Video enkoder tanlovi (TZ 10-bo'lim, ADR-0004).

Ishlab chiqarish yig'masida FFmpeg LGPL (libx264/libx265 yo'q). Ustuvorlik:
    macOS            -> h264_videotoolbox
    Windows+NVIDIA   -> h264_nvenc  -> h264_mf
    Windows+AMD      -> h264_amf    -> h264_mf
    Windows+Intel    -> h264_qsv    -> h264_mf
    Windows, GPU yo'q -> h264_mf
`-encoders` ro'yxatida bo'lish apparat borligini kafolatlamaydi, shuning uchun 1 kadrlik sinov
kodlash bilan tekshiriladi (verify_encoder).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from lahza_engine.media.tools import run

PRIORITY: dict[tuple[str, str | None], list[str]] = {
    ("darwin", None): ["h264_videotoolbox"],
    ("win32", "nvidia"): ["h264_nvenc", "h264_mf"],
    ("win32", "amd"): ["h264_amf", "h264_mf"],
    ("win32", "intel"): ["h264_qsv", "h264_mf"],
    ("win32", None): ["h264_mf"],
}
# Faqat dasturchi muhiti/CI uchun (ishlab chiqarish yig'masida bo'lmaydi).
DEV_FALLBACKS = ["libx264", "mpeg4"]


@dataclass(frozen=True)
class EncoderChoice:
    name: str
    args: tuple[str, ...]
    hardware: bool


def encoder_args(name: str, bitrate_kbps: int) -> tuple[str, ...]:
    b = f"{bitrate_kbps}k"
    common = ("-b:v", b, "-maxrate", f"{int(bitrate_kbps * 1.5)}k", "-bufsize", f"{bitrate_kbps * 2}k")
    if name == "h264_videotoolbox":
        return ("-c:v", name, "-profile:v", "high", *common, "-pix_fmt", "yuv420p")
    if name == "h264_nvenc":
        return ("-c:v", name, "-preset", "p5", "-profile:v", "high", *common, "-pix_fmt", "yuv420p")
    if name in ("h264_amf", "h264_qsv", "h264_mf"):
        return ("-c:v", name, *common, "-pix_fmt", "nv12" if name == "h264_qsv" else "yuv420p")
    if name == "libx264":
        return ("-c:v", name, "-preset", "medium", "-profile:v", "high", *common, "-pix_fmt", "yuv420p")
    if name == "mpeg4":
        return ("-c:v", name, "-q:v", "3", "-pix_fmt", "yuv420p")
    raise ValueError(f"noma'lum enkoder: {name}")


@lru_cache(maxsize=8)
def list_encoders(ffmpeg: str) -> frozenset[str]:
    r = run([ffmpeg, "-hide_banner", "-encoders"])
    names = set()
    for line in r.stdout.splitlines():
        m = re.match(r"^\s*[VAS][\.FSXBD]{5}\s+(\S+)", line)
        if m:
            names.add(m.group(1))
    return frozenset(names)


@lru_cache(maxsize=32)
def verify_encoder(ffmpeg: str, name: str) -> bool:
    r = run(
        [ffmpeg, "-hide_banner", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2",
         *encoder_args(name, 2000), "-frames:v", "3", "-f", "null", "-"],
        timeout=60,
    )
    return r.returncode == 0


def choose_encoder(
    ffmpeg: str | Path,
    gpu_vendor: str | None,
    bitrate_kbps: int,
    platform: str = sys.platform,
    allow_dev_fallback: bool = False,
) -> EncoderChoice:
    ff = str(ffmpeg)
    available = list_encoders(ff)
    order = list(PRIORITY.get((platform, gpu_vendor if platform == "win32" else None), []))
    if platform == "win32" and "h264_mf" not in order:
        order.append("h264_mf")
    for name in order:
        if name in available and verify_encoder(ff, name):
            return EncoderChoice(name, encoder_args(name, bitrate_kbps), True)
    if allow_dev_fallback:
        for name in DEV_FALLBACKS:
            if name in available and verify_encoder(ff, name):
                return EncoderChoice(name, encoder_args(name, bitrate_kbps), False)
    raise RuntimeError(
        "Mos H.264 enkoder topilmadi. TZ 10-bo'lim: dasturiy H.264 zaxirasi ANIQLANSIN."
    )
