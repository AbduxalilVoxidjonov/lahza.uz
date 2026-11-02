"""VAD interfeysi va energiyaga asoslangan zaxira.

Asosiy VAD - Silero (MIT, `vad` extra). Energiya VAD faqat zaxira va testlar uchun:
u shovqinli audioda nutqni musiqadan ajrata olmaydi.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from lahza_engine.media.probe import frame_power


class Vad(Protocol):
    def __call__(self, pcm: np.ndarray, sample_rate: int) -> list[tuple[int, int]]:
        """Nutq oraliqlari ms da."""
        ...


def vad_input(vad: object, pcm: object) -> object:
    """VAD'ga beriladigan audio: oqimli VAD (`streaming = True`) WavPcm'ni o'zi o'qiydi,
    qolganlariga (torch/test VAD'lari) butun ndarray beriladi."""
    if isinstance(pcm, np.ndarray) or getattr(vad, "streaming", False):
        return pcm
    return np.asarray(pcm)


def energy_vad(
    pcm: np.ndarray,  # yoki media.probe.WavPcm (oqimli, butun massiv o'qilmaydi)
    sample_rate: int,
    frame_ms: int = 30,
    min_speech_ms: int = 250,
    min_silence_ms: int = 300,
    margin_db: float = 12.0,
) -> list[tuple[int, int]]:
    hop = int(sample_rate * frame_ms / 1000)
    n = len(pcm) // hop
    if n == 0:
        return []
    db = 20 * np.log10(np.sqrt(frame_power(pcm, hop)) + 1e-9)
    noise = np.percentile(db, 10)
    voiced = db > noise + margin_db
    regions: list[tuple[int, int]] = []
    start: int | None = None
    silence = 0
    for i, v in enumerate(voiced):
        if v:
            if start is None:
                start = i
            silence = 0
        elif start is not None:
            silence += 1
            if silence * frame_ms >= min_silence_ms:
                end = i - silence + 1
                if (end - start) * frame_ms >= min_speech_ms:
                    regions.append((start * frame_ms, end * frame_ms))
                start, silence = None, 0
    if start is not None and (n - start) * frame_ms >= min_speech_ms:
        regions.append((start * frame_ms, n * frame_ms))
    return regions


class SileroVad:
    """`silero-vad` paketi orqali (ixtiyoriy)."""

    def __init__(self) -> None:
        from silero_vad import get_speech_timestamps, load_silero_vad

        self._model = load_silero_vad(onnx=True)
        self._get = get_speech_timestamps

    def __call__(self, pcm: np.ndarray, sample_rate: int) -> list[tuple[int, int]]:
        import torch

        arr = pcm if isinstance(pcm, np.ndarray) else np.asarray(pcm)
        ts = self._get(torch.from_numpy(arr), self._model, sampling_rate=sample_rate,
                       return_seconds=False)
        return [(int(t["start"] * 1000 / sample_rate), int(t["end"] * 1000 / sample_rate)) for t in ts]
