"""So'zlar oqimini gaplarga bo'lish.

Gap - highlight, LLM va kesish uchun asosiy birlik: LLM gap ID'larini qaytaradi (ADR-0005).
"""

from __future__ import annotations

from collections.abc import Iterable

from lahza_engine.types import Sentence, Word

_TERMINAL = (".", "?", "!", "…")


def build_sentences(
    words: Iterable[Word],
    max_gap_ms: int = 700,
    max_len_ms: int = 15_000,
) -> list[Sentence]:
    """Gap chegarasi: tugovchi tinish belgisi, uzun pauza, spiker almashuvi yoki uzunlik chegarasi.

    max_gap_ms / max_len_ms - boshlang'ich qiymatlar (R0'da sozlanadi).
    """
    sentences: list[Sentence] = []
    current: list[Word] = []

    def flush() -> None:
        if not current:
            return
        sentences.append(
            Sentence(
                id=len(sentences),
                start_ms=current[0].start_ms,
                end_ms=current[-1].end_ms,
                speaker=_majority_speaker(current),
                words=list(current),
            )
        )
        current.clear()

    prev: Word | None = None
    for w in words:
        if prev is not None and current:
            gap = w.start_ms - prev.end_ms
            speaker_changed = (
                w.speaker is not None and prev.speaker is not None and w.speaker != prev.speaker
            )
            too_long = w.end_ms - current[0].start_ms > max_len_ms
            if gap >= max_gap_ms or speaker_changed or too_long:
                flush()
        current.append(w)
        if w.text.rstrip().endswith(_TERMINAL):
            flush()
        prev = w
    flush()
    return sentences


def _majority_speaker(words: list[Word]) -> str | None:
    counts: dict[str, int] = {}
    for w in words:
        if w.speaker is not None:
            counts[w.speaker] = counts.get(w.speaker, 0) + (w.end_ms - w.start_ms)
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]
