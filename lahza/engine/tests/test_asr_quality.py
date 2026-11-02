"""Transkripsiya sifati: Tez (base) / Aniq (small) tanlovi, .lzpack orqali o'rnatish, kesh kaliti."""
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from _api_helpers import make_client, wait_job

from lahza_engine.core.analyze import analysis_stages
from lahza_engine.core.cache import stage_key
from lahza_engine.core.errors import CodedError
from lahza_engine.core.runner import Cancelled
from lahza_engine.models import asr_quality as quality
from lahza_engine.models import lzpack
from lahza_engine.models.catalog import Task
from lahza_engine.models.store import InstalledModel, ModelStore

WEIGHTS = b"small-int8-weights"


def _add(store: ModelStore, model_id: str, folder: str, data: bytes, task=Task.ASR, name="model.bin"):
    root = store.model_dir(task, folder)
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_bytes(data)
    model = InstalledModel(id=model_id, task=task, version="1", path=str(root), source="custom")
    store.register([model])
    return model


def _small_pack(tmp_path: Path) -> Path:
    """Haqiqiy export_pack bilan small + silero paketi (build/ dagi artefakt kabi)."""
    src = ModelStore(tmp_path / "pack-src")
    _add(src, quality.ACCURATE_MODEL_ID, "navai-whisper-small-uzbek", WEIGHTS)
    _add(src, "custom:silero-v5.1.2", "silero-v5.1.2", b"onnx", task=Task.VAD, name="silero_vad.onnx")
    out = tmp_path / "small.lzpack"
    lzpack.export_pack(src, out)
    return out


@pytest.fixture
def pinned(monkeypatch):
    monkeypatch.setattr(quality, "ACCURATE_WEIGHTS_SHA256", hashlib.sha256(WEIGHTS).hexdigest())
    monkeypatch.delenv(quality.PACK_URL_ENV, raising=False)


def test_status_and_switch_between_installed_models(tmp_path, pinned):
    store = ModelStore(tmp_path / "m")
    assert quality.status(store)["mode"] == "none"
    _add(store, quality.FAST_MODEL_ID, "navai-whisper-base-uzbek", b"base")
    state = quality.status(store)
    assert state["mode"] == "fast" and state["fast"]["installed"]
    assert state["accurate"] == {"model_id": quality.ACCURATE_MODEL_ID, "installed": False,
                                 "download_bytes": quality.ACCURATE_PACK_SIZE, "download_available": False}
    with pytest.raises(CodedError) as info:
        quality.select(store, "accurate")
    assert info.value.code == "model_missing"
    _add(store, quality.ACCURATE_MODEL_ID, "navai-whisper-small-uzbek", WEIGHTS)
    assert store.default_for(Task.ASR).id == quality.FAST_MODEL_ID  # register standartni almashtirmaydi
    quality.select(store, "accurate")
    assert quality.status(store)["mode"] == "accurate"
    assert quality.status(store)["accurate"]["download_bytes"] == 0
    quality.select(store, "fast")
    assert store.default_for(Task.ASR).id == quality.FAST_MODEL_ID


def test_pack_urls_accept_only_https(monkeypatch):
    monkeypatch.setenv(quality.PACK_URL_ENV, "http://x/a.lzpack, https://a/p.lzpack https://b/p.lzpack")
    assert quality.pack_urls() == ["https://a/p.lzpack", "https://b/p.lzpack"]


def test_install_from_local_pack_keeps_vad_and_selects_small(tmp_path, pinned):
    pack = _small_pack(tmp_path)
    store = ModelStore(tmp_path / "m")
    _add(store, quality.FAST_MODEL_ID, "navai-whisper-base-uzbek", b"base")
    _add(store, "custom:other-vad", "other", b"onnx", task=Task.VAD, name="v.onnx")
    stages = []
    model = quality.install_accurate(store, pack_path=pack, progress=lambda st, f: stages.append((st, f)))
    assert model.id == quality.ACCURATE_MODEL_ID
    assert store.default_for(Task.ASR).id == quality.ACCURATE_MODEL_ID
    assert store.default_for(Task.VAD).id == "custom:other-vad"
    assert stages[-1] == ("verify", 1.0)
    assert [f for _, f in stages] == sorted(f for _, f in stages)
    assert pack.exists()  # foydalanuvchi fayli o'chirilmaydi


def test_install_rejects_wrong_weights(tmp_path, monkeypatch):
    monkeypatch.setattr(quality, "ACCURATE_WEIGHTS_SHA256", "0" * 64)
    store = ModelStore(tmp_path / "m")
    _add(store, quality.FAST_MODEL_ID, "navai-whisper-base-uzbek", b"base")
    with pytest.raises(ValueError, match="sha256"):
        quality.install_accurate(store, pack_path=_small_pack(tmp_path))
    assert store.default_for(Task.ASR).id == quality.FAST_MODEL_ID


