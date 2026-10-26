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
    r = run([ffmpeg, "-y", "-v", "error", "-copyts", "-i", src, "-vn",
             "-af", f"aresample={rate}:async=1:first_pts=0", "-ac", "1", "-ar", str(rate),
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
    """16-bit PCM WAV -> float32 [-1, 1] (butun fayl xotiraga).

    Kichik fayllar uchun. Uzun audio uchun `open_wav_mono` (oqimli, oraliq o'qish) ishlating.
    """
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


# Oqimli o'qishda bitta blok hajmi (namuna): 16 kHz da ~65 s, float32 da 4 MB.
WAV_BLOCK_SAMPLES = 1 << 20


def _wav_layout(path: str) -> tuple[int, int, int, int]:
    """RIFF/WAVE sarlavhasi: (data_offset, n_frames, channels, rate). Faqat 16-bit PCM."""
    import struct

    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(12)
        if len(head) < 12 or head[:4] not in (b"RIFF", b"RF64") or head[8:12] != b"WAVE":
            raise MediaError("WAV fayli emas")
        rf64 = head[:4] == b"RF64"
        ds64_data: int | None = None
        fmt: tuple[int, int, int, int] | None = None
        pos = 12
        while pos + 8 <= size:
            f.seek(pos)
            cid, clen = struct.unpack("<4sI", f.read(8))
            body = pos + 8
            if cid == b"ds64":
                ds64_data = struct.unpack("<QQ", f.read(16))[1]
            elif cid == b"fmt ":
                tag, ch, rate, _br, _ba, bits = struct.unpack("<HHIIHH", f.read(16))
                fmt = (tag, ch, rate, bits)
            elif cid == b"data":
                if fmt is None:
                    raise MediaError("WAV: fmt bo'limi yo'q")
                tag, ch, rate, bits = fmt
                if bits != 16 or tag not in (1, 0xFFFE) or ch < 1:
                    raise MediaError("faqat 16-bit PCM WAV qo'llanadi")
                avail = size - body
                n_bytes = ds64_data if rf64 and clen == 0xFFFFFFFF and ds64_data else clen
                n_bytes = min(n_bytes, avail)  # oqimda yozilgan (o'lchami 0/-1) fayllar
                if clen in (0, 0xFFFFFFFF) and not (rf64 and ds64_data):
                    n_bytes = avail
                return body, n_bytes // (2 * ch), ch, rate
            pos = body + clen + (clen & 1)
    raise MediaError("WAV: data bo'limi topilmadi")


class WavPcm:
    """16-bit PCM WAV ustidan dangasa mono float32 ko'rinish (V1-1: 4 soatlik audio uchun).

    Butun faylni xotiraga o'qimaydi: `pcm[a:b]` faqat shu oraliqni diskdan o'qib, `read_wav_mono`
    bilan bit-darajada bir xil float32 qiymat qaytaradi. `len()`, `rate`, `blocks()` va
    `np.asarray(pcm)` (butunini o'qish - faqat kichik fayllar uchun) qo'llanadi.
    memmap emas, oddiy oraliq o'qish: xaritalangan sahifalar RSS ga qo'shilmasin.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = str(path)
        self._offset, self._n, self.channels, self.rate = _wav_layout(self.path)
        self.dtype = np.dtype(np.float32)

    def __len__(self) -> int:
        return self._n

    @property
    def shape(self) -> tuple[int]:
        return (self._n,)

    def read(self, start: int, stop: int) -> np.ndarray:
        """[start, stop) namunalar (mono float32, [-1, 1])."""
        start = max(0, min(int(start), self._n))
        stop = max(start, min(int(stop), self._n))
        count = (stop - start) * self.channels
        if count == 0:
            return np.zeros(0, dtype=np.float32)
        with open(self.path, "rb") as f:
            f.seek(self._offset + start * 2 * self.channels)
            raw = np.fromfile(f, dtype="<i2", count=count)
        pcm = raw.astype(np.float32) / 32768.0
        if self.channels > 1:
            pcm = pcm[: len(pcm) - len(pcm) % self.channels].reshape(-1, self.channels).mean(axis=1)
        return pcm

    def __getitem__(self, key: object) -> np.ndarray:
        if isinstance(key, slice):
            start, stop, step = key.indices(self._n)
            if step == 1:
                return self.read(start, stop)
            return np.asarray(self)[key]
        if isinstance(key, (int, np.integer)):
            i = int(key) + (self._n if key < 0 else 0)
            if not 0 <= i < self._n:
                raise IndexError(key)
            return self.read(i, i + 1)[0]
        raise TypeError(f"WavPcm indeksi qo'llanmaydi: {type(key).__name__}")

    def __array__(self, dtype: object = None, copy: object = None) -> np.ndarray:
        arr = self.read(0, self._n)
        return arr if dtype is None else arr.astype(dtype)

    def blocks(self, block: int = WAV_BLOCK_SAMPLES, align: int = 1):
        """(start, float32 blok) juftlari; blok uzunligi `align` ga karrali (oxirgisidan tashqari)."""
        block = max(align, block - block % align)
        for a in range(0, self._n, block):
            yield a, self.read(a, a + block)


def open_wav_mono(path: str | os.PathLike[str]) -> tuple[WavPcm, int]:
    """`read_wav_mono` ning oqimli o'rinbosari: (dangasa pcm, rate)."""
    pcm = WavPcm(path)
    return pcm, pcm.rate


def frame_power(pcm: object, hop: int, dtype: object = None,
                block: int = WAV_BLOCK_SAMPLES) -> np.ndarray:
    """Har `hop` namunali kadr uchun o'rtacha kvadrat, oqimli; to'liq bo'lmagan oxiri tashlanadi.

    ndarray ham, WavPcm ham qabul qilinadi. Natija `mean(frames**2, axis=1)` bilan bit-darajada
    bir xil: har kadr alohida qisqartiriladi, bloklash qiymatga ta'sir qilmaydi. `dtype=None` -
    kirish turi saqlanadi (WavPcm uchun float32).
    """
    hop = max(1, int(hop))
    n = len(pcm) // hop  # type: ignore[arg-type]
    dt = np.dtype(dtype) if dtype is not None else np.dtype(getattr(pcm, "dtype", np.float32))
    if n == 0:
        return np.zeros(0, dtype=np.result_type(dt, np.float32) if dt.kind != "f" else dt)
    per = max(1, block // hop)
    parts = []
    for i in range(0, n, per):
        j = min(n, i + per)
        x = np.asarray(pcm[i * hop: j * hop], dtype=dt).reshape(j - i, hop)  # type: ignore[index]
        parts.append(np.mean(x**2, axis=1))
    return parts[0] if len(parts) == 1 else np.concatenate(parts)
