"""ASR "ctc" vaqt rejimi: timestamp'siz dekodlash + taxminiy vaqt + CTC oynalari (aligner yo'q -> whisper)."""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from conftest import requires_ffmpeg
from test_ml_align import VOCAB, _aligner, _speak, _write_wav
from test_raw_montage_asr import create, raw_case  # noqa: F401 - pytest fixture

from lahza_engine.align.ctc_onnx import window_groups
from lahza_engine.asr import whisper_cpp
from lahza_engine.asr.base import AsrOptions, align_in_windows, resolve_timestamps, spread_words
from lahza_engine.asr.faster_whisper_backend import FasterWhisperBackend, segment_conf
from lahza_engine.core.analyze import analysis_stages, asr_timestamps, stage_align, stage_asr
from lahza_engine.core.runner import StageContext
from lahza_engine.core.services import Services
from lahza_engine.montage import raw_asr
from lahza_engine.types import Word


@pytest.fixture(autouse=True)
def _decode_stub(monkeypatch):
    """Model soxta: audio dekodi (LGPL ffmpeg, ADR-0015) bu yerda tekshirilmaydi."""
    from lahza_engine.asr import faster_whisper_backend as fwb

    monkeypatch.setattr(fwb, "decode_pcm_f32", lambda wav, sr=16000: np.zeros(sr, dtype=np.float32))


def _w(text: str, a: int = 0, b: int = 0, conf: float | None = None) -> Word:
    return Word(text=text, start_ms=a, end_ms=b, conf=conf)


# --- AsrOptions / rejim tanlash ---------------------------------------------------------------

def test_default_is_ctc_but_falls_back_to_whisper_without_aligner():
    assert AsrOptions().timestamps == "ctc"
    assert resolve_timestamps(AsrOptions(), object()).timestamps == "ctc"
    opts = AsrOptions(hotwords=["Lahza"], beam_size=3)
    fb = resolve_timestamps(opts, None)
    assert fb.timestamps == "whisper" and fb.hotwords == ["Lahza"] and fb.beam_size == 3
    assert opts.timestamps == "ctc"  # asl nusxa o'zgarmaydi
    assert resolve_timestamps(AsrOptions(timestamps="whisper"), object()).timestamps == "whisper"
    assert asr_timestamps(Services()) == "whisper"
    assert asr_timestamps(Services(aligner=object())) == "ctc"


def test_stage_versions_and_cache_params():
    stages = {s.name: s for s in analysis_stages(SimpleNamespace(highlight=SimpleNamespace(model_dump=dict)))}
    assert stages["asr"].version == 5 and stages["align"].version == 3
    with_al = SimpleNamespace(services={"svc": Services(aligner=object())})
    without = SimpleNamespace(services={"svc": Services()})
    # aligner o'rnatilsa/olib tashlansa ASR qayta ishlaydi (boshqa rejim - boshqa kesh kaliti)
    assert stages["asr"].params(with_al)["timestamps"] == "ctc"
    assert stages["asr"].params(without)["timestamps"] == "whisper"
    assert raw_asr.CACHE_VERSION == 4


# --- faster-whisper ---------------------------------------------------------------------------

def _fw(segments, seen):
    backend = object.__new__(FasterWhisperBackend)

    def transcribe(path, **kw):
        seen.update(kw)
        return iter(segments), None
    backend.model = SimpleNamespace(transcribe=transcribe)
    return backend


def test_faster_whisper_ctc_mode_decodes_without_timestamps():
    seen: dict = {}
    seg = SimpleNamespace(text=" Salom, ʻ dunyo ... 2026 ", start=0.0, end=2.0, avg_logprob=-0.2, words=None)
    words = _fw([seg], seen).transcribe_chunk(Path("t.wav"), 5000, AsrOptions())
    assert seen["without_timestamps"] is True and seen["word_timestamps"] is False
    assert [w.text for w in words] == ["Salom,", "dunyo", "2026"]
    assert words[0].start_ms == 5000 and words[-1].end_ms == 7000
    assert all(a.end_ms <= b.start_ms for a, b in zip(words, words[1:], strict=False))
    assert all(w.conf == pytest.approx(math.exp(-0.2)) for w in words)


