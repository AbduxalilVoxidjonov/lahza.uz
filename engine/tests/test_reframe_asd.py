"""R0-VIS-2: LR-ASD ONNX backend - soxta sessiyalar, oldindan ishlov berish, model yo'q fallback."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from lahza_engine.models.catalog import Catalog, Task
from lahza_engine.reframe.asd import (
    ASD_MFCC_PER_FRAME,
    LrAsdOnnx,
    face_crop,
    find_asd_files,
    load_asd_backend,
    load_asd_from_store,
    mfcc,
    score_track,
    scores_at,
    to_probability,
)
from lahza_engine.reframe.faces import Box

ROOT = Path(__file__).resolve().parents[2]


class _In(SimpleNamespace):
    pass


class FakeCombined:
    """Birlashgan LR-ASD: kirish (audio [1,4T,13], vizual [1,T,112,112]) -> logit [T, 2].

    "Gapiryapti" = yuz kesimi o'rtacha yorqinligi > 128.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_inputs(self):  # noqa: ANN201
        return [_In(name="input_a", shape=[1, "T4", 13]), _In(name="input_v", shape=[1, "T", 112, 112])]

    def run(self, _out, feeds):  # noqa: ANN001, ANN201
        self.calls.append({k: v.shape for k, v in feeds.items()})
        a, v = feeds["input_a"], feeds["input_v"]
        assert a.shape[1] == v.shape[1] * ASD_MFCC_PER_FRAME
        speak = v[0].mean(axis=(1, 2)) > 128
        logits = np.stack([np.where(speak, -3.0, 3.0), np.where(speak, 3.0, -3.0)], axis=1)
        return [logits]


class FakeFront:
    def __init__(self, name: str, kind: str) -> None:
        self.name, self.kind = name, kind

    def get_inputs(self):  # noqa: ANN201
        return [_In(name=self.name, shape=None)]

    def run(self, _out, feeds):  # noqa: ANN001, ANN201
        x = feeds[self.name]
        if self.kind == "audio":
            return [x.reshape(1, -1, ASD_MFCC_PER_FRAME * 13)[:, :, :8]]
        return [x.mean(axis=(2, 3))[..., None].repeat(8, axis=-1)]


class FakeBackend:
    def get_inputs(self):  # noqa: ANN201
        return [_In(name="audioEmbed", shape=[1, "T", 8]), _In(name="visualEmbed", shape=[1, "T", 8])]

    def run(self, _out, feeds):  # noqa: ANN001, ANN201
        v = feeds["visualEmbed"][0, :, 0]
        assert feeds["audioEmbed"].shape[1] == len(v)
        return [(v / 255.0)[None]]  # [1, T] ehtimol


def _faces(bright: list[bool]) -> np.ndarray:
    return np.stack([np.full((112, 112), 200.0 if b else 30.0, np.float32) for b in bright])


def test_combined_session_scores_and_softmax() -> None:
    sess = FakeCombined()
    asd = LrAsdOnnx(session=sess)
    p = asd.score(_faces([True, False, True]), np.zeros((12, 13), np.float32))
    assert p.shape == (3,)
    assert p[0] > 0.9 and p[1] < 0.1 and p[2] > 0.9


def test_trims_to_shorter_stream_and_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    import lahza_engine.reframe.asd as asd_mod

    monkeypatch.setattr(asd_mod, "ASD_CHUNK_FRAMES", 4)
    sess = FakeCombined()
    p = LrAsdOnnx(session=sess).score(_faces([True] * 10), np.zeros((4 * 9 + 2, 13)))
    assert len(p) == 9  # audio 9 kadrga yetadi
    assert [c["input_v"][1] for c in sess.calls] == [4, 4, 1]
    assert LrAsdOnnx(session=sess).score(_faces([True]), np.zeros((2, 13))).size == 0


def test_split_sessions() -> None:
    asd = LrAsdOnnx(audio=FakeFront("a", "audio"), visual=FakeFront("v", "visual"),
                    backend=FakeBackend())
    p = asd.score(_faces([True, False]), np.zeros((8, 13), np.float32))
    assert p[0] == pytest.approx(200 / 255) and p[1] == pytest.approx(30 / 255)


