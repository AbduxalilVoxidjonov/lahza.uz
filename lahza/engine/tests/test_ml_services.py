from pathlib import Path
from types import SimpleNamespace

from lahza_engine.core import services as services_mod
from lahza_engine.models.catalog import Task


class FakeStore:
    def __init__(self, models: dict[Task, Path]) -> None:
        self.models = models

    def default_for(self, task: Task):
        p = self.models.get(task)
        return SimpleNamespace(id=f"{task.value}-1", path=str(p)) if p else None


def test_build_services_prefers_onnx_backends(monkeypatch, tmp_path: Path) -> None:
    import lahza_engine.align.ctc_onnx as ctc_onnx
    import lahza_engine.reframe.faces as faces
    import lahza_engine.vad.silero_onnx as silero_onnx

    for name in ("vad", "align", "vision"):
        (tmp_path / name).mkdir()
    (tmp_path / "vad" / "silero_vad.onnx").write_bytes(b"x")
    (tmp_path / "align" / "model.onnx").write_bytes(b"x")
    (tmp_path / "vision" / "asd.onnx").write_bytes(b"x")
    (tmp_path / "vision" / "blazeface_short.onnx").write_bytes(b"x")

    monkeypatch.setattr(silero_onnx, "SileroOnnxVad", lambda p: ("vad", Path(p).name))
    monkeypatch.setattr(ctc_onnx.CtcAligner, "from_dir", classmethod(lambda cls, p: ("al", p.name)))
    monkeypatch.setattr(faces, "OnnxBlazeFaceDetector", lambda p: ("face", Path(p).name))
    store = FakeStore({Task.VAD: tmp_path / "vad", Task.ALIGN: tmp_path / "align",
                       Task.VISION: tmp_path / "vision"})
    s = services_mod.build_services(store)
    assert s.vad == ("vad", "silero_vad.onnx")
    assert s.aligner == ("al", "align") and s.aligner_model_id == "align-1"
    assert s.face_detector == ("face", "blazeface_short.onnx")


def test_build_services_fallbacks_on_broken_models(tmp_path: Path) -> None:
    (tmp_path / "vad").mkdir()
    (tmp_path / "vad" / "silero_vad.onnx").write_bytes(b"not an onnx model")
    (tmp_path / "align").mkdir()
    (tmp_path / "align" / "model.onnx").write_bytes(b"x")  # vocab.json yo'q
    s = services_mod.build_services(FakeStore({Task.VAD: tmp_path / "vad", Task.ALIGN: tmp_path / "align"}))
    assert s.aligner is None and s.aligner_model_id is None
    # silero_vad paketi o'rnatilgan bo'lmasa - None (energiya VAD); bo'lsa - paket orqali
    assert s.vad is None or not hasattr(s.vad, "session")
