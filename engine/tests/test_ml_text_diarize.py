from pathlib import Path

from lahza_engine.asr.base import AsrOptions, hotword_prompt
from lahza_engine.diarize.assign import Turn, assign_speakers, find_overlaps, normalize_labels
from lahza_engine.text.punctuation import is_question, needs_restoration, restore_punctuation
from lahza_engine.types import Word


def _w(text: str, a: int, b: int) -> Word:
    return Word(text=text, start_ms=a, end_ms=b)


# --- tinish belgisi (M1-ASR-2) ------------------------------------------------------------------

def test_needs_restoration() -> None:
    assert needs_restoration([_w("salom", 0, 1), _w("dunyo", 1, 2)])
    assert not needs_restoration([_w("salom", 0, 1), _w("dunyo.", 1, 2)])
    assert not needs_restoration([_w("Salom", 0, 1), _w("Dunyo", 1, 2)])
    assert not needs_restoration([])


def test_restore_punctuation_pauses_questions_and_caps() -> None:
    words = [
        _w("bugun", 0, 300), _w("havo", 350, 600), _w("yaxshi", 650, 900),
        _w("siz", 1700, 1900), _w("qachon", 1950, 2200), _w("kelasiz", 2250, 2600),
        _w("tayyormisiz", 3500, 4000),
        _w("oʻzbekiston", 5000, 5600), _w("goʻzal", 5650, 6000),
    ]
    out = restore_punctuation(words)
    assert [w.text for w in out] == [
        "Bugun", "havo", "yaxshi.", "Siz", "qachon", "kelasiz?", "Tayyormisiz?",
        "Oʻzbekiston", "goʻzal.",
    ]
    assert [(w.start_ms, w.end_ms) for w in out] == [(w.start_ms, w.end_ms) for w in words]


def test_restore_punctuation_noop_when_model_punctuates() -> None:
    words = [_w("Salom.", 0, 300), _w("Qalaysiz?", 1500, 1800)]
    assert restore_punctuation(words) == words


def test_is_question_exceptions() -> None:
    assert is_question(["bu", "toʻgʻrimi"])
    assert not is_question(["uning", "nomi"])
    assert not is_question(["men", "keldim"])
    assert is_question(["nega", "kech", "qolding"])


# --- diarizatsiya (M1-DIA-1) ---------------------------------------------------------------------

def test_normalize_labels_by_first_appearance() -> None:
    turns = [Turn(5000, 6000, "SPEAKER_00"), Turn(0, 1000, "SPEAKER_03"), Turn(2000, 3000, "SPEAKER_00")]
    out = normalize_labels(turns)
    assert [(t.start_ms, t.speaker) for t in out] == [(0, "S1"), (2000, "S2"), (5000, "S2")]
    m: dict[str, str] = {}
    normalize_labels(turns, m)
    assert normalize_labels([Turn(0, 1, "SPEAKER_00")], m)[0].speaker == "S2"


def test_find_overlaps() -> None:
    turns = [Turn(0, 3000, "S1"), Turn(2500, 5000, "S2"), Turn(2800, 3500, "S1"),
             Turn(5000, 6000, "S1"), Turn(7000, 7050, "S2"), Turn(7000, 8000, "S1")]
    # 2500..3500 (S1 ikki turn'i qo'shilib ketadi); 5000 da chegaradosh - overlap emas; 50 ms < 100
    assert find_overlaps(turns) == [(2500, 3500)]
    assert find_overlaps([Turn(0, 1000, "S1"), Turn(500, 900, "S1")]) == []


def test_assign_speakers_with_normalized_labels() -> None:
    turns = normalize_labels([Turn(0, 1000, "B"), Turn(1000, 2000, "A")])
    words = assign_speakers([_w("a", 100, 400), _w("b", 1200, 1500)], turns)
    assert [w.speaker for w in words] == ["S1", "S2"]


