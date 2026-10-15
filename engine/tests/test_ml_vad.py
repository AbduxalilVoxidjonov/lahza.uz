import numpy as np
import pytest

from lahza_engine.vad.silero_onnx import SileroOnnxVad, probs_to_segments


class _Inp:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeSileroSession:
    """Silero v5 interfeysini taqlid qiladi: ehtimollik = oynadagi amplituda bo'yicha."""

    def __init__(self) -> None:
        self.calls = 0
        self.shapes: list[tuple[int, ...]] = []

    def get_inputs(self):
        return [_Inp("input"), _Inp("state"), _Inp("sr")]

    def run(self, _outs, feeds):
        self.calls += 1
        x, state = feeds["input"], feeds["state"]
        assert state.shape == (2, 1, 128) and feeds["sr"].dtype == np.int64
        self.shapes.append(x.shape)
        p = 0.9 if np.abs(x[0, 64:]).mean() > 0.05 else 0.05
        return np.array([[p]], dtype=np.float32), state + 1


def test_probs_to_segments_hysteresis_and_min_silence() -> None:
    win, sr = 512, 16000  # 32 ms oyna
    probs = [0.0] * 10 + [0.9] * 20 + [0.4] * 3 + [0.9] * 10 + [0.1] * 20
    # 0.4 > neg (0.35) - nutq uzilmaydi; oxirgi sukut >= 100 ms -> bitta oraliq
    segs = probs_to_segments(probs, win, len(probs) * win, sr)
    assert len(segs) == 1
    a, b = segs[0]
    assert a == pytest.approx(10 * 32 - 30, abs=1)
    assert b == pytest.approx(43 * 32 + 30, abs=1)


def test_probs_to_segments_splits_on_silence_and_drops_short() -> None:
    win, sr = 512, 16000
    probs = [0.9] * 20 + [0.1] * 10 + [0.9] * 20 + [0.1] * 10 + [0.9] * 5 + [0.0] * 10
    segs = probs_to_segments(probs, win, len(probs) * win, sr)
    # oxirgi 5 oyna (160 ms) < 250 ms -> tashlanadi
    assert len(segs) == 2
    assert segs[0][0] == 0
    assert segs[0][1] < segs[1][0]


def test_short_silence_does_not_split() -> None:
    win, sr = 512, 16000
    probs = [0.9] * 20 + [0.1] * 2 + [0.9] * 20 + [0.0] * 10  # 64 ms < 100 ms
    assert len(probs_to_segments(probs, win, len(probs) * win, sr)) == 1


def test_silero_onnx_vad_with_fake_session() -> None:
    sr = 16000
    pcm = np.zeros(sr * 3, dtype=np.float32)
    pcm[sr : 2 * sr] = 0.3 * np.sin(np.arange(sr) * 0.1)
    sess = FakeSileroSession()
    vad = SileroOnnxVad(session=sess)
    segs = vad(pcm, sr)
    assert sess.calls == int(np.ceil(len(pcm) / 512))
    assert all(s == (1, 576) for s in sess.shapes)  # 64 kontekst + 512 oyna
    assert len(segs) == 1
    a, b = segs[0]
    assert 900 <= a <= 1000 and 2000 <= b <= 2100


def test_silero_onnx_rejects_old_interface() -> None:
    class Old(FakeSileroSession):
        def get_inputs(self):
            return [_Inp("input"), _Inp("h"), _Inp("c"), _Inp("sr")]

    with pytest.raises(ValueError):
        SileroOnnxVad(session=Old())


def test_silero_onnx_resamples_unknown_rate() -> None:
    sr = 44100
    pcm = np.zeros(sr * 2, dtype=np.float32)
    pcm[sr // 2 : sr + sr // 2] = 0.3
    segs = SileroOnnxVad(session=FakeSileroSession())(pcm, sr)
    assert len(segs) == 1 and 400 <= segs[0][0] <= 520
