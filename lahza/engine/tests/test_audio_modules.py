import numpy as np
import pytest

from lahza_engine.align.ctc import forced_align, word_times
from lahza_engine.asr.base import dedupe_overlaps, plan_chunks
from lahza_engine.asr.whisper_cpp import parse_whisper_json
from lahza_engine.diarize.assign import Turn, assign_speakers
from lahza_engine.eval_metrics import boundary_errors, cer, precision_at_k, recall, wer
from lahza_engine.text.orthography import TURNED_COMMA
from lahza_engine.types import Word
from lahza_engine.vad.energy import energy_vad


def _emissions(seq: list[int], V: int = 5, peak: float = 0.97) -> np.ndarray:
    T = len(seq)
    lp = np.full((T, V), (1 - peak) / (V - 1))
    for t, k in enumerate(seq):
        lp[t, k] = peak
    return np.log(lp)


def test_ctc_forced_align_recovers_spans() -> None:
    # kadrlar: blank,1,1,blank,2,2,2,blank,3,blank  (0 = blank)
    seq = [0, 1, 1, 0, 2, 2, 2, 0, 3, 0]
    spans = forced_align(_emissions(seq), [1, 2, 3])
    assert [(s.start_frame, s.end_frame) for s in spans] == [(1, 3), (4, 7), (8, 9)]
    words = word_times(spans, [2, 1], frame_ms=20.0, offset_ms=1000)
    assert words[0][:2] == (1020, 1140) and words[1][:2] == (1160, 1180)


def test_ctc_repeated_token_needs_blank() -> None:
    seq = [1, 0, 1]
    spans = forced_align(_emissions(seq), [1, 1])
    assert [(s.start_frame, s.end_frame) for s in spans] == [(0, 1), (2, 3)]


def test_ctc_too_short_raises() -> None:
    with pytest.raises(ValueError):
        forced_align(_emissions([1]), [1, 1])


def test_plan_chunks_limits_length() -> None:
    chunks = plan_chunks([(0, 5_000), (6_000, 12_000), (13_000, 80_000)], max_ms=30_000, pad_ms=0)
    assert all(b - a <= 30_000 for a, b in chunks)
    assert chunks[0] == (0, 12_000)
    assert chunks[-1][1] == 80_000


def test_dedupe_overlaps() -> None:
    w = [Word(text="salom", start_ms=0, end_ms=300), Word(text="salom", start_ms=100, end_ms=320),
         Word(text="dunyo", start_ms=400, end_ms=700)]
    assert [x.text for x in dedupe_overlaps(w)] == ["salom", "dunyo"]


def test_parse_whisper_json() -> None:
    data = {"transcription": [
        {"offsets": {"from": 0, "to": 320}, "text": " O'zbekiston"},
        {"offsets": {"from": 320, "to": 320}, "text": " bo'sh"},
        {"offsets": {"from": 400, "to": 600}, "text": "[_BEG_]"},
        {"offsets": {"from": 600, "to": 900}, "text": " ma'no"},
    ]}
    words = parse_whisper_json(data, offset_ms=10_000)
    assert [w.text for w in words] == [f"O{TURNED_COMMA}zbekiston", "maʼno"]
    assert words[0].start_ms == 10_000


def test_assign_speakers() -> None:
    w = [Word(text="a", start_ms=0, end_ms=500), Word(text="b", start_ms=1_000, end_ms=1_400),
         Word(text="c", start_ms=5_000, end_ms=5_200)]
    turns = [Turn(0, 900, "A"), Turn(900, 2_000, "B")]
    out = assign_speakers(w, turns)
    assert [x.speaker for x in out] == ["A", "B", "B"]


def test_energy_vad_finds_speech() -> None:
    sr = 16_000
    rng = np.random.default_rng(0)
    pcm = np.concatenate([0.001 * rng.standard_normal(sr), 0.3 * rng.standard_normal(sr * 2),
                          0.001 * rng.standard_normal(sr)]).astype(np.float32)
    regions = energy_vad(pcm, sr)
    assert len(regions) == 1
    a, b = regions[0]
    assert 900 <= a <= 1_100 and 2_900 <= b <= 3_100


def test_metrics() -> None:
    assert wer("O'zbekiston go'zal", "O‘zbekiston go'zal") == 0.0
    assert wer("bir ikki uch", "bir uch") == pytest.approx(1 / 3)
    assert cer("abc", "abd") > 0
    assert boundary_errors([(0, 100)], [(10, 130)]) == {"median_ms": 20.0, "p95_ms": 29.0}
    assert precision_at_k([(0, 10), (50, 60)], [(0, 9)], k=5) == 0.5
    assert recall([(0, 10)], [(0, 9), (100, 110)]) == 0.5
