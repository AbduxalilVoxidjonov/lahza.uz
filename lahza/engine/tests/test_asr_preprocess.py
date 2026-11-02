import wave
from pathlib import Path

import numpy as np
import pytest

from lahza_engine.asr.preprocess import (
    MAX_GAIN_DB,
    PEAK_CEILING_DBFS,
    TARGET_RMS_DBFS,
    normalization_gain,
    normalize_pcm,
    normalize_wav_file,
)

SR = 16_000


def _db(x):
    return 20 * np.log10(x)


def _rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))


def _tone(amp, secs=1.0):
    t = np.arange(int(SR * secs)) / SR
    return (amp * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def test_quiet_speech_raised_to_target_rms():
    x = _tone(10 ** (-35 / 20) * np.sqrt(2))  # RMS -35 dBFS
    y = normalize_pcm(x, SR)
    assert _db(_rms(y)) == pytest.approx(TARGET_RMS_DBFS, abs=0.2)
    assert y.dtype == np.float32


def test_normal_and_loud_audio_untouched():
    for amp in (0.9, 10 ** ((TARGET_RMS_DBFS + 2) / 20) * np.sqrt(2)):
        x = _tone(amp)
        assert normalization_gain(x, SR) == 1.0
        np.testing.assert_array_equal(normalize_pcm(x, SR), x)


def test_peak_ceiling_limits_gain():
    x = _tone(0.01)
    x[100] = 0.5  # bitta cho'qqi: RMS bo'yicha gain uni -1 dBFS dan oshirib yuborardi
    y = normalize_pcm(x, SR)
    assert np.max(np.abs(y)) <= 10 ** (PEAK_CEILING_DBFS / 20) + 1e-6


def test_gain_capped_for_very_quiet_input():
    x = _tone(10 ** (-49 / 20) * np.sqrt(2))  # -49 dBFS RMS: 23 dB kerak, 20 dB ruxsat
    assert _db(normalization_gain(x, SR)) == pytest.approx(MAX_GAIN_DB, abs=0.01)


def test_silence_and_noise_floor_not_amplified():
    assert normalization_gain(np.zeros(SR, np.float32), SR) == 1.0
    noise = (np.random.default_rng(0).standard_normal(SR) * 10 ** (-65 / 20)).astype(np.float32)
    assert normalization_gain(noise, SR) == 1.0
    assert normalization_gain(np.zeros(0, np.float32), SR) == 1.0


def test_silent_frames_do_not_drag_rms_down():
    # 0.5 s nutq -36 dBFS + 1.5 s sukut: gain faqat nutq bo'yicha (target+36), +6 dB ko'p emas.
    x = np.concatenate([_tone(10 ** (-36 / 20) * np.sqrt(2), 0.5), np.zeros(int(SR * 1.5), np.float32)])
    assert _db(normalization_gain(x, SR)) == pytest.approx(TARGET_RMS_DBFS + 36, abs=0.3)


def _write(path: Path, pcm: np.ndarray, ch: int = 1):
    data = np.clip(np.round(pcm * 32768), -32768, 32767).astype("<i2")
    if ch > 1:
        data = np.repeat(data, ch)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def _read(path: Path):
    with wave.open(str(path), "rb") as w:
        assert w.getnchannels() == 1 and w.getframerate() == SR and w.getsampwidth() == 2
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768


@pytest.mark.parametrize("ch", [1, 2])
def test_normalize_wav_file_in_place(tmp_path, ch):
    p = tmp_path / "c.wav"
    _write(p, _tone(0.02), ch)  # RMS ~ -37 dBFS
    gain = normalize_wav_file(p)
    assert gain > 1
    y = _read(p)
    assert len(y) == SR
    assert _db(_rms(y)) == pytest.approx(TARGET_RMS_DBFS, abs=0.3)


def test_normalize_wav_file_leaves_silence_untouched(tmp_path):
    p = tmp_path / "s.wav"
    _write(p, np.zeros(SR, np.float32))
    before = p.read_bytes()
    assert normalize_wav_file(p) == 1.0
    assert p.read_bytes() == before


def test_stage_asr_feeds_normalized_chunks(tmp_path):
    import sqlite3
    from types import SimpleNamespace

    from lahza_engine.core.analyze import analysis_stages, stage_asr
    from lahza_engine.core.runner import StageContext
    from lahza_engine.media.probe import read_wav_mono
    from lahza_engine.types import Word

    src = tmp_path / "audio16k.wav"
    _write(src, np.concatenate([np.zeros(SR // 2, np.float32), _tone(0.02, 2.0)]))  # ~ -37 dBFS
    levels = []

    class Asr:
        def transcribe_chunk(self, wav, offset_ms, opts):
            pcm, _ = read_wav_mono(wav)
            levels.append(_db(_rms(pcm[pcm != 0])))
            assert opts.temperature == 0.0 and opts.beam_size == 5
            return [Word(text="salom", start_ms=offset_ms, end_ms=offset_ms + 400)]

    ctx = StageContext("m", "h", tmp_path, sqlite3.connect(":memory:"),
                       results={"ingest": {"wav": str(src)}, "vad": {"speech": [(500, 2500)]}},
                       services={"svc": SimpleNamespace(asr=Asr()), "progress": lambda f: None})
    out = stage_asr(ctx)
    assert out["chunks"] == 1 and levels
    assert levels[0] == pytest.approx(TARGET_RMS_DBFS, abs=0.5)  # -37 dBFS bo'lak ko'tariladi
    versions = {s.name: s.version for s in analysis_stages(SimpleNamespace(highlight=SimpleNamespace()))}
    assert versions["asr"] >= 4 and versions["vad"] >= 3