def test_faster_whisper_whisper_mode_keeps_word_timestamps():
    seen: dict = {}
    seg = SimpleNamespace(words=[SimpleNamespace(word=" ha", start=0.1, end=0.3, probability=0.4)])
    words = _fw([seg], seen).transcribe_chunk(Path("t.wav"), 0, AsrOptions(timestamps="whisper"))
    assert seen["word_timestamps"] is True and seen["without_timestamps"] is False
    assert [(w.start_ms, w.end_ms, w.conf) for w in words] == [(100, 300, 0.4)]


def test_segment_conf_scale():
    assert segment_conf(0.0) == 1.0
    assert segment_conf(-0.5) == pytest.approx(math.exp(-0.5))
    assert segment_conf(None) is None and segment_conf(float("nan")) is None
    assert segment_conf(5.0) == 1.0


# --- whisper.cpp ------------------------------------------------------------------------------

def _cpp(monkeypatch, tmp_path, payload):
    seen: dict = {}

    class R:
        returncode = 0
        stderr = ""

    def fake_run(args, timeout=None):
        seen["args"] = [str(a) for a in args]
        out = Path(seen["args"][seen["args"].index("-of") + 1]).with_suffix(".json")
        out.write_text(json.dumps(payload), encoding="utf-8")
        return R()

    monkeypatch.setattr(whisper_cpp, "find_tool", lambda name: Path("/bin/whisper-cli"))
    monkeypatch.setattr(whisper_cpp, "run", fake_run)
    return whisper_cpp.WhisperCppBackend(tmp_path / "m.bin", "m"), seen


def test_whisper_cpp_ctc_mode_uses_no_timestamps(monkeypatch, tmp_path):
    from _api_helpers import write_wav

    wav = tmp_path / "a.wav"
    write_wav(wav, 3000)
    payload = {"transcription": [{"text": " Salom dunyo", "offsets": {"from": 0, "to": 0}},
                                 {"text": "[MUSIQA]"}, {"text": " yana bir ʻ"}]}
    be, seen = _cpp(monkeypatch, tmp_path, payload)
    words = be.transcribe_chunk(wav, 1000, AsrOptions())
    args = seen["args"]
    assert "-nt" in args and "-ml" not in args and "-sow" not in args and "-oj" in args
    assert [w.text for w in words] == ["Salom", "dunyo", "yana", "bir"]
    assert words[0].start_ms == 1000 and words[-1].end_ms == 4000
    be.transcribe_chunk(wav, 0, AsrOptions(timestamps="whisper"))
    args = seen["args"]
    assert "-nt" not in args and args[args.index("-ml") + 1] == "1" and "-sow" in args


def test_whisper_cpp_output_args():
    assert whisper_cpp.output_args(AsrOptions()) == ["-nt"]
    assert whisper_cpp.output_args(AsrOptions(timestamps="whisper")) == ["-ml", "1", "-sow"]


# --- taxminiy vaqt ----------------------------------------------------------------------------

def test_spread_words_skips_vad_silence():
    words = [_w("aaaa"), _w("bbbb"), _w("cccc"), _w("dddd")]
    # bo'lak 0..10 s, nutq: 1-3 s va 6-8 s (orada 3 s sukunat)
    out = spread_words(words, 0, 10_000, [(1000, 3000), (6000, 8000), (12_000, 13_000)])
    assert [(w.start_ms, w.end_ms) for w in out] == [(1000, 2000), (2000, 3000), (6000, 7000), (7000, 8000)]
    assert [w.text for w in out] == ["aaaa", "bbbb", "cccc", "dddd"]
    # nutq bo'lakka tushmasa - butun oraliq
    out = spread_words(words, 0, 4000, [(5000, 6000)])
    assert (out[0].start_ms, out[-1].end_ms) == (0, 4000)
    assert spread_words([], 0, 10) == []


def test_spread_words_overlapping_speech_and_monotonic():
    words = [_w("a" * k) for k in (1, 5, 2, 9, 3)]
    out = spread_words(words, 500, 9500, [(0, 2000), (1500, 4000), (7000, 9000)])
    assert out[0].start_ms >= 500 and out[-1].end_ms <= 9000
    for w in out:
        assert w.end_ms > w.start_ms
        assert not (4000 < w.start_ms < 7000)  # hech bir so'z sukunatda boshlanmaydi
    assert all(a.start_ms <= b.start_ms for a, b in zip(out, out[1:], strict=False))


# --- CTC oynalari -----------------------------------------------------------------------------

