"""Klip chegaralarini gap/pauza bo'yicha tekislash (TZ 7-bo'lim). Bu ishni kod qiladi, LLM emas.

Kafolat: klip hech qachon so'z o'rtasida boshlanmaydi yoki tugamaydi - chegaralar faqat gap
chegarasidan hisoblanadi va qo'shni gapga kirib ketmaydi.
"""

from __future__ import annotations

from dataclasses import dataclass

from lahza_engine.config import HighlightConfig
from lahza_engine.types import Sentence

_GUARD_MS = 20  # qo'shni gapning birinchi/oxirgi so'ziga tegmaslik uchun


@dataclass(frozen=True)
class ClipSpan:
    start_id: int
    end_id: int
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


def _span(sentences: list[Sentence], a: int, b: int, cfg: HighlightConfig) -> ClipSpan:
    first, last = sentences[a], sentences[b]
    start = first.start_ms - cfg.pre_roll_ms
    if a > 0:
        start = max(start, sentences[a - 1].end_ms + _GUARD_MS)
    start = max(0, min(start, first.start_ms))
    end = last.end_ms + cfg.post_roll_ms
    if b + 1 < len(sentences):
        end = min(end, sentences[b + 1].start_ms - _GUARD_MS)
    end = max(end, last.end_ms)
    return ClipSpan(a, b, start, end)


def _gap_before(sentences: list[Sentence], i: int) -> int:
    if i == 0:
        return 10**9
    return sentences[i].start_ms - sentences[i - 1].end_ms


def snap(
    sentences: list[Sentence],
    start_id: int,
    end_id: int,
    cfg: HighlightConfig,
    min_ms: int | None = None,
    max_ms: int | None = None,
) -> ClipSpan:
    """Gap ID oralig'ini haqiqiy vaqt oralig'iga aylantiradi va davomiylikni moslaydi."""
    if not sentences:
        raise ValueError("bo'sh transkript")
    n = len(sentences)
    a = max(0, min(start_id, n - 1))
    b = max(a, min(end_id, n - 1))
    lo = cfg.min_clip_ms if min_ms is None else min_ms
    hi = cfg.max_clip_ms if max_ms is None else max_ms

    # Boshlanishni pauzasi yetarli gapga surish (ko'pi bilan 3 qadam, max'dan oshmasdan).
    for _ in range(3):
        if a == 0 or _gap_before(sentences, a) >= cfg.min_pause_before_start_ms:
            break
        if _span(sentences, a - 1, b, cfg).duration_ms > hi:
            break
        a -= 1

    span = _span(sentences, a, b, cfg)
    # Juda uzun: oxiridan gap-gap qisqartirish.
    while span.duration_ms > hi and b > a:
        b -= 1
        span = _span(sentences, a, b, cfg)
    # Juda qisqa: avval oxiriga, keyin boshiga gap qo'shish.
    while span.duration_ms < lo:
        if b + 1 < n and _span(sentences, a, b + 1, cfg).duration_ms <= hi:
            b += 1
        elif a > 0 and _span(sentences, a - 1, b, cfg).duration_ms <= hi:
            a -= 1
        else:
            break
        span = _span(sentences, a, b, cfg)
    return span
