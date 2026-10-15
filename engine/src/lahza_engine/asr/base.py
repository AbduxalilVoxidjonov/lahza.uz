"""ASR backend interfeysi va VAD bo'yicha bo'laklash (TZ 5-bo'lim).

Talablar:
* til qat'iy `uz`; oldingi matnga tayanish o'chiq (takrorlanish halqasiga qarshi);
* faqat nutq bo'laklari, har biri <= 30 s;
* lug'at (hotwords) dekoderga uzatiladi;
* chiqish - so'zlar (matn, boshlanish/tugash ms, ishonch bali bo'lsa).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from lahza_engine.types import Word

MAX_CHUNK_MS = 30_000


@dataclass
class AsrOptions:
    language: str = "uz"
    hotwords: list[str] = field(default_factory=list)
    threads: int = 0  # 0 = avtomatik


def hotword_prompt(hotwords: list[str], max_chars: int = 400) -> str | None:
    """Lug'at -> dekoder uchun qisqa ko'rsatma ("Ali, Lahza, ...").

    Whisper prompti ~224 token bilan cheklangan: takrorlar olib tashlanadi, uzunlik kesiladi.
    """
    seen: set[str] = set()
    parts: list[str] = []
    size = 0
    for h in hotwords:
        t = " ".join(h.split())
        if not t or t.lower() in seen:
            continue
        if size + len(t) + 2 > max_chars:
            break
        seen.add(t.lower())
        parts.append(t)
        size += len(t) + 2
    return ", ".join(parts) or None


class AsrBackend(Protocol):
    model_id: str

    def transcribe_chunk(self, wav: Path, offset_ms: int, opts: AsrOptions) -> list[Word]:
        """Bitta bo'lak (<= 30 s). Qaytgan vaqtlar offset_ms qo'shilgan, manba vaqtida."""
        ...


def plan_chunks(speech: list[tuple[int, int]], max_ms: int = MAX_CHUNK_MS, pad_ms: int = 200) -> list[tuple[int, int]]:
    """VAD oraliqlarini <= max_ms bo'laklarga birlashtiradi; uzun nutqni teng bo'laklarga ajratadi."""
    chunks: list[tuple[int, int]] = []
    cur: tuple[int, int] | None = None
    for a, b in speech:
        a, b = max(0, a - pad_ms), b + pad_ms
        if b - a > max_ms:
            if cur:
                chunks.append(cur)
                cur = None
            t = a
            while t < b:
                chunks.append((t, min(b, t + max_ms)))
                t += max_ms
            continue
        if cur is None:
            cur = (a, b)
        elif b - cur[0] <= max_ms:
            cur = (cur[0], max(cur[1], b))
        else:
            chunks.append(cur)
            cur = (a, b)
    if cur:
        chunks.append(cur)
    return chunks


def dedupe_overlaps(words: list[Word]) -> list[Word]:
    """Bo'laklar chegarasida ikki marta tushgan so'zlarni olib tashlaydi."""
    out: list[Word] = []
    for w in sorted(words, key=lambda x: x.start_ms):
        if out and w.start_ms < out[-1].end_ms - 50 and w.text == out[-1].text:
            continue
        out.append(w)
    return out