def test_download_path_uses_pinned_pack_and_cleans_up(tmp_path, pinned, monkeypatch):
    pack = _small_pack(tmp_path)
    monkeypatch.setenv(quality.PACK_URL_ENV, "https://example.invalid/small.lzpack")
    seen = {}

    def fake_download(urls, dest, sha256, size, progress=None):
        seen.update(urls=urls, sha256=sha256, size=size)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(pack.read_bytes())
        progress(5, 10)
        progress(10, 10)
        return dest

    monkeypatch.setattr(quality, "download", fake_download)
    store = ModelStore(tmp_path / "m")
    with pytest.raises(ValueError, match="rozilig"):
        quality.install_accurate(store)
    stages = []
    quality.install_accurate(store, consent=True, progress=lambda st, f: stages.append((st, f)))
    assert seen == {"urls": ["https://example.invalid/small.lzpack"],
                    "sha256": quality.ACCURATE_PACK_SHA256, "size": quality.ACCURATE_PACK_SIZE}
    assert ("download", 0.4) in stages and ("download", 0.8) in stages
    assert store.default_for(Task.ASR).id == quality.ACCURATE_MODEL_ID
    assert not list((store.root / ".downloads").glob("*.lzpack"))


def test_download_cancel_propagates(tmp_path, pinned, monkeypatch):
    monkeypatch.setenv(quality.PACK_URL_ENV, "https://example.invalid/small.lzpack")
    flag = SimpleNamespace(on=False)

    def fake_download(urls, dest, sha256, size, progress=None):
        flag.on = True
        progress(1, 10)
        raise AssertionError("unreachable")

    monkeypatch.setattr(quality, "download", fake_download)
    store = ModelStore(tmp_path / "m")
    with pytest.raises(Cancelled):
        quality.install_accurate(store, consent=True, is_cancelled=lambda: flag.on)
    assert store.default_for(Task.ASR) is None


def test_api_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(quality, "ACCURATE_WEIGHTS_SHA256", hashlib.sha256(WEIGHTS).hexdigest())
    monkeypatch.delenv(quality.PACK_URL_ENV, raising=False)
    client, state = make_client(tmp_path, monkeypatch)
    assert client.get("/v1/asr-quality").json()["mode"] == "none"
    r = client.post("/v1/asr-quality", json={"mode": "fast"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "model_missing"
    _add(state.store, quality.FAST_MODEL_ID, "navai-whisper-base-uzbek", b"base")
    assert client.post("/v1/asr-quality", json={"mode": "accurate"}).status_code == 400  # rozilik yo'q
    assert client.post("/v1/asr-quality", json={"mode": "accurate", "consent": True}).status_code == 409
    assert client.post("/v1/asr-quality", json={"mode": "accurate",
                                                 "pack_path": str(tmp_path / "x.zip")}).status_code == 400
    pack = _small_pack(tmp_path)
    body = client.post("/v1/asr-quality", json={"mode": "accurate", "pack_path": str(pack)}).json()
    assert body["job"]["kind"] == "install" and body["job"]["meta"]["op"] == "asr-quality"
    job = wait_job(state, body["job"]["id"])
    assert job.status == "done", job.error
    assert client.get("/v1/asr-quality").json()["mode"] == "accurate"
    state._services = object()
    body = client.post("/v1/asr-quality", json={"mode": "fast"}).json()
    assert body["mode"] == "fast" and body["job"] is None
    assert state._services is None  # keyingi tahlil yangi ASR bilan quriladi
    body = client.post("/v1/asr-quality", json={"mode": "accurate"}).json()
    assert body["mode"] == "accurate" and body["job"] is None


def test_asr_model_id_is_part_of_analysis_cache_key():
    """Tanlov yangi tahlilga ta'sir qiladi; eski natija o'z kaliti bilan saqlanib qoladi."""
    asr = next(s for s in analysis_stages(SimpleNamespace(highlight=SimpleNamespace(model_dump=dict)))
               if s.name == "asr")
    keys = set()
    for model_id in (quality.FAST_MODEL_ID, quality.ACCURATE_MODEL_ID):
        ctx = SimpleNamespace(services={"svc": SimpleNamespace(asr_model_id=model_id, aligner=None)})
        assert asr.model_id(ctx) == model_id
        keys.add(stage_key("media", asr.name, asr.version, asr.model_id(ctx), {}))
    assert len(keys) == 2
