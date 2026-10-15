"""So'zlarni ekrandagi subtitr bo'laklariga ajratish (TZ 9-bo'lim, "Maketlash qoidalari").

Qoidalar:
* Bir ekranda 1..max_words so'z, 1..max_lines qator; qator uzunligi shrift o'lchamidan.
* Bo'linish avval pauza va tinish belgisida.
* Bog'liq juftliklar ajratilmaydi: son + birlik, ketma-ket bosh harfli so'zlar (ism-familiya).
"""

from __future__ import annotations

from dataclasses import dataclass

from lahza_engine.text.orthography import fold_for_match
from lahza_engine.types import Word

# Son bilan birga ajralmas keladigan birlik so'zlari (kengaytiriladi).
UNIT_WORDS = frozenset(
    {"foiz", "so'm", "dollar", "yil", "yilda", "ta", "kishi", "marta", "daqiqa", "soniya", "soat",
     "kun", "oy", "hafta", "metr", "kilogramm", "million", "milliard", "ming"}
)
_BREAK_PUNCT = (".", ",", "?", "!", "…", ":", ";", "—")
CHAR_WIDTH_FACTOR = 0.55
"""O'rtacha belgi eni ~ font_size * 0.55 (taxminiy; aniq o'lchov - libass, M3)."""


@dataclass
class CaptionChunk:
    words: list[Word]
    lines: list[list[Word]]

    @property
    def start_ms(self) -> int:
        return self.words[0].start_ms

    @property
    def end_ms(self) -> int:
        return self.words[-1].end_ms


def max_chars_per_line(font_size: int, usable_width_px: int) -> int:
    return max(8, int(usable_width_px / (font_size * CHAR_WIDTH_FACTOR)))


def _is_number(token: str) -> bool:
    t = token.strip(".,%")
    return t.replace(" ", "").isdigit()


def _bound(prev: Word, nxt: Word, sentence_initial: bool) -> bool:
    """prev va nxt bitta bo'lakda qolishi shartmi?"""
    if _is_number(prev.text) and fold_for_match(nxt.text).strip(".,!?") in UNIT_WORDS:
        return True
    p, n = prev.text.strip(), nxt.text.strip()
    return bool(
        not sentence_initial
        and p[:1].isupper()
        and n[:1].isupper()
        and not p.endswith(_BREAK_PUNCT)
    )


def chunk_words(
    words: list[Word],
    max_words: int,
    max_lines: int,
    max_chars: int,
    pause_break_ms: int = 300,
) -> list[CaptionChunk]:
    chunks: list[CaptionChunk] = []
    cur: list[Word] = []
    sentence_initial = True

    def flush() -> None:
        if cur:
            chunks.append(CaptionChunk(list(cur), _wrap(cur, max_lines, max_chars)))
            cur.clear()

    for i, w in enumerate(words):
        if cur:
            prev = cur[-1]
            bound = _bound(prev, w, sentence_initial and len(cur) == 1)
            pause = w.start_ms - prev.end_ms >= pause_break_ms
            punct = prev.text.rstrip().endswith(_BREAK_PUNCT)
            full = len(cur) >= max_words or len(" ".join(x.text for x in cur + [w])) > max_chars * max_lines
            if not bound and (pause or punct or full):
                flush()
        cur.append(w)
        sentence_initial = w.text.rstrip().endswith((".", "?", "!", "…"))
        if i == len(words) - 1:
            flush()
    return chunks


def _wrap(words: list[Word], max_lines: int, max_chars: int) -> list[list[Word]]:
    lines: list[list[Word]] = [[]]
    for w in words:
        line = lines[-1]
        candidate = " ".join(x.text for x in line + [w])
        if line and len(candidate) > max_chars and len(lines) < max_lines:
            lines.append([w])
        else:
            line.append(w)
    return lines
