"""ASR'ga beriladigan PCM uchun yengil ovoz normalizatsiyasi (16 kHz mono bo'laklar).

Whisper log-mel spektri mutlaq sathga bog'liq: juda past yozuvlar (-35..-45 dBFS) va qattiq
yozuvlar bir xil modelga turlicha ko'rinadi. Bitta chiziqli kuchaytirish qo'llanadi:

* faqat kuchaytiriladi: nutqli kadrlar (20 ms, RMS >= SILENCE_FLOOR_DBFS) RMS'i TARGET_RMS_DBFS
  dan past bo'lsa shu sathga ko'tariladi - jim kadrlar o'rtachani pasaytirmaydi. Normal sathli
  yozuv o'zgarmaydi: 150 s real nutqda (-25 dBFS) -20 dBFS ga majburiy keltirish so'z sonini
  394 -> 366 ga tushirdi, -26 dBFS chegarasi esa bunday yozuvga deyarli tegmaydi;
* cho'qqi PEAK_CEILING_DBFS dan oshmaydi (klipping yo'q);
* kuchaytirish MAX_GAIN_DB bilan cheklangan; nutqli kadr bo'lmasa (sukunat/fon) o'zgarmaydi -
  shovqin kuchaytirib yuborilmaydi.
"""

from __future__ import annotations

import os
import wave

import numpy as np

TARGET_RMS_DBFS = -26.0
PEAK_CEILING_DBFS = -1.0
MAX_GAIN_DB = 20.0
SILENCE_FLOOR_DBFS = -50.0
FRAME_MS = 20


def _db(x: float) -> float:
    return 20.0 * float(np.log10(max(x, 1e-12)))


def normalization_gain(pcm: np.ndarray, sample_rate: int = 16_000) -> float:
    """Chiziqli kuchaytirish koeffitsienti (1.0 = o'zgarishsiz)."""
    x = np.asarray(pcm, dtype=np.float32)
    if x.size == 0:
        return 1.0
    frame = max(1, sample_rate * FRAME_MS // 1000)
    n = x.size // frame
    frames = x[None, :] if n == 0 else x[: n * frame].reshape(n, frame)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
    active = rms[rms >= 10 ** (SILENCE_FLOOR_DBFS / 20)]
    if active.size == 0:
        return 1.0
    speech_rms = float(np.sqrt(np.mean(active**2)))
    gain_db = min(TARGET_RMS_DBFS - _db(speech_rms), MAX_GAIN_DB)
    if gain_db <= 0:
        return 1.0  # yetarlicha baland - pasaytirilmaydi
    peak = float(np.max(np.abs(x)))
    if peak > 0:
        gain_db = min(gain_db, PEAK_CEILING_DBFS - _db(peak))
    return float(10 ** (gain_db / 20))


def normalize_pcm(pcm: np.ndarray, sample_rate: int = 16_000) -> np.ndarray:
    """float32 [-1, 1] PCM -> normalizatsiyalangan nusxa."""
    x = np.asarray(pcm, dtype=np.float32)
    gain = normalization_gain(x, sample_rate)
    if gain == 1.0:
        return x.copy()
    return np.clip(x * np.float32(gain), -1.0, 1.0).astype(np.float32)


def normalize_wav_file(path: str | os.PathLike[str]) -> float:
    """16-bit PCM WAV bo'lakni joyida normalizatsiya qiladi (mono). Qo'llangan gain qaytariladi."""
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("faqat 16-bit PCM WAV qo'llanadi")
        rate, ch = w.getframerate(), w.getnchannels()
        raw = w.readframes(w.getnframes())
    pcm = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        pcm = pcm.reshape(-1, ch).mean(axis=1)
    gain = normalization_gain(pcm, rate)
    if gain == 1.0 and ch == 1:
        return gain
    out = np.clip(np.round(pcm * gain * 32768.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(out.tobytes())
    return gain
