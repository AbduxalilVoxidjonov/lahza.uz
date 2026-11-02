"""Bitta gapni qayta tekislash (M2-APP-4): foydalanuvchi so'zni tahrirlaganda butun fayl emas,
faqat o'sha gap oralig'i qayta hisoblanadi.

* aligner bo'lsa - `aligner.align_words(words, wav, start_ms, end_ms)` (CTC, ML agent).
* bo'lmasa - so'z soni o'zgargan (yoki vaqtlari yaroqsiz) bo'lsa, gap oralig'i harf soniga
  proporsional taqsimlanadi; so'z soni o'zgarmasa vaqtlar saqlanadi.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from lahza_engine.types import Sentence, Word

log = logging.getLogger(__name__)


def _timings_valid(words: list[Word]) -> bool:
    """Yangi qo'shilgan (bo'linish natijasidagi) so'zlar nol uzunlikda keladi."""
    return all(w.end_ms > w.start_ms for w in words)


def distribute(words: list[Word], start_ms: int, end_ms: int) -> list[Word]:
    """Oraliqni so'zlar orasida harf soniga proporsional taqsimlaydi (bo'shliqsiz, ketma-ket)."""
    if not words:
        return []
    span = max(len(words), end_ms - start_ms)
    weights = [max(1, len(w.text)) for w in words]
    total = sum(weights)
    out: list[Word] = []
    acc = 0
    for w, k in zip(words, weights, strict=True):
        a = start_ms + span * acc // total
        acc += k
        b = start_ms + span * acc // total
        out.append(w.model_copy(update={"start_ms": a, "end_ms": max(a + 1, b)}))
    return out


def realign_sentence(
    sentence: Sentence,
    wav_path: Path | None,
    aligner: Any | None,
    original_count: int | None = None,
) -> Sentence:
    """Gapning so'z vaqtlarini qayta hisoblaydi va yangi Sentence qaytaradi.

    `original_count` - tahrirdan oldingi so'z soni (berilsa, so'z soni o'zgarganini aniqlash uchun).
    """
    words = list(sentence.words)
    start, end = sentence.start_ms, max(sentence.end_ms, sentence.start_ms + 1)
    if not words:
        return sentence.model_copy(update={"words": []})
    if aligner is not None and wav_path is not None and Path(wav_path).exists():
        try:
            aligned = aligner.align_words(words, Path(wav_path), start, end)
            if len(aligned) == len(words):
                return sentence.model_copy(update={"words": list(aligned)})
            log.warning("aligner so'z sonini o'zgartirdi - proporsional zaxiraga o'tildi")
        except Exception as e:  # noqa: BLE001 - zaxira usul bor
            log.warning("gapni qayta tekislash muvaffaqiyatsiz (%s) - proporsional zaxira",
                        type(e).__name__)
    count_changed = original_count is not None and original_count != len(words)
    if count_changed or not _timings_valid(words):
        words = distribute(words, start, end)
    return sentence.model_copy(update={"words": words})