def test_constructor_needs_sessions() -> None:
    with pytest.raises(ValueError):
        LrAsdOnnx(audio=FakeFront("a", "audio"))


def test_to_probability_modes() -> None:
    assert to_probability([0.2, 0.8]).tolist() == pytest.approx([0.2, 0.8])
    assert to_probability([[0.0, 0.0]])[0] == pytest.approx(0.5)
    assert to_probability([-10.0, 10.0])[0] < 0.01
    assert to_probability([0.0], mode="logit")[0] == pytest.approx(0.5)
    # [1, 2]: T=2 ehtimol (bitta kadrning 2 sinfi emas)
    assert to_probability([[0.8, 0.1]], frames=2).tolist() == pytest.approx([0.8, 0.1])


def test_mfcc_shape_and_rate() -> None:
    sr = 16_000
    t = np.arange(sr) / sr
    audio = (np.sin(2 * np.pi * 220 * t) * 10_000).astype(np.int16)
    m = mfcc(audio, sr)
    assert m.shape[1] == 13
    assert 98 <= m.shape[0] <= 100  # 100 kadr/s
    assert np.isfinite(m).all()
    assert mfcc(np.zeros(sr // 10), sr).shape[1] == 13  # sukunat - log(0) yo'q


def test_face_crop_is_gray_112_and_handles_border() -> None:
    frame = np.zeros((360, 640, 3), np.uint8)
    frame[100:200, 300:380] = 255
    c = face_crop(frame, Box(300 / 640, 100 / 360, 80 / 640, 100 / 360))
    assert c.shape == (112, 112) and c.dtype == np.float32
    assert c.max() == pytest.approx(255, abs=1)
    edge = face_crop(frame, Box(0.95, 0.9, 0.1, 0.2))  # kadrdan chiqib ketgan
    assert edge.shape == (112, 112)


def test_score_track_aligns_audio_and_fallbacks() -> None:
    asd = LrAsdOnnx(session=FakeCombined())
    frames = [(1_000 + i * 40, f) for i, f in enumerate(_faces([True, True, False, False]))]
    audio = np.zeros(16_000 * 3, np.int16)
    res = score_track(asd, frames, audio, audio_start_ms=0)
    assert [t for t, _ in res] == [1_000, 1_040, 1_080, 1_120]
    assert res[0][1] > 0.9 and res[3][1] < 0.1
    assert score_track(None, frames, audio) == []  # model yo'q - heuristika

    class Broken:
        def score(self, *_a):  # noqa: ANN002, ANN201
            raise RuntimeError("buzuq")

    assert score_track(Broken(), frames, audio) == []


def test_scores_at_window_average() -> None:
    ts = {1: [(0, 0.2), (40, 0.4), (400, 1.0)], 2: [(1_000, 0.9)]}
    assert scores_at(ts, 20, window_ms=100) == {1: pytest.approx(0.3)}


def test_find_and_load_without_model(tmp_path: Path) -> None:
    assert load_asd_backend(None) is None
    assert load_asd_backend(tmp_path / "yoq") is None
    (tmp_path / "face_detector.onnx").write_bytes(b"x")
    assert find_asd_files(tmp_path) is None
    assert load_asd_backend(tmp_path) is None  # faqat yuz detektori - ASD yo'q
    (tmp_path / "asd.onnx").write_bytes(b"buzuq onnx")
    assert find_asd_files(tmp_path) == [tmp_path / "asd.onnx"]
    assert load_asd_backend(tmp_path) is None  # buzuq fayl - xatosiz fallback
    for n in ("asd_audio_frontend.onnx", "asd_visual_frontend.onnx", "asd_av_backend.onnx"):
        (tmp_path / n).write_bytes(b"x")
    assert [p.name for p in find_asd_files(tmp_path) or []] == [
        "asd_audio_frontend.onnx", "asd_visual_frontend.onnx", "asd_av_backend.onnx"]


def test_load_from_store(tmp_path: Path) -> None:
    class Store:
        def __init__(self, m) -> None:  # noqa: ANN001
            self.m = m

        def default_for(self, task):  # noqa: ANN001, ANN201
            assert task is Task.VISION
            return self.m

    assert load_asd_from_store(Store(None)) is None
    assert load_asd_from_store(Store(SimpleNamespace(path=str(tmp_path)))) is None


def test_from_dir_uses_onnxruntime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Papkadan yuklash onnxruntime.InferenceSession orqali (soxta sessiya bilan almashtirilgan)."""
    ort = pytest.importorskip("onnxruntime")
    opened: list[str] = []
    fakes = {"asd.onnx": FakeCombined, "asd_audio_frontend.onnx": lambda: FakeFront("a", "audio"),
             "asd_visual_frontend.onnx": lambda: FakeFront("v", "visual"),
             "asd_av_backend.onnx": FakeBackend}

    def fake_session(path, providers=None):  # noqa: ANN001, ANN202
        opened.append(Path(path).name)
        return fakes[Path(path).name]()

    monkeypatch.setattr(ort, "InferenceSession", fake_session)
    (tmp_path / "asd.onnx").write_bytes(b"x")
    asd = load_asd_backend(tmp_path)
    assert asd is not None and asd.session is not None and opened == ["asd.onnx"]
    for n in ("asd_audio_frontend.onnx", "asd_visual_frontend.onnx", "asd_av_backend.onnx"):
        (tmp_path / n).write_bytes(b"x")
    asd = load_asd_backend(tmp_path)  # uchta fayl ustuvor (katalog to'plami)
    assert asd is not None and asd.session is None
    p = asd.score(_faces([True, False]), np.zeros((8, 13), np.float32))
    assert p[0] > p[1]


def test_real_onnxruntime_session(tmp_path: Path) -> None:
    """Haqiqiy onnxruntime bilan kichik birlashgan model (onnx paketi bo'lsa)."""
    onnx = pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")
    from onnx import TensorProto, helper

    a = helper.make_tensor_value_info("audioFeature", TensorProto.FLOAT, [1, None, 13])
    v = helper.make_tensor_value_info("visualFeature", TensorProto.FLOAT, [1, None, 112, 112])
    out = helper.make_tensor_value_info("score", TensorProto.FLOAT, [1, None])
    axes = helper.make_tensor("axes", TensorProto.INT64, [2], [2, 3])
    k = helper.make_tensor("k", TensorProto.FLOAT, [], [0.05])
    b = helper.make_tensor("b", TensorProto.FLOAT, [], [-6.0])
    nodes = [
        helper.make_node("ReduceMean", ["visualFeature", "axes"], ["m"], keepdims=0),
        helper.make_node("Mul", ["m", "k"], ["mk"]),
        helper.make_node("Add", ["mk", "b"], ["score"]),
    ]
    g = helper.make_graph(nodes, "fake_asd", [a, v], [out], initializer=[axes, k, b])
    model = helper.make_model(g, opset_imports=[helper.make_opsetid("", 18)])
    model.ir_version = 8
    onnx.save(model, tmp_path / "asd.onnx")
    asd = load_asd_backend(tmp_path)
    assert asd is not None
    p = asd.score(_faces([True, False]), np.zeros((8, 13), np.float32))
    assert p[0] > 0.9 and p[1] < 0.1  # logit -> sigmoid


def test_catalog_vision_entry_is_candidate() -> None:
    cat = Catalog.model_validate_json((ROOT / "catalog/catalog.json").read_text(encoding="utf-8"))
    e = next(x for x in cat.entries if x.id == "vision-blazeface-lrasd")
    assert e.status == "candidate"
    names = {f.path for f in e.files}
    assert {"asd_audio_frontend.onnx", "asd_visual_frontend.onnx", "asd_av_backend.onnx"} <= names
    assert all(f.sha256 is None for f in e.files if f.path.startswith("asd_"))
