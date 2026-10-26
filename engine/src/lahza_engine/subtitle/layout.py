"""So'zlarni ekrandagi subtitr bo'laklariga ajratish (TZ 9-bo'lim, "Maketlash qoidalari").

Qoidalar:
* Bir ekranda 1..max_words so'z, 1..max_lines qator; qator uzunligi shrift o'lchamidan.
* Bo'linish avval pauza va tinish belgisida.
* Bog'liq juftliklar ajratilmaydi: son + birlik, ketma-ket bosh harfli so'zlar (ism-familiya).
* Bir ekran MAX_CARD_MS dan uzun turmaydi. ASR nutqni tashlab, bo'shliqni bitta so'zga cho'zgan
  bo'lsa (whisper xatosi) - so'z ko'rinishi `plausible_word_ms` bilan cheklanadi; bir nechta so'z
  bitta umumiy vaqtni bo'lishsa (so'z darajasidagi vaqt yo'q) - oraliq harf soniga proporsional
  taqsimlanadi.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from lahza_engine.align.realign import distribute
from lahza_engine.asr.base import plausible_word_ms
from lahza_engine.text.orthography import fold_for_match
from lahza_engine.types import Word

# Son bilan birga ajralmas keladigan birlik so'zlari (kengaytiriladi).
UNIT_WORDS = frozenset(
    {"foiz", "so'm", "dollar", "yil", "yilda", "ta", "kishi", "marta", "daqiqa", "soniya", "soat",
     "kun", "oy", "hafta", "metr", "kilogramm", "million", "milliard", "ming"}
)
_BREAK_PUNCT = (".", ",", "?", "!", "…", ":", ";", "—")
MAX_CARD_MS = 6_000
"""Bitta subtitr kartochkasining eng uzun davomiyligi."""
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


def display_timings(words: list[Word]) -> list[Word]:
    """Subtitr uchun so'z vaqtlarini tuzatadi (manba transkripti o'zgarmaydi).

    1. Umumiy vaqtli guruh: ketma-ket so'zlar bir xil (start, end) ga ega yoki nol uzunlikda -
       segment darajasidagi vaqt; guruh oralig'i harf soniga proporsional bo'linadi.
    2. Cho'zilgan so'z: davomiyligi `plausible_word_ms` dan oshsa, tugashi qisqartiriladi
       (boshlanish saqlanadi - whisper tashlab ketgan nutq odatda so'zdan keyin keladi).
    """
    out: list[Word] = []
    i = 0
    while i < len(words):
        j = i + 1
        w = words[i]
        while j < len(words) and (
            (words[j].start_ms, words[j].end_ms) == (w.start_ms, w.end_ms)
            or (words[j].end_ms <= words[j].start_ms and words[j].start_ms <= w.end_ms)
        ):
            j += 1
        group = words[i:j]
        if len(group) > 1:
            a = min(x.start_ms for x in group)
            b = max(x.end_ms for x in group)
            group = distribute(group, a, b)
        for x in group:
            cap = x.start_ms + plausible_word_ms(x.text)
            if x.end_ms > cap:
                x = x.model_copy(update={"end_ms": cap})
            out.append(x)
        i = j
    return out


def chunk_words(
    words: list[Word],
    max_words: int,
    max_lines: int,
    max_chars: int,
    pause_break_ms: int = 300,
    breaks_ms: Sequence[int] = (),
    max_card_ms: int = MAX_CARD_MS,
) -> list[CaptionChunk]:
    """breaks_ms: chiqish vaqtidagi majburiy chegaralar (masalan hook prefiksi oxiri) - hech bir
    bo'lak ularni kesib o'tmaydi (bog'liq juftlik qoidasidan ham ustun).
    max_card_ms: bo'lak davomiyligi chegarasi (bog'liq juftlikdan ham ustun)."""
    words = display_timings(words)
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
            forced = any(prev.start_ms < b <= w.start_ms for b in breaks_ms)
            too_long = w.end_ms - cur[0].start_ms > max_card_ms
            if forced or too_long or (not bound and (pause or punct or full)):
                flush()
        cur.append(w)
        sentence_initial = w.text.rstrip().endswith((".", "?", "!", "…"))
        if i == len(words) - 1:
            flush()
    return chunks


def hold_end(chunks: list[CaptionChunk], i: int, hold_ms: int, breaks_ms: Sequence[int] = ()) -> int:
    """Qisqa pauzalarda subtitr miltillamasin: bo'lak keyingisigacha (<= hold_ms) ushlab turiladi,
    lekin majburiy chegaradan (breaks_ms) oshmaydi."""
    ch = chunks[i]
    if i + 1 >= len(chunks):
        return ch.end_ms
    end = min(chunks[i + 1].start_ms, ch.end_ms + hold_ms)
    for b in breaks_ms:
        if ch.end_ms <= b < end:
            end = b
    return end


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
