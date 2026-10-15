"""Diarizatsiya natijasini so'zlarga biriktirish (TZ 6-bo'lim).

Backend: pyannote `speaker-diarization-community-1` (CC-BY-4.0), lokal papkadan yuklanadi va
"exclusive" (bir vaqtda bitta spiker) rejimidan foydalaniladi.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from lahza_engine.types import Word


@dataclass(frozen=True)
class Turn:
    start_ms: int
    end_ms: int
    speaker: str


def assign_speakers(words: list[Word], turns: list[Turn]) -> list[Word]:
    """Har so'zga eng ko'p ustma-ust tushgan spiker; ustma-ustlik bo'lmasa - eng yaqini."""
    if not turns:
        return words
    turns = sorted(turns, key=lambda t: t.start_ms)
    out = []
    for w in words:
        best, best_ov = None, 0
        for t in turns:
            if t.start_ms > w.end_ms:
                break
            ov = min(w.end_ms, t.end_ms) - max(w.start_ms, t.start_ms)
            if ov > best_ov:
                best, best_ov = t.speaker, ov
        if best is None:
            mid = (w.start_ms + w.end_ms) / 2
            best = min(turns, key=lambda t: min(abs(mid - t.start_ms), abs(mid - t.end_ms))).speaker
        out.append(w.model_copy(update={"speaker": best}))
    return out


def normalize_labels(turns: list[Turn], mapping: dict[str, str] | None = None) -> list[Turn]:
    """Spiker yorliqlarini paydo bo'lish tartibida "S1", "S2", ... ga o'giradi.

    `mapping` berilsa (masalan, to'liq diarizatsiyadan) shu xarita qo'llanadi va to'ldiriladi.
    """
    m = mapping if mapping is not None else {}
    out = []
    for t in sorted(turns, key=lambda t: (t.start_ms, t.end_ms)):
        if t.speaker not in m:
            m[t.speaker] = f"S{len(m) + 1}"
        out.append(Turn(t.start_ms, t.end_ms, m[t.speaker]))
    return out


def find_overlaps(turns: list[Turn], min_ms: int = 100) -> list[tuple[int, int]]:
    """Kamida ikki turli spiker bir vaqtda gapirgan oraliqlar (birlashtirilgan, >= min_ms)."""
    events: list[tuple[int, int, str]] = []
    for t in turns:
        if t.end_ms > t.start_ms:
            events.append((t.start_ms, 1, t.speaker))
            events.append((t.end_ms, -1, t.speaker))
    events.sort(key=lambda e: (e[0], e[1]))  # bir nuqtada avval tugash, keyin boshlanish
    active: dict[str, int] = {}
    raw: list[tuple[int, int]] = []
    start: int | None = None
    for t, kind, spk in events:
        active[spk] = active.get(spk, 0) + kind
        if active[spk] <= 0:
            active.pop(spk)
        n = len(active)
        if n >= 2 and start is None:
            start = t
        elif n < 2 and start is not None:
            if t > start:
                raw.append((start, t))
            start = None
    merged: list[tuple[int, int]] = []
    for a, b in raw:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return [(a, b) for a, b in merged if b - a >= min_ms]


@dataclass
class DiarizationResult:
    turns: list[Turn]  # exclusive (bir vaqtda bitta spiker) - so'zlarga biriktirish uchun
    overlaps: list[tuple[int, int]] = field(default_factory=list)


def _to_turns(annotation) -> list[Turn]:  # noqa: ANN001 - pyannote.core.Annotation
    return [
        Turn(int(seg.start * 1000), int(seg.end * 1000), str(label))
        for seg, _, label in annotation.itertracks(yield_label=True)
    ]


class PyannoteDiarizer:
    """pyannote.audio 4: `Pipeline.from_pretrained(<lokal papka>)`, tarmoqsiz (HF_HUB_OFFLINE=1)."""

    def __init__(self, model_dir: Path) -> None:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        from pyannote.audio import Pipeline

        self.pipeline = Pipeline.from_pretrained(str(model_dir))
        if self.pipeline is None:
            raise RuntimeError(f"pyannote pipeline yuklanmadi: {model_dir}")

    def diarize(self, wav: Path, num_speakers: int | None = None) -> DiarizationResult:
        kwargs = {"num_speakers": num_speakers} if num_speakers else {}
        output = self.pipeline(str(wav), **kwargs)
        full_ann = getattr(output, "speaker_diarization", None)
        if full_ann is None:  # pyannote 3.x: natija to'g'ridan-to'g'ri Annotation
            full_ann = output
        excl_ann = getattr(output, "exclusive_speaker_diarization", None)
        if excl_ann is None:
            excl_ann = full_ann
        mapping: dict[str, str] = {}
        full = normalize_labels(_to_turns(full_ann), mapping)
        excl = normalize_labels(_to_turns(excl_ann), mapping)
        return DiarizationResult(excl, find_overlaps(full))

    def __call__(self, wav: Path, num_speakers: int | None = None) -> list[Turn]:
        return self.diarize(wav, num_speakers).turns
