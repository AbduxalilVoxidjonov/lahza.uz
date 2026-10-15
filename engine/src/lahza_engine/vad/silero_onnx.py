"""Silero VAD v5 - to'g'ridan-to'g'ri onnxruntime orqali (torch'siz, M1-PIPE-4).

Model interfeysi (silero-vad v5 ONNX):
* kirish: `input` [1, context + window] float32, `state` [2, 1, 128] float32, `sr` int64 skalyar;
* chiqish: ehtimollik [1, 1] va yangi `state`.
16 kHz da oyna 512 namuna (32 ms), kontekst - oldingi oynaning oxirgi 64 namunasi.
Ehtimolliklar `probs_to_segments` da gisterezis bilan nutq oraliqlariga aylanadi (silero
`get_speech_timestamps` mantig'i bilan bir xil).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

_WINDOW = {16000: 512, 8000: 256}
_CONTEXT = {16000: 64, 8000: 32}


def probs_to_segments(
    probs: np.ndarray | list[float],
    window: int,
    n_samples: int,
    sample_rate: int,
    threshold: float = 0.5,
    neg_threshold: float = 0.35,
    min_speech_ms: int = 250,
    min_silence_ms: int = 100,
    pad_ms: int = 30,
) -> list[tuple[int, int]]:
    """Oyna ehtimolliklari -> nutq oraliqlari (ms). Kirish va chiqish namunalar bo'yicha hisoblanadi."""
    min_speech = sample_rate * min_speech_ms / 1000
    min_silence = sample_rate * min_silence_ms / 1000
    pad = int(sample_rate * pad_ms / 1000)

    speeches: list[list[int]] = []
    triggered = False
    start = 0
    temp_end = 0
    for i, p in enumerate(probs):
        pos = window * i
        if p >= threshold and temp_end:
            temp_end = 0
        if p >= threshold and not triggered:
            triggered = True
            start = pos
            continue
        if p < neg_threshold and triggered:
            if not temp_end:
                temp_end = pos
            if pos - temp_end < min_silence:
                continue
            if temp_end - start > min_speech:
                speeches.append([start, temp_end])
            triggered, temp_end = False, 0
    if triggered and n_samples - start > min_speech:
        speeches.append([start, n_samples])

    # Atrofga pad: qo'shni oraliqlar orasidagi sukut 2*pad dan kichik bo'lsa - o'rtadan bo'linadi.
    for i, sp in enumerate(speeches):
        if i == 0:
            sp[0] = max(0, sp[0] - pad)
        if i != len(speeches) - 1:
            nxt = speeches[i + 1]
            silence = nxt[0] - sp[1]
            if silence < 2 * pad:
                sp[1] += silence // 2
                nxt[0] = max(0, nxt[0] - silence // 2)
            else:
                sp[1] = min(n_samples, sp[1] + pad)
                nxt[0] = max(0, nxt[0] - pad)
        else:
            sp[1] = min(n_samples, sp[1] + pad)
    return [(int(a * 1000 / sample_rate), int(b * 1000 / sample_rate)) for a, b in speeches]


def _resample_linear(pcm: np.ndarray, sr: int, target: int) -> np.ndarray:
    if sr == target or len(pcm) == 0:
        return pcm
    n = int(round(len(pcm) * target / sr))
    x_old = np.arange(len(pcm), dtype=np.float64) / sr
    x_new = np.arange(n, dtype=np.float64) / target
    return np.interp(x_new, x_old, pcm).astype(np.float32)


class SileroOnnxVad:
    """Silero VAD v5 ONNX. `session` - testlar uchun (onnxruntime.InferenceSession o'rniga)."""

    method = "silero"

    def __init__(
        self,
        model_path: Path | None = None,
        session: Any | None = None,
        threshold: float = 0.5,
        neg_threshold: float = 0.35,
        min_speech_ms: int = 250,
        min_silence_ms: int = 100,
        pad_ms: int = 30,
    ) -> None:
        if session is None:
            if model_path is None:
                raise ValueError("model_path yoki session kerak")
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 1
            opts.inter_op_num_threads = 1
            session = ort.InferenceSession(str(model_path), sess_options=opts,
                                           providers=["CPUExecutionProvider"])
        names = {i.name for i in session.get_inputs()}
        if not {"input", "state", "sr"} <= names:
            raise ValueError(f"Silero v5 ONNX interfeysi kutilgan edi, kirishlar: {sorted(names)}")
        self.session = session
        self.threshold = threshold
        self.neg_threshold = neg_threshold
        self.min_speech_ms = min_speech_ms
        self.min_silence_ms = min_silence_ms
        self.pad_ms = pad_ms

    def probabilities(self, pcm: np.ndarray, sample_rate: int) -> np.ndarray:
        window, ctx_n = _WINDOW[sample_rate], _CONTEXT[sample_rate]
        state = np.zeros((2, 1, 128), dtype=np.float32)
        context = np.zeros((1, ctx_n), dtype=np.float32)
        sr = np.array(sample_rate, dtype=np.int64)
        n = (len(pcm) + window - 1) // window
        out = np.zeros(n, dtype=np.float32)
        for i in range(n):
            chunk = pcm[i * window : (i + 1) * window]
            if len(chunk) < window:
                chunk = np.pad(chunk, (0, window - len(chunk)))
            x = np.concatenate([context, chunk[None, :].astype(np.float32)], axis=1)
            prob, state = self.session.run(None, {"input": x, "state": state, "sr": sr})
            out[i] = float(np.asarray(prob).reshape(-1)[0])
            context = x[:, -ctx_n:]
        return out

    def __call__(self, pcm: np.ndarray, sample_rate: int) -> list[tuple[int, int]]:
        pcm = np.asarray(pcm, dtype=np.float32)
        if sample_rate not in _WINDOW:
            pcm = _resample_linear(pcm, sample_rate, 16000)
            sample_rate = 16000
        if len(pcm) == 0:
            return []
        probs = self.probabilities(pcm, sample_rate)
        return probs_to_segments(
            probs, _WINDOW[sample_rate], len(pcm), sample_rate, self.threshold, self.neg_threshold,
            self.min_speech_ms, self.min_silence_ms, self.pad_ms,
        )
