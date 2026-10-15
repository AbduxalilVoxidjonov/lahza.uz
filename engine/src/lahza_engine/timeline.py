"""Manba vaqti <-> klip (chiqish) vaqti xaritasi.

Klip = [start, end] oraliq minus foydalanuvchi matn orqali o'chirgan oraliqlar (cuts).
Subtitr, kamera yo'li va render hammasi shu xarita bo'yicha hisoblanadi.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    src_start_ms: int
    src_end_ms: int
    out_start_ms: int

    @property
    def duration_ms(self) -> int:
        return self.src_end_ms - self.src_start_ms


class Timeline:
    def __init__(self, start_ms: int, end_ms: int, cuts: list[tuple[int, int]] | None = None):
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
        self.segments: list[Segment] = []
        out = 0
        for a, b in kept:
            self.segments.append(Segment(a, b, out))
            out += b - a
        self.duration_ms = out

    def to_out(self, src_ms: int) -> int | None:
        """Manba vaqtini chiqish vaqtiga. O'chirilgan joyga tushsa - None."""
        for seg in self.segments:
            if seg.src_start_ms <= src_ms <= seg.src_end_ms:
                return seg.out_start_ms + (src_ms - seg.src_start_ms)
        return None

    def clamp_to_out(self, src_ms: int) -> int:
        """O'chirilgan joyga tushsa, keyingi saqlangan nuqtaga yopishtiradi."""
        v = self.to_out(src_ms)
        if v is not None:
            return v
        for seg in self.segments:
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
