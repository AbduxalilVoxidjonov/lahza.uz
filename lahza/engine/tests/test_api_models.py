from pathlib import Path

from _api_helpers import make_client, wait_job

from lahza_engine.models.catalog import Task
from lahza_engine.models.store import InstalledModel


def _seed(st) -> None:
    root = st.store.root
    for mid in ("w1", "w2"):
        d = root / "asr" / mid
        d.mkdir(parents=True)
        (d / "model.bin").write_bytes(mid.encode() * 100)
    (root / "llm").mkdir()
    (root / "llm" / "q.gguf").write_bytes(b"GGUF" + b"\x00" * 20)
    st.store.register([
        InstalledModel(id="w1", task=Task.ASR, version="1", path=str(root / "asr" / "w1")),
        InstalledModel(id="w2", task=Task.ASR, version="1", path=str(root / "asr" / "w2")),
        InstalledModel(id="custom:q", task=Task.LLM, version="custom", path=str(root / "llm" / "q.gguf"),
                       source="custom", verified=False),
    ])


def test_default_and_delete(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _seed(st)
    assert c.post("/v1/models/w2:default").json() == {"ok": True}
    assert c.get("/v1/models").json()["defaults"]["asr"] == "w2"
    assert c.post("/v1/models/yoq:default").status_code == 404
    assert c.delete("/v1/models/w2").json() == {"ok": True}
    assert c.get("/v1/models").json()["defaults"]["asr"] == "w1"
    assert not (st.store.root / "asr" / "w2").exists()
    assert c.delete("/v1/models/custom:q").json() == {"ok": True}
    assert "llm" not in c.get("/v1/models").json()["defaults"]
    assert c.delete("/v1/models/yoq").status_code == 404
    assert st._services is None  # servislar qayta yig'iladi


def test_self_test(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _seed(st)
    monkeypatch.setenv("LAHZA_CATALOG", str(tmp_path / "yoq.json"))  # katalogsiz
    r = c.post("/v1/models/custom:q:test").json()
    assert r["ok"] is True and "backend yuklandi" in r["detail"], r
    assert st.store.get("custom:q").self_test_ok is True

    import lahza_engine.core.services as services

    class FakeAsr:
        def __init__(self, *a, **k):
            pass

    monkeypatch.setattr("lahza_engine.asr.faster_whisper_backend.FasterWhisperBackend", FakeAsr,
                        raising=False)
    r = c.post("/v1/models/w1:test").json()
    assert r["ok"] is True, r
    (st.store.root / "asr" / "w1" / "model.bin").unlink()
    r = c.post("/v1/models/w1:test").json()
    assert r["ok"] is False and st.store.get("w1").self_test_ok is False
    assert c.post("/v1/models/yoq:test").status_code == 404
    assert services  # import ishlatildi


def test_pack_export_import_jobs(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _seed(st)
    pack = tmp_path / "m.lzpack"
    r = c.post("/v1/models:export-pack", json={"path": str(pack)})
    assert r.status_code == 200 and r.json()["kind"] == "pack"
    job = wait_job(st, r.json()["id"])
    assert job.status == "done" and pack.exists() and job.result["files"] == 3
    assert c.post("/v1/models:export-pack", json={"path": str(tmp_path / "x.zip")}).status_code == 400
    assert c.post("/v1/models:export-pack",
                  json={"path": str(tmp_path / "yoq" / "m.lzpack")}).status_code == 400

    c2, st2 = make_client(tmp_path / "ikkinchi", monkeypatch)
    r = c2.post("/v1/models:import-pack", json={"path": str(pack)})
    job = wait_job(st2, r.json()["id"])
    assert job.status == "done", job.error
    assert {m["id"] for m in c2.get("/v1/models").json()["models"]} == {"w1", "w2", "custom:q"}
    assert c2.post("/v1/models:import-pack", json={"path": str(tmp_path / "yoq.lzpack")}).status_code == 400
    bad = tmp_path / "bad.lzpack"
    bad.write_bytes(b"emas")
    job = wait_job(st2, c2.post("/v1/models:import-pack", json={"path": str(bad)}).json()["id"])
    assert job.status == "failed" and "zip" in job.error
