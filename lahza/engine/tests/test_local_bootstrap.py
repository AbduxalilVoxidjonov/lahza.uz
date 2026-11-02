import hashlib
import json
import sys
from types import SimpleNamespace

import pytest

from lahza_engine.models import local_bootstrap as lb
from lahza_engine.models.catalog import Task
from lahza_engine.models.store import ModelStore


def test_consent_before_network_or_files(tmp_path, monkeypatch):
    monkeypatch.setattr(lb.httpx, "Client", lambda **kw: pytest.fail("network"))
    with pytest.raises(ValueError, match="consent"):
        lb.bootstrap(ModelStore(tmp_path))
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("args", [[], ["--download"], ["--consent"]])
def test_cli_requires_both_flags(args, tmp_path):
    target = tmp_path / "absent"
    with pytest.raises(SystemExit) as exc:
        lb.main([*args, "--models-dir", str(target)])
    assert exc.value.code == 2
    assert not target.exists()


@pytest.mark.parametrize("failure", [None, "hash", "size", "load", "revision"])
def test_install_contract(tmp_path, monkeypatch, failure):
    payload = b"model contents"
    blob = hashlib.sha1(b"blob 14\0" + payload).hexdigest()
    entries = [{"rfilename": n, "size": len(payload), "blobId": blob} for n in lb.FILES]
    if failure == "hash":
        entries[0]["blobId"] = "bad"
    if failure == "size":
        entries[0]["size"] = lb.MAX_BYTES + 1
    metadata = {"sha": "bad" if failure == "revision" else lb.REVISION, "siblings": entries}

    class Client:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kw):
            assert any(revision in url for _, revision in lb.SOURCES.values())
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {**metadata, "sha": "bad" if failure == "revision" else next(revision for _, revision in lb.SOURCES.values() if revision in url)})

    def fake_download(urls, dest, expected, size, **kw):
        kw["progress"](size, size)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)

    def load(path, **kw):
        assert kw == {"device": "cpu", "compute_type": "int8", "local_files_only": True}
        if failure == "load":
            raise RuntimeError("load failed")

    monkeypatch.setattr(lb.httpx, "Client", Client)
    monkeypatch.setattr(lb, "download", fake_download)
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=load))
    store = ModelStore(tmp_path)
    if failure:
        with pytest.raises((ValueError, RuntimeError)):
            lb.bootstrap(store, consent=True)
        assert store.default_for(Task.ASR) is None
    else:
        events = []
        model = lb.bootstrap(store, consent=True, progress=lambda n, t: events.append((n, t)))
        assert events == [(i * len(payload), len(lb.FILES) * len(payload)) for i in range(len(lb.FILES) + 1)]
        assert store.default_for(Task.ASR) == model
        assert model.source == "custom" and not model.verified
        provenance = json.loads((tmp_path / "asr" / lb.MODEL_FOLDER / "provenance.json").read_text())
        assert provenance["revision"] == lb.REVISION
        assert all(f["sha256"] == hashlib.sha256(payload).hexdigest() for f in provenance["files"])


def test_cancel_progress_propagates(tmp_path, monkeypatch):
    class Cancelled(Exception):
        pass

    def cancel(have, total):
        raise Cancelled()

    class Client:
        def __init__(self, **kw):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, **kw):
            data = {"sha": next(revision for _, revision in lb.SOURCES.values() if revision in url), "siblings": [
                {"rfilename": n, "size": 1} for n in lb.FILES]}
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: data)

    monkeypatch.setattr(lb.httpx, "Client", Client)
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=None))
    store = ModelStore(tmp_path)
    with pytest.raises(Cancelled):
        lb.bootstrap(store, consent=True, progress=cancel)
    assert store.default_for(Task.ASR) is None


def test_vad_explicit_consent_and_validated_registration(tmp_path, monkeypatch):
    from lahza_engine.vad import silero_onnx
    store = ModelStore(tmp_path)
    with pytest.raises(ValueError, match="consent"):
        lb.bootstrap_vad(store)
    called = []
    def fake_download(urls, dest, expected, size, **kw):
        assert lb.SILERO_REVISION in urls[0]
        assert len(expected) == 64
        called.append(dest.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"test")
    monkeypatch.setattr(lb, "download", fake_download)
    monkeypatch.setattr(silero_onnx, "SileroOnnxVad", lambda path: None)
    model = lb.bootstrap_vad(store, consent=True)
    assert called == ["silero_vad.onnx", "LICENSE"]
    assert store.default_for(Task.VAD) == model
    assert model.source == "custom" and not model.verified
