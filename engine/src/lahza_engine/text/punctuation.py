"""Qoidaviy tinish belgisi va katta harf tiklagich (M1-ASR-2).

Faqat ASR modeli matnni kichik harf va tinishsiz bergan holda ishlaydi (so'zlarning >90% kichik
harfda va birorta ham tinish belgisi yo'q). Qoidalar:
* pauza >= 700 ms dan oldingi so'z va oxirgi so'z - gap oxiri (".");
* savol so'zi bor yoki -mi/-mikan bilan tugagan gap - "?";
* gap boshidagi so'z - katta harf bilan.
"""

from __future__ import annotations

import re

from lahza_engine.types import Word

_PUNCT = re.compile(r"[.,!?…;:]")
_TRAIL = ".,!?…;:\"'»)"
QUESTION_WORDS = frozenset({
    "nega", "nimaga", "nima", "nimani", "nimadan", "nimada", "nimasi", "qanday",
    "qanaqa", "qachon", "kim", "kimga", "kimni", "kimning", "kimdan", "kimlar", "qayer", "qayerda",
    "qayerga", "qayerdan", "qaysi", "qancha", "nechta", "necha", "nechanchi", "nahotki", "qani",
})
# -mi so'roq yuklamasi; "nomi", "ismi" kabi egalik qo'shimchali so'zlar istisno.
_QUESTION_SUFFIXES = ("mikan", "misiz", "misan", "mi")
_MI_EXCEPTIONS = frozenset({
    "nomi", "ismi", "qismi", "ilmi", "bilimi", "jismi", "rasmi", "hajmi", "tizimi",
    "umumi", "yarmi",
})


def needs_restoration(words: list[Word], lower_ratio: float = 0.9) -> bool:
    alpha = [w.text for w in words if any(c.isalpha() for c in w.text)]
    if not alpha:
        return False
    if any(_PUNCT.search(w.text) for w in words):
        return False
    lower = sum(1 for t in alpha if t == t.lower())
    return lower / len(alpha) > lower_ratio


def _bare(text: str) -> str:
    return text.strip(_TRAIL).lower()


def is_question(sentence: list[str]) -> bool:
    bare = [_bare(t) for t in sentence if t.strip()]
    if not bare:
        return False
    if any(t in QUESTION_WORDS for t in bare):
        return True
    last = bare[-1]
    if last in _MI_EXCEPTIONS or len(last) < 4:
        return False
    return last.endswith(_QUESTION_SUFFIXES)


def _capitalize(text: str) -> str:
    for i, c in enumerate(text):
        if c.isalpha():
            return text[:i] + c.upper() + text[i + 1 :]
    return text


def restore_punctuation(words: list[Word], pause_ms: int = 700, force: bool = False) -> list[Word]:
    """Kerak bo'lsa tinish va katta harfni tiklaydi; aks holda so'zlar o'zgarishsiz qaytadi."""
    if not words or not (force or needs_restoration(words)):
        return words
    out: list[Word] = []
    sent: list[int] = []

    def close() -> None:
        if not sent:
            return
        texts = [out[i].text for i in sent]
        mark = "?" if is_question(texts) else "."
        last = sent[-1]
        out[last] = out[last].model_copy(update={"text": out[last].text.rstrip() + mark})
        first = sent[0]
        out[first] = out[first].model_copy(update={"text": _capitalize(out[first].text)})
        sent.clear()

    for i, w in enumerate(words):
        out.append(w)
        if any(c.isalnum() for c in w.text):
            sent.append(i)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt is None or nxt.start_ms - w.end_ms >= pause_ms:
            close()
    close()
    return out