def test_window_groups_assigns_by_midpoint_and_merges():
    words = [_w("a", 100, 200), _w("b", 4900, 5300), _w("c", 5400, 5600), _w("d", 30_000, 30_100),
             _w("e", 21_000, 21_500)]
    words = sorted(words, key=lambda w: w.start_ms)
    wins = [(0, 5200), (5000, 9000), (12_000, 20_000), (20_500, 25_000), (29_000, 31_000)]
    groups = window_groups(words, wins, max_ms=15_000)
    idx = {words[i].text: g for g, (_, ids) in enumerate(groups) for i in ids}
    # kesishma (5000..5200) o'rtasidan bo'linadi: "b" (o'rtasi 5100) 1-oynada, "c" 2-oynada;
    # 1+2 oyna birlashadi (9 s <= 15 s), bo'sh 12-20 s oyna tashlanadi.
    assert groups[0][0] == (0, 9000) and idx["a"] == idx["b"] == idx["c"] == 0
    assert [g for g, _ in groups] == [(0, 9000), (20_500, 31_000)]
    assert sorted(i for _, ids in groups for i in ids) == list(range(len(words)))
    # oynadan tashqaridagi so'z eng yaqin oynaga
    g = window_groups([_w("x", 10_000, 10_200)], [(0, 9000), (15_000, 20_000)], max_ms=5000)
    assert g == [((0, 9000), [0])]
    assert window_groups([], wins, 15_000) == [] and window_groups(words, [], 15_000) == []


def test_ctc_aligner_windows_bound_approximate_error(tmp_path: Path):
    # Ikki ASR bo'lagi: 0-2 s ("salom", "dost") va 4-6 s ("bir"). Taxminiy vaqtlar ataylab noto'g'ri
    # (bo'lak bo'ylab tekis), lekin har so'z o'z oynasida qoladi va aniq vaqtga tekislanadi.
    frames: dict[int, int] = {}
    _speak(frames, 30, "salom")
    frames[45] = VOCAB["|"]
    _speak(frames, 60, "dost")
    _speak(frames, 250, "bir")
    wav = tmp_path / "w.wav"
    _write_wav(wav, frames, 300)
    windows = [(0, 2000), (4000, 6000)]
    words = [_w("Salom", 0, 1100, 0.9), _w("dost.", 1100, 2000, 0.9), _w("bir", 4000, 6000, 0.9)]
    out = _aligner()(words, wav, windows=windows)
    assert [(w.start_ms, w.end_ms) for w in out] == [(600, 700), (1200, 1280), (5000, 5060)]
    assert [w.text for w in out] == ["Salom", "dost.", "bir"]
    # oynalarsiz (eski yo'l) ham ishlaydi - shartnoma o'zgarmagan
    assert len(_aligner()(words, wav)) == 3


def test_align_in_windows_respects_aligner_signature(tmp_path: Path):
    words = [_w("a", 0, 10)]
    seen = {}

    def old(ws, wav):
        seen["old"] = True
        return ws

    def new(ws, wav, windows=None):
        seen["windows"] = windows
        return ws

    align_in_windows(old, words, tmp_path, [(0, 100)])
    align_in_windows(new, words, tmp_path, [[0, 100]])
    assert seen == {"old": True, "windows": [(0, 100)]}
    align_in_windows(new, words, tmp_path, None)
    assert seen["windows"] is None


# --- stage_asr / stage_align ------------------------------------------------------------------

def _wav16(path: Path, ms: int) -> None:
    import wave

    pcm = (0.1 * np.sin(np.arange(16 * ms) * 0.05) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm.tobytes())


class _Asr:
    def __init__(self):
        self.modes = []

    def transcribe_chunk(self, wav, offset_ms, opts):
        self.modes.append(opts.timestamps)
        # backend "whisper" rejimida aniq vaqt, "ctc" da bo'lak bo'ylab tekis (taxminiy)
        if opts.timestamps == "whisper":
            return [_w("salom", offset_ms + 100, offset_ms + 300, 0.8)]
        return [_w("salom", offset_ms, offset_ms + 4000, 0.9), _w("dunyo", offset_ms + 4000, offset_ms + 8000, 0.9)]


