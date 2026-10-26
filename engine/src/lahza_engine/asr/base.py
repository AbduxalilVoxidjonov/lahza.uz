"""ASR backend interfeysi va VAD bo'yicha bo'laklash (TZ 5-bo'lim).

Talablar:
* til qat'iy `uz`; oldingi matnga tayanish o'chiq (takrorlanish halqasiga qarshi);
* faqat nutq bo'laklari, har biri <= 30 s (amalda ~10 s, ASR_TARGET_CHUNK_MS);
* lug'at (hotwords) dekoderga uzatiladi;
* chiqish - so'zlar (matn, boshlanish/tugash ms, ishonch bali bo'lsa).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, Protocol

from lahza_engine.text.personal_dict import apply_active
from lahza_engine.types import Word

MAX_CHUNK_MS = 30_000
"""Whisper oynasining qat'iy chegarasi."""
ASR_TARGET_CHUNK_MS = 10_000
"""Amalda ishlatiladigan bo'lak uzunligi. NavAI (o'zbekcha fine-tune) modellari 30 s oynada nutqning
katta qismini tashlab yuboradi va bo'shliqni bitta so'zga cho'zadi (150 s real nutqda, base:
30 s -> 240 so'z, 12 s -> 347, 10 s -> 370; eng uzun "so'z" 9.7 s -> <3 s). Qisqa bo'lak sekinroq
(har bo'lak 30 s ga to'ldiriladi), lekin siyrak transkriptni bartaraf etadi."""
SPARSE_WPM = 60.0
"""Nutq daqiqasiga bundan kam so'z - transkript shubhali darajada siyrak."""


@dataclass
class AsrOptions:
    language: str = "uz"
    hotwords: list[str] = field(default_factory=list)
    threads: int = 0  # 0 = avtomatik
    # Deterministik dekodlash: temperature fallback (0.2..1.0) qisqa bo'laklarda tasodifiy
    # "ixtiro" qilingan so'zlar beradi. beam_size - faster-whisper/whisper-cli standarti.
    temperature: float = 0.0
    beam_size: int = 5
    # So'z vaqtlari manbai:
    # * "ctc" - matn timestamp tokenlarisiz dekodlanadi (`without_timestamps`); so'zlarga bo'lak
    #   ichida harf soniga proporsional taxminiy vaqt beriladi, aniq vaqtni stage_align (CTC) beradi.
    #   Timestamp tokenlari yoqilganda model gap oxiriga yo'q so'zlar qo'shadi: FLEURS uz (80 gap)
    #   WER base 41.7% -> 18.5%, small 20.0% -> 12.4%.
    # * "whisper" - eski rejim: whisper so'z vaqtlari (word_timestamps). Aligner yo'q bo'lsa
    #   majburan shu ishlatiladi (`resolve_timestamps`) - proporsional vaqt montaj uchun yaroqsiz.
    timestamps: Literal["ctc", "whisper"] = "ctc"


def align_in_windows(aligner: Any, words: list[Word], wav: Path,
                     windows: list[tuple[int, int]] | None) -> list[Word]:
    """Aligner'ni ASR bo'laklari oynalari bilan chaqiradi (qo'llamasa - oynalarsiz)."""
    import inspect

    if windows:
        try:
            params = inspect.signature(aligner).parameters
        except (TypeError, ValueError):
            params = {}
        if "windows" in params or any(p.kind is p.VAR_KEYWORD for p in params.values()):
            return aligner(words, wav, windows=[tuple(w) for w in windows])
    return aligner(words, wav)


def resolve_timestamps(opts: AsrOptions, aligner: Any | None) -> AsrOptions:
    """CTC aligner bo'lmasa "ctc" rejimi "whisper" ga almashtiriladi (vaqtlar aniq qolishi uchun)."""
    if opts.timestamps == "ctc" and aligner is None:
        return replace(opts, timestamps="whisper")
    return opts


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


