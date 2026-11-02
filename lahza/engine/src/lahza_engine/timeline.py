"""Manba vaqti <-> klip (chiqish) vaqti xaritasi.

Klip = [start, end] oraliq minus foydalanuvchi matn orqali o'chirgan oraliqlar (cuts).
Subtitr, kamera yo'li va render hammasi shu xarita bo'yicha hisoblanadi.

PRO-3 "Hook oldinga": ixtiyoriy `hook=(a, b)` - klip ichidagi bo'lak (kesimlar chiqarilgan holda)
chiqishning boshiga nusxa sifatida qo'yiladi, keyin asosiy qism to'liq davom etadi. Shunda
`segments` manba vaqti bo'yicha monoton emas (avval hook, keyin klip boshidan). `to_out` asosiy
qismni xaritalaydi; hook nusxasi uchun `prefix_to_out`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lahza_engine.types import Clip


@dataclass(frozen=True)
class Segment:
    src_start_ms: int
    src_end_ms: int
    out_start_ms: int

    @property
    def duration_ms(self) -> int:
        return self.src_end_ms - self.src_start_ms


class Timeline:
    def __init__(self, start_ms: int, end_ms: int, cuts: list[tuple[int, int]] | None = None,
                 hook: tuple[int, int] | None = None):
        if end_ms <= start_ms:
            raise ValueError("end_ms > start_ms bo'lishi kerak")
        kept: list[tuple[int, int]] = []
        cursor = start_ms
        for a, b in sorted(cuts or []):
            a, b = max(a, start_ms), min(b, end_ms)
            if b <= a:
                continue
            if a > cursor:
                kept.append((cursor, a))
            cursor = max(cursor, b)
        if cursor < end_ms:
            kept.append((cursor, end_ms))
        prefix: list[tuple[int, int]] = []
        if hook is not None:
            ha, hb = hook
            prefix = [(max(a, ha), min(b, hb)) for a, b in kept if min(b, hb) > max(a, ha)]
        self.segments: list[Segment] = []
        out = 0
        for a, b in prefix:
            self.segments.append(Segment(a, b, out))
            out += b - a
        self.prefix_ms = out
        """Hook nusxasining chiqishdagi davomiyligi (hook yo'q bo'lsa 0)."""
        self._n_prefix = len(prefix)
        for a, b in kept:
            self.segments.append(Segment(a, b, out))
            out += b - a
        self.duration_ms = out

    @property
    def prefix_segments(self) -> list[Segment]:
        return self.segments[: self._n_prefix]

    @property
    def body_segments(self) -> list[Segment]:
        return self.segments[self._n_prefix :]

    def prefix_to_out(self, src_ms: int) -> int | None:
        """Manba vaqtini hook nusxasidagi chiqish vaqtiga (hook tashqarisida - None)."""
        for seg in self.prefix_segments:
            if seg.src_start_ms <= src_ms <= seg.src_end_ms:
                return seg.out_start_ms + (src_ms - seg.src_start_ms)
        return None

    def to_out(self, src_ms: int) -> int | None:
        """Manba vaqtini (asosiy qismdagi) chiqish vaqtiga. O'chirilgan joyga tushsa - None."""
        for seg in self.body_segments:
            if seg.src_start_ms <= src_ms <= seg.src_end_ms:
                return seg.out_start_ms + (src_ms - seg.src_start_ms)
        return None

    def clamp_to_out(self, src_ms: int) -> int:
        """O'chirilgan joyga tushsa, keyingi saqlangan nuqtaga yopishtiradi."""
        v = self.to_out(src_ms)
        if v is not None:
            return v
        for seg in self.body_segments:
            if src_ms < seg.src_start_ms:
                return seg.out_start_ms
        return self.duration_ms

    def to_src(self, out_ms: int) -> int:
        """Chiqish vaqtini manba vaqtiga (chegaradan tashqarisi yopishtiriladi)."""
        out_ms = max(0, min(self.duration_ms, out_ms))
        for seg in self.segments:
            if out_ms < seg.out_start_ms + seg.duration_ms:
                return seg.src_start_ms + (out_ms - seg.out_start_ms)
        last = self.segments[-1]
        return last.src_end_ms

    def boundaries_out(self) -> list[int]:
        """O'chirilgan joylar tufayli tasvir keskin almashadigan chiqish vaqtlari."""
        return [seg.out_start_ms for seg in self.segments[1:]]


def clip_timeline(clip: Clip) -> Timeline:
    """Klipning to'liq chiqish xaritasi: kesimlar + (yoqilgan bo'lsa) hook prefiksi."""
    hook = (clip.hook.start_ms, clip.hook.end_ms) if clip.hook is not None else None
    return Timeline(clip.start_ms, clip.end_ms, clip.cuts, hook=hook)