@requires_ffmpeg
@pytest.mark.parametrize("aligner", [None, "fake"])
def test_stage_asr_mode_follows_aligner(tmp_path, aligner):
    src = tmp_path / "audio16k.wav"
    _wav16(src, 8000)
    asr = _Asr()
    svc = Services(asr=asr, aligner=(lambda ws, wav: ws) if aligner else None)
    ctx = StageContext("m", "h", tmp_path, sqlite3.connect(":memory:"),
                       results={"ingest": {"wav": str(src)}, "vad": {"speech": [(1000, 2500), (5000, 6500)]}},
                       services={"svc": svc, "progress": lambda f: None})
    out = stage_asr(ctx)
    if aligner is None:
        assert asr.modes == ["whisper"] and out["timestamps"] == "whisper" and "windows" not in out
        assert [(w["start_ms"], w["end_ms"]) for w in out["words"]] == [(900, 1100)]
        return
    assert asr.modes == ["ctc"] and out["timestamps"] == "ctc"
    assert out["windows"] == [[800, 6700]]
    # taxminiy vaqtlar VAD nutq qismlariga tushadi (sukunatda emas)
    (a, b) = (out["words"][0], out["words"][1])
    assert a["start_ms"] == 1000 and a["end_ms"] == 2500 and b["start_ms"] == 5000 and b["end_ms"] == 6500
    # stage_align oynalarni aligner'ga uzatadi
    got = {}

    class Al:
        method = "ctc"

        def __call__(self, ws, wav, windows=None):
            got["windows"] = windows
            return ws

    ctx.results["asr"] = out
    ctx.results["normalize"] = {"words": out["words"]}
    ctx.services["svc"] = Services(asr=asr, aligner=Al())
    assert stage_align(ctx)["method"] == "ctc" and got["windows"] == [(800, 6700)]

    def boom(ws, wav, windows=None):
        raise RuntimeError("x")

    ctx.services["svc"] = Services(asr=asr, aligner=boom)
    assert stage_align(ctx)["method"] == "asr-approx"
    ctx.services["svc"] = Services(asr=asr)
    assert stage_align(ctx)["method"] == "asr-approx"


# --- raw montage ASR --------------------------------------------------------------------------

class _RawAsr:
    def __init__(self, model_id):
        self.model_id = model_id
        self.modes = []

    def transcribe_chunk(self, wav, offset_ms, opts):
        self.modes.append(opts.timestamps)
        return [_w("Salom", offset_ms + 300, offset_ms + 600), _w("dunyo.", offset_ms + 700, offset_ms + 1000)]


@requires_ffmpeg
@pytest.mark.parametrize("case", ["no-aligner", "aligner", "aligner-fails"])
def test_raw_asr_timestamps_follow_aligner(raw_case, case):  # noqa: F811
    client, state, _, path, _ = raw_case
    backend = _RawAsr("fake:asr")
    calls = []

    def aligner(ws, wav, windows=None):
        calls.append(windows)
        if case == "aligner-fails":
            raise RuntimeError("onnx")
        return [w.model_copy(update={"start_ms": 1000 + 1000 * i, "end_ms": 1500 + 1000 * i})
                for i, w in enumerate(ws)]

    state._services = Services(asr=backend, asr_model_id="fake:asr", vad=lambda pcm, rate: [(0, 6000)],
                               aligner=None if case == "no-aligner" else aligner)
    with client:
        _, _, timeline = create(client, state, path)
    words = timeline.captions.words
    assert [w.text for w in words] == ["Salom", "dunyo."]
    if case == "no-aligner":
        assert backend.modes == ["whisper"] and not calls
    elif case == "aligner":
        assert backend.modes == ["ctc"] and calls == [[(0, 6200)]]
    else:  # CTC xatosi -> whisper so'z vaqtlari bilan qayta transkripsiya
        assert backend.modes == ["ctc", "whisper"] and len(calls) == 1


def test_word_conf_combines_segment_and_ctc(tmp_path: Path):
    from lahza_engine.align.ctc_onnx import word_conf

    assert word_conf(0.9, 0.5) == pytest.approx(0.45)
    assert word_conf(None, 0.7) == pytest.approx(0.7)
    assert word_conf(1.5, 2.0) == 1.0 and word_conf(0.8, -1) == 0.0
    # oynali rejimda conf CTC bilan yangilanadi, oddiy rejimda ASR conf saqlanadi
    frames: dict[int, int] = {}
    _speak(frames, 30, "bir")
    wav = tmp_path / "c.wav"
    _write_wav(wav, frames, 100)
    words = [_w("bir", 0, 2000, 0.8)]
    windowed = _aligner()(words, wav, windows=[(0, 2000)])[0].conf
    assert windowed is not None and 0 < windowed <= 0.8
    assert _aligner()(words, wav)[0].conf == 0.8
