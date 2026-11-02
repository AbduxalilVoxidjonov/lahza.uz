"""Klip boshlanishi uchun jarima qoidalari (TZ 7-bo'lim).

Ro'yxatlar foydalanuvchi/jamoa tomonidan kengaytiriladi; bu yerda TZ'da sanab o'tilgan
holatlar va ularning bevosita variantlari.
"""

from __future__ import annotations

from lahza_engine.text.orthography import fold_for_match

# TZ: "va", "lekin", "shuning uchun" bilan boshlanish.
CONNECTIVE_STARTS: tuple[str, ...] = ("va", "lekin", "shuning uchun")
# TZ: kontekstsiz olmosh ("u", "bu narsa") bilan boshlanish.
PRONOUN_STARTS: tuple[str, ...] = ("u", "bu narsa")

QUESTION_WORDS: tuple[str, ...] = ("nima", "nega", "qanday", "qachon", "qayerda", "kim", "qancha")


def _starts_with_phrase(folded: str, phrase: str) -> bool:
    return folded == phrase or folded.startswith(phrase + " ")


def start_penalty(sentence_text: str) -> tuple[float, list[str]]:
    """0..1 oralig'idagi jarima va sabablar ro'yxati."""
    folded = fold_for_match(sentence_text).strip(" ,.-—")
    reasons: list[str] = []
    for p in CONNECTIVE_STARTS:
        if _starts_with_phrase(folded, p):
            reasons.append(f"bog'lovchi bilan boshlanadi: '{p}'")
            break
    for p in PRONOUN_STARTS:
        if _starts_with_phrase(folded, p):
            reasons.append(f"kontekstsiz olmosh bilan boshlanadi: '{p}'")
            break
    return (min(1.0, 0.5 * len(reasons)), reasons)


def is_question(sentence_text: str) -> bool:
    folded = fold_for_match(sentence_text).strip()
    if folded.endswith("?"):
        return True
    first = folded.split(" ", 1)[0] if folded else ""
    return first in QUESTION_WORDS