def test_stage_diarize_fallback_and_overlaps(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from lahza_engine.core.analyze import stage_diarize
    from lahza_engine.core.services import Services

    words = [_w("a", 100, 400).model_dump(), _w("b", 1200, 1500).model_dump()]

    def ctx(diarizer) -> SimpleNamespace:
        return SimpleNamespace(services={"svc": Services(diarizer=diarizer)},
                               results={"align": {"words": words}, "ingest": {"wav": str(tmp_path / "x.wav")}})

    def plain(wav, n):
        return [Turn(0, 1100, "spk_b"), Turn(900, 2000, "spk_a")]

    res = stage_diarize(ctx(plain))
    assert [t["speaker"] for t in res["turns"]] == ["S1", "S2"]
    assert res["overlaps"] == [[900, 1100]]
    assert [w["speaker"] for w in res["words"]] == ["S1", "S2"]

    def broken(wav, n):
        raise RuntimeError("model yo'q")

    res = stage_diarize(ctx(broken))
    assert res["method"] == "none" and res["overlaps"] == []


# --- hotwords (M1-ASR-1) -------------------------------------------------------------------------

def test_hotword_prompt_dedupes_and_truncates() -> None:
    assert hotword_prompt([]) is None
    assert hotword_prompt(["Lahza", " lahza ", "Toshkent  shahri", ""]) == "Lahza, Toshkent shahri"
    long = hotword_prompt([f"soʻz{i}" for i in range(500)], max_chars=100)
    assert long is not None and len(long) <= 100


def test_whisper_cpp_passes_prompt(monkeypatch, tmp_path: Path) -> None:
    import json

    from lahza_engine.asr import whisper_cpp

    seen: dict = {}

    class R:
        returncode = 0
        stderr = ""

    def fake_run(args, timeout=None):
        seen["args"] = [str(a) for a in args]
        out = Path(seen["args"][seen["args"].index("-of") + 1]).with_suffix(".json")
        out.write_text(json.dumps({"transcription": []}), encoding="utf-8")
        return R()

    monkeypatch.setattr(whisper_cpp, "find_tool", lambda name: Path("/bin/whisper-cli"))
    monkeypatch.setattr(whisper_cpp, "run", fake_run)
    be = whisper_cpp.WhisperCppBackend(tmp_path / "m.bin", "m")
    be.transcribe_chunk(tmp_path / "a.wav", 0, AsrOptions(hotwords=["Lahza", "Toshkent"]))
    args = seen["args"]
    assert args[args.index("--prompt") + 1] == "Lahza, Toshkent"
    be.transcribe_chunk(tmp_path / "a.wav", 0, AsrOptions())
    assert "--prompt" not in seen["args"]


def test_faster_whisper_passes_hotwords() -> None:
    from lahza_engine.asr.faster_whisper_backend import FasterWhisperBackend

    calls: list[dict] = []

    class Model:
        def transcribe(self, wav, language, word_timestamps, condition_on_previous_text, vad_filter,
                       hotwords=None, compression_ratio_threshold=2.4, log_prob_threshold=-1.0,
                       no_speech_threshold=0.6):
            assert (compression_ratio_threshold, log_prob_threshold, no_speech_threshold) == (2.4, -1.0, 0.6)
            calls.append({"hotwords": hotwords, "cond": condition_on_previous_text})
            return iter([]), None

    class OldModel:
        def transcribe(self, wav, language, word_timestamps, condition_on_previous_text, vad_filter,
                       initial_prompt=None, compression_ratio_threshold=2.4, log_prob_threshold=-1.0,
                       no_speech_threshold=0.6):
            calls.append({"initial_prompt": initial_prompt})
            return iter([]), None

    be = FasterWhisperBackend.__new__(FasterWhisperBackend)
    be.model, be.model_id = Model(), "m"
    be.transcribe_chunk(Path("a.wav"), 0, AsrOptions(hotwords=["Lahza"]))
    assert calls[-1] == {"hotwords": "Lahza", "cond": False}
    be.model = OldModel()
    be.transcribe_chunk(Path("a.wav"), 0, AsrOptions(hotwords=["Lahza"]))
    assert calls[-1] == {"initial_prompt": "Lahza"}


def test_stage_normalize_restores_punctuation() -> None:
    from types import SimpleNamespace

    from lahza_engine.core.analyze import stage_normalize

    words = [_w("salom", 0, 300), _w("doʼstlar", 350, 700), _w("qalaysiz", 1600, 2000)]
    ctx = SimpleNamespace(services={}, results={"asr": {"words": [w.model_dump() for w in words]}})
    res = stage_normalize(ctx)
    assert res["punctuation"] == "restored"
    assert [w["text"] for w in res["words"]] == ["Salom", "doʻstlar.", "Qalaysiz."]


def test_stage_vad_falls_back_to_energy(tmp_path: Path) -> None:
    import wave
    from types import SimpleNamespace

    import numpy as np

    from lahza_engine.core.analyze import stage_vad
    from lahza_engine.core.services import Services

    wav = tmp_path / "a.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(np.zeros(16000, dtype="<i2").tobytes())

    def broken(pcm, sr):
        raise RuntimeError("onnx")

    ctx = SimpleNamespace(services={"svc": Services(vad=broken)}, results={"ingest": {"wav": str(wav)}})
    assert stage_vad(ctx)["method"] == "energy"
