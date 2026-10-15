import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from lahza_engine.align.ctc_onnx import CtcAligner, Tokenizer, group_words
from lahza_engine.core.analyze import stage_align
from lahza_engine.core.services import Services
from lahza_engine.types import Word

FRAME = 320  # 20 ms @ 16 kHz
VOCAB = {"<pad>": 0, "|": 1, **{c: i + 2 for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")}, "'": 28}


class _Inp:
    name = "input_values"


class FakeCtcSession:
    """Sintetik "akustik model": har 20 ms kadrdagi o'rtacha qiymat*100 = token ID."""

    def __init__(self, frames_div: int = 1) -> None:
        self.frames_div = frames_div

    def get_inputs(self):
        return [_Inp()]

    def run(self, _outs, feeds):
        x = feeds["input_values"][0]
        T = len(x) // FRAME // self.frames_div
        ids = np.rint(x[: T * FRAME * self.frames_div].reshape(T, -1).mean(axis=1) * 100).astype(int)
        logits = np.full((1, T, len(VOCAB)), -10.0, dtype=np.float32)
        logits[0, np.arange(T), np.clip(ids, 0, len(VOCAB) - 1)] = 10.0
        return [logits]


def _write_wav(path: Path, frames: dict[int, int], total_frames: int) -> None:
    sig = np.zeros(total_frames * FRAME, dtype=np.float32)
    for k, tok in frames.items():
        sig[k * FRAME : (k + 1) * FRAME] = tok / 100
    pcm = np.rint(sig * 32768).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm.tobytes())


def _speak(frames: dict[int, int], start_frame: int, word: str) -> int:
    for i, c in enumerate(word):
        frames[start_frame + i] = VOCAB[c]
    return start_frame + len(word)


def _aligner(**kw) -> CtcAligner:
    return CtcAligner(VOCAB, session=FakeCtcSession(**kw), normalize_input=False)


def test_tokenizer_uzbek_normalization() -> None:
    tok = Tokenizer(VOCAB)
    assert tok.blank == 0 and tok.sep == 1
    # ʻ va ʼ lug'atdagi "'" ga, katta harf kichikka; raqam va tinish tashlanadi
    assert tok.word_tokens("Doʻst,") == [VOCAB[c] for c in "do'st"]
    assert tok.word_tokens("maʼno") == [VOCAB[c] for c in "ma'no"]
    assert tok.word_tokens("2024") == []
    assert Tokenizer({"<blank>": 5, "a": 1}).blank == 5


def test_tokenizer_drops_apostrophe_if_not_in_vocab() -> None:
    tok = Tokenizer({"<pad>": 0, "o": 1, "g": 2})
    assert tok.word_tokens("oʻg") == [1, 2]


def test_ctc_aligner_recovers_word_times(tmp_path: Path) -> None:
    frames: dict[int, int] = {}
    _speak(frames, 30, "salom")
    frames[45] = VOCAB["|"]
    _speak(frames, 60, "do'st")
    wav = tmp_path / "a.wav"
    _write_wav(wav, frames, 150)
    words = [Word(text="Salom", start_ms=400, end_ms=1000), Word(text="doʻst.", start_ms=1100, end_ms=1700)]
    out = _aligner()(words, wav)
    assert [(w.start_ms, w.end_ms) for w in out] == [(600, 700), (1200, 1300)]
    assert [w.text for w in out] == ["Salom", "doʻst."]


def test_ctc_aligner_align_words_window(tmp_path: Path) -> None:
    frames: dict[int, int] = {}
    _speak(frames, 100, "bir")
    wav = tmp_path / "b.wav"
    _write_wav(wav, frames, 200)
    out = _aligner().align_words([Word(text="bir", start_ms=1900, end_ms=2400)], wav, 1900, 2400)
    assert (out[0].start_ms, out[0].end_ms) == (2000, 2060)


def test_ctc_aligner_falls_back_to_asr_times(tmp_path: Path) -> None:
    wav = tmp_path / "c.wav"
    _write_wav(wav, {}, 30)
    words = [Word(text="juda uzun soʻzlar ketma-ketligi", start_ms=0, end_ms=500)]
    # kadrlar soni tokenlardan kam -> tekislab bo'lmaydi -> ASR vaqtlari qoladi
    out = _aligner(frames_div=8)(words, wav)
    assert out == words


def test_unaligned_word_kept_between_neighbours(tmp_path: Path) -> None:
    frames: dict[int, int] = {}
    _speak(frames, 20, "ab")
    frames[25] = VOCAB["|"]
    _speak(frames, 40, "cd")
    wav = tmp_path / "d.wav"
    _write_wav(wav, frames, 80)
    words = [Word(text="ab", start_ms=300, end_ms=500), Word(text="2024", start_ms=450, end_ms=700),
             Word(text="cd", start_ms=750, end_ms=900)]
    out = _aligner()(words, wav)
    assert (out[0].start_ms, out[2].start_ms) == (400, 800)
    assert out[0].end_ms <= out[1].start_ms < out[1].end_ms <= out[2].start_ms


def test_group_words_respects_30s_and_sentences() -> None:
    words = [Word(text=f"w{i}" + ("." if i % 5 == 4 else ""), start_ms=i * 1000, end_ms=i * 1000 + 800)
             for i in range(100)]
    chunks = group_words(words)
    assert sum(len(c) for c in chunks) == 100
    for c in chunks:
        assert words[c[-1]].end_ms - words[c[0]].start_ms <= 29_600
        assert words[c[-1]].text.endswith(".")  # gap chegarasida bo'linadi


def test_stage_align_uses_services_aligner(tmp_path: Path) -> None:
    words = [Word(text="a", start_ms=0, end_ms=100)]

    class Al:
        method = "ctc"

        def __call__(self, ws, wav):
            assert isinstance(wav, Path)
            return [w.model_copy(update={"start_ms": 10}) for w in ws]

    def ctx(svc: Services) -> SimpleNamespace:
        return SimpleNamespace(services={"svc": svc},
                               results={"normalize": {"words": [w.model_dump() for w in words]},
                                        "ingest": {"wav": str(tmp_path / "x.wav")}})

    res = stage_align(ctx(Services(aligner=Al())))
    assert res["method"] == "ctc" and res["words"][0]["start_ms"] == 10
    res = stage_align(ctx(Services()))
    assert res["method"] == "asr-timestamps" and res["words"][0]["start_ms"] == 0


def test_stage_align_survives_aligner_error(tmp_path: Path) -> None:
    def boom(ws, wav):
        raise RuntimeError("x")

    c = SimpleNamespace(services={"svc": Services(aligner=boom)},
                        results={"normalize": {"words": [Word(text="a", start_ms=0, end_ms=1).model_dump()]},
                                 "ingest": {"wav": str(tmp_path / "x.wav")}})
    assert stage_align(c)["method"] == "asr-timestamps"
