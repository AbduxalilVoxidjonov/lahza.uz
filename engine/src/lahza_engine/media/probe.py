"""Ingest bosqichi: metadata, tez xesh, ASR uchun WAV, UI uchun proksi (TZ 4-bo'lim, 1-bosqich)."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from lahza_engine.media.tools import find_tool, run

_EDGE = 64 * 1024 * 1024  # TZ: birinchi/oxirgi 64 MB + hajm


class MediaError(RuntimeError):
    pass


@dataclass
class MediaInfo:
    path: str
    duration_ms: int
    width: int
    height: int
    fps: float
    audio_channels: int
    video_codec: str | None
    audio_codec: str | None
    rotation: int = 0

    @property
    def has_audio(self) -> bool:
        return self.audio_channels > 0


def fast_hash(path: str | os.PathLike[str]) -> str:
    """Katta fayllar uchun tez xesh. xxhash o'rnatilgan bo'lsa - xxh3_128, aks holda blake2b."""
    p = Path(path)
    size = p.stat().st_size
    try:
        import xxhash

        h = xxhash.xxh3_128()
        prefix = "xxh3"
    except ImportError:
        h = hashlib.blake2b(digest_size=16)
        prefix = "b2b"
    h.update(str(size).encode())
    with p.open("rb") as f:
        h.update(f.read(_EDGE))
        if size > 2 * _EDGE:
            f.seek(size - _EDGE)
            h.update(f.read(_EDGE))
        elif size > _EDGE:
            h.update(f.read())
    return f"{prefix}:{h.hexdigest()}"


def _fps(rate: str | None) -> float:
    if not rate or rate in ("0/0",):
        return 0.0
    if "/" in rate:
        a, b = rate.split("/", 1)
        return float(a) / float(b) if float(b) else 0.0
    return float(rate)


def probe(path: str | os.PathLike[str]) -> MediaInfo:
    ffprobe = find_tool("ffprobe")
    r = run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path])
    if r.returncode != 0:
        raise MediaError(f"ffprobe xatosi: {r.stderr.strip()[:500]}")
    data = json.loads(r.stdout)
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if v is None:
        raise MediaError("Videoda tasvir yo'lagi topilmadi")
    if a is None:
        raise MediaError("Videoda ovoz yo'lagi topilmadi - boshqa fayl tanlang")
    dur = float(data.get("format", {}).get("duration") or v.get("duration") or 0.0)
    rotation = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rotation = int(sd["rotation"])
    return MediaInfo(
        path=str(path),
        duration_ms=int(round(dur * 1000)),
        width=int(v.get("width", 0)),
        height=int(v.get("height", 0)),
        fps=_fps(v.get("avg_frame_rate") or v.get("r_frame_rate")),
        audio_channels=int(a.get("channels", 0)),
        video_codec=v.get("codec_name"),
        audio_codec=a.get("codec_name"),
        rotation=rotation,
    )


def extract_wav(src: str | os.PathLike[str], dst: str | os.PathLike[str], rate: int = 16_000) -> Path:
    """ASR uchun 16 kHz mono PCM WAV."""
    ffmpeg = find_tool("ffmpeg")
    r = run([ffmpeg, "-y", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", str(rate),
             "-c:a", "pcm_s16le", dst])
    if r.returncode != 0:
        raise MediaError(f"audio ajratib bo'lmadi: {r.stderr.strip()[:500]}")
    return Path(dst)


def make_proxy(src: str | os.PathLike[str], dst: str | os.PathLike[str], height: int = 540,
               encoder_args: list[str] | None = None) -> Path:
    """UI preview uchun yengil proksi (540p)."""
    ffmpeg = find_tool("ffmpeg")
    enc = encoder_args or ["-c:v", "mpeg4", "-q:v", "6"]
    r = run([ffmpeg, "-y", "-v", "error", "-i", src, "-vf", f"scale=-2:{height}", *enc,
             "-c:a", "aac", "-b:a", "96k", dst])
    if r.returncode != 0:
        raise MediaError(f"proksi yaratib bo'lmadi: {r.stderr.strip()[:500]}")
    return Path(dst)


def read_wav_mono(path: str | os.PathLike[str]) -> tuple[np.ndarray, int]:
    """16-bit PCM WAV -> float32 [-1, 1]."""
    import wave

    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise MediaError("faqat 16-bit PCM WAV qo'llanadi")
        rate = w.getframerate()
        ch = w.getnchannels()
        raw = w.readframes(w.getnframes())
    pcm = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        pcm = pcm.reshape(-1, ch).mean(axis=1)
    return pcm, rate
