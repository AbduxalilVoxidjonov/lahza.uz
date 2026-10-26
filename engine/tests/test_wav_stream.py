"""V1-1 xotira: oqimli WAV o'qish (`open_wav_mono`/`WavPcm`) eski `read_wav_mono` bilan bir xil."""

from __future__ import annotations

import struct
import wave
from pathlib import Path

import numpy as np
import pytest

from lahza_engine.asr.base import plan_chunks
from lahza_engine.highlight.signals import compute_signals, loudness_db
from lahza_engine.media.probe import MediaError, WavPcm, frame_power, open_wav_mono, read_wav_mono
from lahza_engine.types import Sentence, Word
from lahza_engine.vad.energy import energy_vad, vad_input
from lahza_engine.vad.silero_onnx import SileroOnnxVad

SR = 16_000


def _speechy(n: int, ch: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    env = np.repeat((np.sin(np.arange(n) / 9000.0) > 0.2).astype(np.float64), ch)
    x = rng.standard_normal(n * ch) * (300 + 6000 * env)
    return np.clip(x, -32768, 32767).astype("<i2")


def _write(path: Path, data: np.ndarray, ch: int = 1, rate: int = SR) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.tobytes())
    return path


@pytest.fixture(params=[1, 2])
def wav(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    ch = request.param
    n = SR * 75 + 777  # bir nechta blok + to'liq bo'lmagan oxir
    return _write(tmp_path / f"a{ch}.wav", _speechy(n, ch), ch)


def test_full_read_identical(wav: Path) -> None:
    old, r1 = read_wav_mono(wav)
    pcm, r2 = open_wav_mono(wav)
    assert r1 == r2 == SR and len(pcm) == len(old)
    assert np.array_equal(np.asarray(pcm), old)


def test_ranges_and_block_edges(wav: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old, _ = read_wav_mono(wav)
    pcm = WavPcm(wav)
    n = len(old)
    for a, b in [(0, 1), (0, 0), (5, 5), (12345, 54321), (n - 10, n), (n - 10, n + 500),
                 (-100, 50), (n + 5, n + 10), (1 << 20, (1 << 20) + 3)]:
        assert np.array_equal(pcm[a:b], old[a:b]), (a, b)
    assert pcm[7] == old[7] and pcm[-1] == old[-1]
    assert np.array_equal(pcm[10:1000:7], old[10:1000:7])
    with pytest.raises(IndexError):
        pcm[n]
    # bloklar butun audioni bo'shliqsiz, ustma-ust tushmasdan qoplaydi
    got = np.concatenate([blk for _, blk in pcm.blocks(block=SR * 7 + 3, align=480)])
    assert np.array_equal(got, old)
    starts = [a for a, _ in pcm.blocks(block=SR * 7 + 3, align=480)]
    assert all(s % 480 == 0 for s in starts)


@pytest.mark.parametrize("hop", [1, 480, 1600, SR * 3 + 1])
def test_frame_power_matches_full(wav: Path, hop: int) -> None:
    old, _ = read_wav_mono(wav)
    n = len(old) // hop
    want = np.mean(old[: n * hop].reshape(n, hop) ** 2, axis=1)
    for block in (hop, hop * 3 + 1, 1 << 20):
        assert np.array_equal(frame_power(WavPcm(wav), hop, block=block), want)
        assert np.array_equal(frame_power(old, hop, block=block), want)


def test_frame_power_keeps_dtype_and_empty() -> None:
    x = np.linspace(-1, 1, 1000)
    assert frame_power(x, 100).dtype == np.float64
    assert frame_power(x, 100, np.float32).dtype == np.float32
    assert len(frame_power(x[:50], 100)) == 0


def test_consumers_identical(wav: Path) -> None:
    old, _ = read_wav_mono(wav)
    pcm, _ = open_wav_mono(wav)
    assert energy_vad(pcm, SR) == energy_vad(old, SR)
    assert np.array_equal(loudness_db(pcm, SR), loudness_db(old, SR))
    speech = [(0, 70_000)]  # uzun nutq -> jim nuqtalarda kesiladi
    assert plan_chunks(speech, pcm=pcm, sample_rate=SR) == plan_chunks(speech, pcm=old, sample_rate=SR)
    words = [Word(text="a", start_ms=1000, end_ms=1500), Word(text="b?", start_ms=1600, end_ms=2000)]
    sents = [Sentence(id=1, start_ms=1000, end_ms=1500, words=words[:1]),
             Sentence(id=2, start_ms=1600, end_ms=2000, words=words[1:])]
    a = compute_signals(sents, pcm, SR).sentences
    b = compute_signals(sents, old, SR).sentences
    assert [s.__dict__ for s in a] == [s.__dict__ for s in b]


class _FakeSession:
    """Silero v5 interfeysi: ehtimol = kontekst+oyna o'rtacha kvadrati (deterministik)."""

    class _In:
        def __init__(self, name: str) -> None:
            self.name = name

    def get_inputs(self) -> list:
        return [self._In("input"), self._In("state"), self._In("sr")]

    def run(self, _out, feed: dict) -> tuple:
        x = feed["input"]
        return np.array([[min(1.0, float(np.mean(x**2)) * 40)]], dtype=np.float32), feed["state"]


def test_silero_streams_wavpcm(wav: Path) -> None:
    old, _ = read_wav_mono(wav)
    pcm, _ = open_wav_mono(wav)
    vad = SileroOnnxVad(session=_FakeSession())
    assert vad_input(vad, pcm) is pcm  # oqimli VAD butun massivni talab qilmaydi
    assert np.array_equal(vad.probabilities(pcm, SR), vad.probabilities(old, SR))
    assert vad(pcm, SR) == vad(old, SR)
    assert isinstance(vad_input(lambda p, s: [], pcm), np.ndarray)


def test_streamed_header_sizes(tmp_path: Path) -> None:
    """ffmpeg oqimda yozganda data o'lchami 0/0xFFFFFFFF bo'lishi mumkin - fayl oxirigacha o'qiladi."""
    data = _speechy(SR, 1)
    p = _write(tmp_path / "s.wav", data)
    raw = bytearray(p.read_bytes())
    i = raw.index(b"data")
    raw[i + 4:i + 8] = struct.pack("<I", 0xFFFFFFFF)
    q = tmp_path / "q.wav"
    q.write_bytes(bytes(raw) + b"\x01")  # toq bayt: to'liq bo'lmagan namuna tashlanadi
    pcm = WavPcm(q)
    assert len(pcm) == SR
    assert np.array_equal(np.asarray(pcm), data.astype(np.float32) / 32768.0)


def test_rejects_non_pcm16(tmp_path: Path) -> None:
    p = tmp_path / "x.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(SR)
        w.writeframes(b"\x80" * 100)
    with pytest.raises(MediaError):
        WavPcm(p)
    (tmp_path / "y.wav").write_bytes(b"not a wav at all")
    with pytest.raises(MediaError):
        WavPcm(tmp_path / "y.wav")