def _quietest_cut(pcm: Any, sample_rate: int, lo_ms: int, hi_ms: int, frame_ms: int = 20) -> int:
    """[lo_ms, hi_ms) oralig'idagi eng past energiyali kadr markazi (ms) - so'z o'rtasidan kesmaslik uchun."""
    import numpy as np

    hop = max(1, sample_rate * frame_ms // 1000)
    a, b = lo_ms * sample_rate // 1000, min(len(pcm), hi_ms * sample_rate // 1000)
    n = (b - a) // hop
    if n <= 1:
        return hi_ms
    frames = np.asarray(pcm[a : a + n * hop], dtype=np.float32).reshape(n, hop)
    i = int(np.argmin((frames**2).mean(axis=1)))
    return lo_ms + i * frame_ms + frame_ms // 2


def _split_long(a: int, b: int, max_ms: int, pcm: Any | None, sample_rate: int) -> list[tuple[int, int]]:
    """max_ms dan uzun nutq oralig'ini bo'laklarga ajratadi.

    Audio berilsa - har kesim [max/2, max] oynasidagi eng jim joyda; bo'lmasa teng bo'laklar
    (oldingi `max + kichik qoldiq` o'rniga, oxirgi bo'lak 1-2 s bo'lib qolmasin).
    """
    out: list[tuple[int, int]] = []
    t = a
    if pcm is None:
        n = -(-(b - a) // max_ms)
        step = -(-(b - a) // n)
        while t < b:
            out.append((t, min(b, t + step)))
            t += step
        return out
    while b - t > max_ms:
        cut = _quietest_cut(pcm, sample_rate, t + max_ms // 2, t + max_ms)
        cut = min(max(cut, t + 1), t + max_ms)
        out.append((t, cut))
        t = cut
    out.append((t, b))
    return out


def plan_chunks(
    speech: list[tuple[int, int]],
    max_ms: int = ASR_TARGET_CHUNK_MS,
    pad_ms: int = 200,
    pcm: Any | None = None,
    sample_rate: int = 16_000,
) -> list[tuple[int, int]]:
    """VAD oraliqlarini <= max_ms bo'laklarga birlashtiradi; uzun nutqni bo'laklarga ajratadi.

    pcm (mono float, sample_rate) berilsa uzun nutq eng jim nuqtalarda kesiladi.
    """
    max_ms = min(max_ms, MAX_CHUNK_MS)
    chunks: list[tuple[int, int]] = []
    cur: tuple[int, int] | None = None
    for a, b in speech:
        a, b = max(0, a - pad_ms), b + pad_ms
        if b - a > max_ms:
            if cur:
                chunks.append(cur)
                cur = None
            chunks.extend(_split_long(a, b, max_ms, pcm, sample_rate))
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


def plausible_word_ms(text: str) -> int:
    """Bitta so'z ekranda/eshitishda odatda shundan uzun davom etmaydi (o'zbekcha ~8-15 belgi/s)."""
    return min(3_000, 600 + 120 * len(text.strip()))


def transcript_density(
    words: list[Word], speech: list[tuple[int, int]] | None = None, duration_ms: int | None = None,
) -> dict[str, Any]:
    """Siyrak transkript diagnostikasi.

    * words_per_min - nutq daqiqasiga so'z (VAD bo'lsa nutq vaqti, bo'lmasa umumiy vaqt);
      o'zbekcha jonli nutq ~110-170;
    * longest_word_ms / stretched_words - model nutqni tashlab, bo'shliqni bitta so'zga
      "cho'zgan" holatlar (whisper so'z vaqtlarining ma'lum xatosi);
    * longest_gap_ms - ketma-ket so'zlar orasidagi eng uzun bo'shliq;
    * sparse - yuqoridagilardan biri me'yordan tashqarida.
    """
    ws = sorted(words, key=lambda w: w.start_ms)
    if speech:
        span_ms = sum(max(0, b - a) for a, b in speech)
    elif duration_ms is not None:
        span_ms = duration_ms
    else:
        span_ms = (ws[-1].end_ms - ws[0].start_ms) if ws else 0
    wpm = len(ws) / (span_ms / 60_000) if span_ms > 0 else 0.0
    stretched = [w for w in ws if w.end_ms - w.start_ms > plausible_word_ms(w.text)]
    gaps = [b.start_ms - a.end_ms for a, b in zip(ws, ws[1:], strict=False)]
    longest_word = max((w.end_ms - w.start_ms for w in ws), default=0)
    longest_gap = max(gaps, default=0)
    stretched_ms = sum(w.end_ms - w.start_ms - plausible_word_ms(w.text) for w in stretched)
    sparse = bool(span_ms >= 30_000 and (
        wpm < SPARSE_WPM or stretched_ms > 0.05 * span_ms or longest_gap > 15_000))
    return {
        "words": len(ws),
        "speech_ms": int(span_ms),
        "words_per_min": round(wpm, 1),
        "longest_word_ms": int(longest_word),
        "stretched_words": len(stretched),
        "stretched_ms": int(stretched_ms),
        "longest_gap_ms": int(longest_gap),
        "sparse": sparse,
    }


def spread_words(words: list[Word], start_ms: int, end_ms: int,
                 speech: list[tuple[int, int]] | None = None) -> list[Word]:
    """Taxminiy so'z vaqtlari: [start_ms, end_ms) ning nutq qismlari bo'ylab harf soniga proporsional.

    `speech` (VAD oraliqlari) berilsa, bo'lak ichidagi sukunatlar o'tkazib yuboriladi - so'zlar faqat
    nutq qismlariga tushadi, pauzalar esa so'zlar orasida qoladi (tinish tiklash va CTC oynalari uchun).
    Nutq bo'lakka tushmasa - butun oraliq. Matn tartibi saqlanadi.
    """
    if not words:
        return []
    from lahza_engine.align.realign import distribute

    end_ms = max(end_ms, start_ms + len(words))
    parts: list[tuple[int, int]] = []
    for a, b in sorted(speech or []):
        a, b = max(a, start_ms), min(b, end_ms)
        if b <= a:
            continue
        if parts and a <= parts[-1][1]:
            parts[-1] = (parts[-1][0], max(parts[-1][1], b))
        else:
            parts.append((a, b))
    total = sum(b - a for a, b in parts)
    if total < len(words):
        return distribute(words, start_ms, end_ms)

    def to_real(v: int, closing: bool) -> int:
        # Nutq vaqt o'qi -> manba vaqti; qism chegarasida so'z oxiri chapdagi, boshi o'ngdagi qismga.
        acc = 0
        for a, b in parts:
            n = b - a
            if v < acc + n or (closing and v == acc + n):
                return a + (v - acc)
            acc += n
        return parts[-1][1]

    out: list[Word] = []
    for w in distribute(words, 0, total):
        a = to_real(w.start_ms, False)
        b = max(a + 1, to_real(min(total, w.end_ms), True))
        out.append(w.model_copy(update={"start_ms": a, "end_ms": b}))
    return out


def dedupe_overlaps(words: list[Word]) -> list[Word]:
    """Bo'laklar chegarasida ikki marta tushgan so'zlarni olib tashlaydi."""
    out: list[Word] = []
    for w in sorted(words, key=lambda x: x.start_ms):
        if out and w.start_ms < out[-1].end_ms - 50 and w.text == out[-1].text:
            continue
        out.append(w)
    # PRO-1: tahlil vazifasida faol shaxsiy lug'at bo'lsa - post-tuzatish (aks holda o'zgarishsiz).
    return apply_active(out)
