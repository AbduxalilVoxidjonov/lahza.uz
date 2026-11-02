"""Siyrak transkript regressiyalari: 30 s ASR oynasi nutqni tashlab, bo'shliqni bitta so'zga
cho'zgan (real NavAI base natijasi: "ekan" 84.9 s -> 93.3 s), natijada bitta subtitr kartochkasi
~19 s ekranda qolgan."""

import numpy as np

from lahza_engine.asr.base import (
    ASR_TARGET_CHUNK_MS,
    MAX_CHUNK_MS,
    plan_chunks,
    plausible_word_ms,
    transcript_density,
)
from lahza_engine.subtitle.layout import MAX_CARD_MS, chunk_words, display_timings, hold_end
from lahza_engine.types import Word


def _w(text: str, a: int, b: int) -> Word:
    return Word(text=text, start_ms=a, end_ms=b)


# --- ASR bo'laklash ---------------------------------------------------------------------------


def test_default_chunks_are_short() -> None:
    # 30 daqiqa uzluksiz nutqqa o'xshash: qisqa pauzali VAD oraliqlari.
    speech = [(i * 4_000, i * 4_000 + 3_800) for i in range(450)]
    chunks = plan_chunks(speech)
    assert ASR_TARGET_CHUNK_MS <= 12_000
    assert all(b - a <= ASR_TARGET_CHUNK_MS for a, b in chunks)
    # hech bir nutq oralig'i tushib qolmaydi
    for a, b in speech:
        assert any(ca <= a and b <= cb for ca, cb in chunks)


def test_max_ms_never_exceeds_whisper_window() -> None:
    chunks = plan_chunks([(0, 100_000)], max_ms=60_000, pad_ms=0)
    assert all(b - a <= MAX_CHUNK_MS for a, b in chunks)


def test_long_speech_split_without_tiny_tail() -> None:
    chunks = plan_chunks([(0, 21_000)], max_ms=10_000, pad_ms=0)
    assert chunks[0][0] == 0 and chunks[-1][1] == 21_000
    assert all(b - a <= 10_000 for a, b in chunks)
    assert min(b - a for a, b in chunks) >= 6_000  # 10+10+1 emas, 7+7+7
    assert all(x[1] == y[0] for x, y in zip(chunks, chunks[1:], strict=False))  # uzilishsiz


def test_long_speech_split_at_quietest_point() -> None:
    sr = 16_000
    rng = np.random.default_rng(0)
    pcm = (rng.standard_normal(sr * 20) * 0.3).astype(np.float32)
    quiet = int(7.3 * sr)
    pcm[quiet : quiet + sr // 10] = 0.0  # 7.30-7.40 s - jimlik
    chunks = plan_chunks([(0, 20_000)], max_ms=10_000, pad_ms=0, pcm=pcm, sample_rate=sr)
    assert 7_300 <= chunks[0][1] <= 7_400
    assert chunks[-1][1] == 20_000
    assert all(b - a <= 10_000 for a, b in chunks)
    assert all(x[1] == y[0] for x, y in zip(chunks, chunks[1:], strict=False))


# --- Diagnostika ------------------------------------------------------------------------------


def test_density_flags_stretched_sparse_transcript() -> None:
    speech = [(0, 60_000)]
    # 60 s nutqda 40 so'z, ulardan biri 19 s ga cho'zilgan
    words = [_w(f"soz{i}", i * 1_000, i * 1_000 + 400) for i in range(39)]
    words.append(_w("ekan", 40_000, 59_000))
    d = transcript_density(words, speech)
    assert d["sparse"] is True
    assert d["longest_word_ms"] == 19_000
    assert d["stretched_words"] == 1
    assert d["words_per_min"] == 40.0


def test_density_ok_for_normal_speech() -> None:
    speech = [(0, 60_000)]
    words = [_w("salom", i * 400, i * 400 + 350) for i in range(150)]
    d = transcript_density(words, speech)
    assert d["sparse"] is False
    assert d["words_per_min"] == 150.0
    assert d["stretched_words"] == 0
    assert d["longest_gap_ms"] == 50


# --- Subtitr kartochkalari --------------------------------------------------------------------


def test_stretched_word_does_not_hold_card_for_19s() -> None:
    words = [_w("shunaqa", 80_000, 80_500), _w("qoʻllarimiz", 80_500, 81_000), _w("bor", 81_000, 81_300),
             _w("ekan", 81_300, 100_300), _w("qisqagina", 100_400, 100_900)]
    chunks = chunk_words(words, max_words=7, max_lines=2, max_chars=30)
    for i, ch in enumerate(chunks):
        end = hold_end(chunks, i, 400)
        assert end - ch.start_ms <= MAX_CARD_MS
    ekan = next(w for ch in chunks for w in ch.words if w.text == "ekan")
    assert ekan.start_ms == 81_300
    assert ekan.end_ms - ekan.start_ms <= plausible_word_ms("ekan")


def test_card_duration_cap_without_pauses() -> None:
    # Pauza ham, tinish belgisi ham yo'q, so'zlar uzun-uzun (sekin nutq).
    words = [_w("a" * 10, i * 1_500, (i + 1) * 1_500) for i in range(7)]
    assert chunk_words(words, 7, 2, 40, max_card_ms=60_000)[0].words == words  # chegarasiz - bitta
    chunks = chunk_words(words, max_words=7, max_lines=2, max_chars=40, max_card_ms=6_000)
    assert [len(c.words) for c in chunks] == [4, 3]
    assert all(ch.end_ms - ch.start_ms <= 6_000 for ch in chunks)
    assert sum(len(ch.words) for ch in chunks) == 7


def test_card_cap_overrides_bound_pair() -> None:
    words = [_w("Ali", 0, 900), _w("Valiyev", 900, 2_400)]
    assert len(chunk_words(words, 7, 2, 40)) == 1  # ism-familiya birga
    chunks = chunk_words(words, max_words=7, max_lines=2, max_chars=40, max_card_ms=2_000)
    assert len(chunks) == 2


def test_segment_level_timings_distributed_by_length() -> None:
    # So'z darajasidagi vaqt yo'q: butun segment har bir so'zga berilgan.
    seg = (10_000, 13_000)
    words = [_w(t, *seg) for t in ("bu", "juda", "qiziqarli", "voqea")]
    out = display_timings(words)
    assert out[0].start_ms == 10_000 and out[-1].end_ms == 13_000
    assert all(x.end_ms <= y.start_ms for x, y in zip(out, out[1:], strict=False))
    durs = [w.end_ms - w.start_ms for w in out]
    assert durs[2] > durs[1] > durs[0]  # harf soniga proporsional
    chunks = chunk_words(words, max_words=2, max_lines=1, max_chars=30)
    assert [len(c.words) for c in chunks] == [2, 2]
    assert chunks[0].end_ms < chunks[1].start_ms + 1


def test_zero_length_followers_get_time() -> None:
    words = [_w("salom", 0, 1_000), _w("dunyo", 1_000, 1_000)]
    out = display_timings(words)
    assert all(w.end_ms > w.start_ms for w in out)
    assert out[-1].end_ms == 1_000


def test_normal_word_timings_untouched() -> None:
    words = [_w("salom", 0, 400), _w("dunyo", 450, 900)]
    assert display_timings(words) == words
