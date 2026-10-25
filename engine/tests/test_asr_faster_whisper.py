from pathlib import Path
from types import SimpleNamespace

import pytest

from lahza_engine.asr.base import AsrOptions
from lahza_engine.asr.faster_whisper_backend import FasterWhisperBackend


def test_punctuation_hallucinations_filtered_without_losing_uzbek():
    backend = object.__new__(FasterWhisperBackend)
    inputs = ["'", "ʻ", "ʼ", "’", "...", "?!", "—", " ", "oʻzbek", "gʻoya,", "2026", "Ўзбекистон"]
    def transcribe(path, **kw):
        assert kw["language"] == "uz"
        assert kw["compression_ratio_threshold"] == 2.4
        assert kw["log_prob_threshold"] == -1.0
        assert kw["no_speech_threshold"] == 0.6
        assert kw["condition_on_previous_text"] is False
        assert kw["word_timestamps"] is True
        words = [SimpleNamespace(word=w, start=i, end=i + .5, probability=.9)
                 for i, w in enumerate(inputs)]
        return iter([SimpleNamespace(words=words)]), None
    backend.model = SimpleNamespace(transcribe=transcribe)
    words = backend.transcribe_chunk(Path("test.wav"), 2000, AsrOptions())
    assert [w.text for w in words] == ["oʻzbek", "gʻoya,", "2026", "Ўзбекистон"]
    assert words[0].start_ms == 10000
    assert words[0].end_ms == 10500
    assert words[0].conf == .9


def test_backend_load_is_local_only(monkeypatch, tmp_path):
    import sys
    def load(path, **kw):
        assert path == str(tmp_path)
        assert kw == {"device": "cpu", "compute_type": "int8", "local_files_only": True}
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=load))
    FasterWhisperBackend(tmp_path, "test", device="cpu")


@pytest.mark.parametrize("message", [
    "decoder failure", "Model.transcribe_hotwords() got an unexpected keyword argument 'other'",
])
def test_unrelated_type_error_is_not_retried(message):
    backend = object.__new__(FasterWhisperBackend)
    calls = []
    def broken(*args, **kw):
        calls.append(kw)
        raise TypeError(message)
    backend.model = SimpleNamespace(transcribe=broken)
    with pytest.raises(TypeError) as caught:
        backend.transcribe_chunk(Path("test.wav"), 0, AsrOptions())
    assert str(caught.value) == message
    assert len(calls) == 1
