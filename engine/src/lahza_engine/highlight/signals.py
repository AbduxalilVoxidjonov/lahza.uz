"""Audio va transkriptdan signal xususiyatlari (TZ 4-bo'lim, 8-bosqich).

Kulgi/olqish detektori model talab qiladi: interfeys bor, standart realizatsiya - NullDetector
(R0'da model tanlanadi). Natija ballar o'ylab topilmaydi: detektor yo'q bo'lsa ball 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from lahza_engine.highlight.rules import is_question
from lahza_engine.types import Sentence

FRAME_MS = 100


class EventDetector(Protocol):
    def __call__(self, pcm: np.ndarray, sample_rate: int) -> list[tuple[int, int]]:
        """Hodisa (kulgi/olqish) oraliqlari ms da."""
        ...


class NullDetector:
    def __call__(self, pcm: np.ndarray, sample_rate: int) -> list[tuple[int, int]]:
        return []


def loudness_db(pcm: np.ndarray, sample_rate: int, frame_ms: int = FRAME_MS) -> np.ndarray:
    """Har frame uchun RMS (dBFS)."""
    hop = max(1, int(sample_rate * frame_ms / 1000))
    n = len(pcm) // hop
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    frames = pcm[: n * hop].astype(np.float32).reshape(n, hop)
    rms = np.sqrt(np.mean(frames**2, axis=1) + 1e-12)
    return (20.0 * np.log10(rms + 1e-12)).astype(np.float32)


@dataclass
class SentenceSignals:
    sentence_id: int
    loudness_z: float = 0.0
    peak_z: float = 0.0
    words_per_s: float = 0.0
    rate_change: float = 0.0
    pause_before_ms: int = 0
    pause_after_ms: int = 0
    speaker_switch: bool = False
    question: bool = False
    events: int = 0

    def score(self) -> float:
        """0..100 signal bali. Vaznlar boshlang'ich (R0'da o'rganiladi)."""
        s = 0.0
        s += 18.0 * float(np.clip(self.loudness_z, -2, 3))
        s += 12.0 * float(np.clip(self.peak_z, -2, 3))
        s += 10.0 * float(np.clip(abs(self.rate_change), 0, 2))
        s += 8.0 if self.speaker_switch else 0.0
        s += 10.0 if self.question else 0.0
        s += 15.0 * min(self.events, 2)
        return float(np.clip(50.0 + s, 0.0, 100.0))


@dataclass
class SignalReport:
    sentences: list[SentenceSignals] = field(default_factory=list)

    def by_id(self) -> dict[int, SentenceSignals]:
        return {s.sentence_id: s for s in self.sentences}


def compute_signals(
    sentences: list[Sentence],
    pcm: np.ndarray | None,
    sample_rate: int = 16_000,
    event_detector: EventDetector | None = None,
) -> SignalReport:
    detector = event_detector or NullDetector()
    db = loudness_db(pcm, sample_rate) if pcm is not None and len(pcm) else np.zeros(0)
    events = detector(pcm, sample_rate) if pcm is not None else []

    per_sentence_mean: list[float] = []
    per_sentence_peak: list[float] = []
    rates: list[float] = []
    for s in sentences:
        a, b = s.start_ms // FRAME_MS, max(s.start_ms // FRAME_MS + 1, s.end_ms // FRAME_MS)
        seg = db[a:b] if len(db) else np.zeros(0)
        per_sentence_mean.append(float(seg.mean()) if len(seg) else 0.0)
        per_sentence_peak.append(float(seg.max()) if len(seg) else 0.0)
        dur_s = max(0.001, s.duration_ms / 1000)
        rates.append(len(s.words) / dur_s)

    def z(values: list[float]) -> list[float]:
        arr = np.asarray(values, dtype=np.float64)
        if len(arr) < 2 or arr.std() < 1e-9:
            return [0.0] * len(values)
        return list((arr - arr.mean()) / arr.std())

    mean_z, peak_z = z(per_sentence_mean), z(per_sentence_peak)
    median_rate = float(np.median(rates)) if rates else 0.0

    report = SignalReport()
    for i, s in enumerate(sentences):
        prev_end = sentences[i - 1].end_ms if i > 0 else s.start_ms
        next_start = sentences[i + 1].start_ms if i + 1 < len(sentences) else s.end_ms
        ev = sum(1 for (a, b) in events if a < s.end_ms + 1500 and b > s.start_ms)
        report.sentences.append(
            SentenceSignals(
                sentence_id=s.id,
                loudness_z=mean_z[i],
                peak_z=peak_z[i],
                words_per_s=rates[i],
                rate_change=(rates[i] - median_rate) / median_rate if median_rate else 0.0,
                pause_before_ms=max(0, s.start_ms - prev_end),
                pause_after_ms=max(0, next_start - s.end_ms),
                speaker_switch=i > 0
                and s.speaker is not None
                and sentences[i - 1].speaker not in (None, s.speaker),
                question=is_question(s.text),
                events=ev,
            )
        )
    return report
