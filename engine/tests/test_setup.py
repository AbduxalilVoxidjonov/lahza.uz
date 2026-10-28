"""First-run contract, concurrency, durable retry/cancel, offline integrity checks."""
import hashlib
import json
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import httpx
import pytest
from _api_helpers import make_client, wait_job
from conftest import requires_symlink

from lahza_engine.core.events import EventBus
from lahza_engine.core.jobs import Job, JobManager
from lahza_engine.models import local_llm
from lahza_engine.models import setup as setup_backend
from lahza_engine.models.catalog import Task
from lahza_engine.models.downloader import DownloadError, download
from lahza_engine.models.setup import Setup, coordinator
from lahza_engine.models.store import InstalledModel, ModelStore


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    client, state = make_client(tmp_path, monkeypatch)
    manager = coordinator(state.store, state.jobs)
    monkeypatch.setattr(manager, "_runtime", lambda names: (True, None))
    monkeypatch.setattr(setup_backend.importlib, "import_module", lambda name: object())
    monkeypatch.setattr(manager, "_validate_model", lambda model, root: None)
    calls = []

    def install(task):
        def work(store, *, consent, progress):
            assert consent is True
            calls.append(task.value)
            progress(2, 4)
            path = store.root / (task.value + ".model")
            path.write_bytes(b"ready")
            model = InstalledModel(id="test:" + task.value, task=task, path=str(path), version="1")
            store.register([model])
            progress(4, 4)
            return model
        return work

    monkeypatch.setattr(setup_backend.bootstrap, "bootstrap", install(Task.ASR))
    monkeypatch.setattr(setup_backend.bootstrap, "bootstrap_vad", install(Task.VAD))
    monkeypatch.setattr(local_llm, "install_model", install(Task.LLM))
    return client, state, manager, calls


def test_status_offline_no_download_or_submit(tmp_path, monkeypatch):
    client, state = make_client(tmp_path, monkeypatch)
    # Block the real transport: TestClient itself goes through httpx.Client.request.
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", lambda *a, **kw: pytest.fail("network"))
    monkeypatch.setattr(state.jobs, "submit", lambda *a, **kw: pytest.fail("submit"))
    with client:
        response = client.get("/v1/setup")
        assert response.status_code == 200
        data = response.json()
        assert set(data) == {"ready", "components", "job"}
        assert not data["ready"] and data["job"] is None
        assert {c["id"] for c in data["components"]} == {"asr", "vad", "llm", "render", "llm_runtime"}
        assert all(set(c) == {"id", "ready", "required", "download_bytes", "detail"} for c in data["components"])
        assert all(c["required"] for c in data["components"])
        client.headers.pop("Authorization")
        assert client.get("/v1/setup").status_code == 401
        assert client.post("/v1/setup:start", json={"consent": True}).status_code == 401


@pytest.mark.parametrize("body,status", [({}, 422), ({"consent": False}, 400),
                                        ({"consent": "true"}, 422), ({"consent": 1}, 422)])
def test_requires_literal_consent(prepared, body, status):
    client, state, manager, calls = prepared
    with client:
        assert client.post("/v1/setup:start", json=body).status_code == status
        assert not calls and not state.jobs.jobs


def test_install_idempotent_progress_and_preserve_healthy_defaults(prepared):
    client, state, manager, calls = prepared
    path = state.store.root / "my-asr"
    path.write_bytes(b"already installed")
    existing = InstalledModel(id="my-asr", task=Task.ASR, version="custom", path=str(path))
    state.store.register([existing])
    with client:
        result = client.post("/v1/setup:start", json={"consent": True}).json()
        job = wait_job(state, result["id"])
        assert job.kind == "install" and job.status == "done", job.error
        assert calls == ["vad", "llm"]
        assert state.store.default_for(Task.ASR).id == existing.id
        assert client.get("/v1/setup").json()["ready"]
        assert client.post("/v1/setup:start", json={"consent": True}).json()["id"] == job.id
        assert job.meta["op"] == "setup" and job.meta["download_bytes"] == 4
        journal = json.loads(manager.journal.read_text())
        assert journal["status"] == "done" and journal["progress"] == 1
        assert "on_change" not in journal


def test_concurrent_starts_same_store_return_one_job(prepared, monkeypatch):
    client, state, manager, calls = prepared
    entered, release = threading.Event(), threading.Event()
    original = setup_backend.bootstrap.bootstrap

    def blocking(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(setup_backend.bootstrap, "bootstrap", blocking)
    another_jobs = JobManager(EventBus())
    try:
        with client:
            manager.start(state.invalidate_services)
            with ThreadPoolExecutor(max_workers=8) as pool:
                jobs = list(pool.map(lambda _: coordinator(ModelStore(state.store.root), another_jobs)
                                     .start(state.invalidate_services), range(8)))
            assert len({job.id for job in jobs}) == 1
            assert entered.wait(5)
            release.set()
            # The coordinator belongs to original State; all starts share it.
            assert wait_job(state, jobs[0].id).status == "done"
            assert calls == ["asr", "vad", "llm"]
    finally:
        release.set()
        another_jobs.shutdown()


def test_failed_retry_skips_completed_assets(prepared, monkeypatch):
    client, state, manager, calls = prepared
    install_vad = setup_backend.bootstrap.bootstrap_vad
    monkeypatch.setattr(setup_backend.bootstrap, "bootstrap_vad", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    with client:
        failed = wait_job(state, client.post("/v1/setup:start", json={"consent": True}).json()["id"])
        assert failed.status == "failed" and "offline" in failed.error
        assert not client.get("/v1/setup").json()["ready"]
        assert json.loads(manager.journal.read_text())["status"] == "failed"
        monkeypatch.setattr(setup_backend.bootstrap, "bootstrap_vad", install_vad)
        retried = wait_job(state, client.post("/v1/setup:start", json={"consent": True}).json()["id"])
        assert retried.status == "done" and retried.id != failed.id
        assert calls == ["asr", "vad", "llm"]


def test_cancel_and_explicit_retry(prepared, monkeypatch):
    client, state, manager, calls = prepared
    entered, release = threading.Event(), threading.Event()
    original = setup_backend.bootstrap.bootstrap

    def blocking(store, *, consent, progress):
        entered.set()
        assert release.wait(5)
        progress(1, 4)
        return original(store, consent=consent, progress=progress)

    monkeypatch.setattr(setup_backend.bootstrap, "bootstrap", blocking)
    with client:
        jid = client.post("/v1/setup:start", json={"consent": True}).json()["id"]
        try:
            assert entered.wait(5)
            assert client.post(f"/v1/jobs/{jid}:cancel").status_code == 200
        finally:
            release.set()
        assert wait_job(state, jid).status == "cancelled"
        assert client.get("/v1/setup").json()["job"]["status"] == "cancelled"
        assert calls == []
        monkeypatch.setattr(setup_backend.bootstrap, "bootstrap", original)
        assert wait_job(state, client.post("/v1/setup:start", json={"consent": True}).json()["id"]).status == "done"


def test_runtime_preflight_before_any_download(prepared, monkeypatch):
    client, state, manager, calls = prepared
    monkeypatch.setattr(manager, "_runtime", lambda names: (False, "llama-server paketda yo‘q; desktop paketini o‘rnating"))
    with client:
        job = wait_job(state, client.post("/v1/setup:start", json={"consent": True}).json()["id"])
        assert job.status == "failed" and "desktop" in job.error
        assert not calls
        assert all(not c["ready"] and c["detail"] for c in client.get("/v1/setup").json()["components"][-2:])


def test_interrupted_journal_recovered_without_network(tmp_path, monkeypatch):
    store, jobs = ModelStore(tmp_path), JobManager(EventBus())
    interrupted = Job(id="interrupted", kind="install", status="running", progress=.42,
                      stage="llm", meta={"op": "setup", "download_bytes": 123})
    (tmp_path / "setup-job.json").write_text(json.dumps(interrupted.public()))
    try:
        manager = Setup(store, jobs)
        assert manager.job.status == "failed"
        assert manager.job.progress == .42 and manager.job.meta["download_bytes"] == 123
        assert "Qayta" in manager.job.error or "qayta" in manager.job.error
        assert jobs.jobs["interrupted"] is manager.job
    finally:
        jobs.shutdown()


def test_readiness_hash_cached_and_corruption_invalidates(tmp_path, monkeypatch):
    store, jobs = ModelStore(tmp_path), JobManager(EventBus())
    root = tmp_path / "llm" / "qwen3-4b-q4-k-m"
    root.mkdir(parents=True)
    weights = root / local_llm.MODEL_FILE
    payload = b"GGUF" + struct.pack("<IQQ", 3, 1, 1) + b"model"
    weights.write_bytes(payload)
    metadata = root / "metadata"
    metadata.mkdir()
    (metadata / "LICENSE").write_bytes(b"notice")
    (metadata / "README.md").write_bytes(b"notice")
    provenance = {"revision": local_llm.MODEL_REVISION, "repository": local_llm.MODEL_REPO,
                  "sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload),
                  "notices": [{"file": name, "sha256": hashlib.sha256(b"notice").hexdigest()}
                              for name in ("LICENSE", "README.md")]}
    (metadata / "SOURCE.json").write_text(json.dumps(provenance))
    monkeypatch.setattr(local_llm, "MODEL_SIZE", len(payload))
    monkeypatch.setattr(local_llm, "MODEL_SHA256", hashlib.sha256(payload).hexdigest())
    model = InstalledModel(id=local_llm.MODEL_ID, task=Task.LLM, version="1", path=str(weights))
    store.register([model])
    manager = Setup(store, jobs)
    hashes = []
    original = setup_backend.sha256_file
    monkeypatch.setattr(local_llm, "sha256_file", lambda p: (hashes.append(p), original(p))[1])
    try:
        assert manager._model(model) == (True, None)
        assert manager._model(model) == (True, None)
        assert len(hashes) == 3
        (metadata / "SOURCE.json").write_text('{"revision":"wrong","notices":[]}')
        assert not manager._model(model)[0]
        (metadata / "SOURCE.json").write_text(json.dumps(provenance))
        weights.write_bytes(payload[:-1] + b"X")
        assert not manager._model(model)[0]
        assert "sha256" in manager._model(model)[1]
    finally:
        jobs.shutdown()


def test_registry_id_without_file_not_ready(tmp_path):
    jobs = JobManager(EventBus())
    try:
        manager = Setup(ModelStore(tmp_path), jobs)
        model = InstalledModel(id=local_llm.MODEL_ID, task=Task.LLM, version="1", path=str(tmp_path / "gone"))
        assert not manager._model(model)[0]
    finally:
        jobs.shutdown()


def test_downloader_verified_asset_offline_and_corrupt_repair(tmp_path):
    path = tmp_path / "model"
    payload = b"healthy"
    digest = hashlib.sha256(payload).hexdigest()
    path.write_bytes(payload)
    requests = []

    def transport(request):
        requests.append(request)
        return httpx.Response(200, content=payload)

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        assert download(["https://test/model"], path, digest, len(payload), client=client) == path
        assert requests == []
        path.write_bytes(b"corrupt")
        download(["https://test/model"], path, digest, len(payload), client=client)
        assert len(requests) == 1 and path.read_bytes() == payload


def test_downloader_checksum_failure_keeps_existing_asset(tmp_path):
    path = tmp_path / "model"
    path.write_bytes(b"old")
    with (httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"bad"))) as client,
          pytest.raises(DownloadError, match="sha256")):
        download(["https://test/model"], path, "0" * 64, 3, client=client)
    assert path.read_bytes() == b"old" and not path.with_suffix(".part").exists()


def test_llm_installer_requires_consent_before_network(tmp_path, monkeypatch):
    monkeypatch.setattr(local_llm, "download", lambda *a, **k: pytest.fail("network"))
    with pytest.raises(ValueError, match="consent"):
        local_llm.install_model(ModelStore(tmp_path))


def test_llm_installer_pinned_metadata_registration(tmp_path, monkeypatch):
    payload = b"GGUFtest"
    content = b"notice"
    blob = hashlib.sha1(b"blob 6\0" + content).hexdigest()
    calls = []

    def fake_download(urls, dest, digest, size, **kwargs):
        calls.append((urls[0], digest, size))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload if dest.name == local_llm.MODEL_FILE else content)
        return dest

    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, **kwargs):
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
                "sha": local_llm.MODEL_REVISION, "siblings": [
                    {"rfilename": n, "size": len(content), "blobId": blob} for n in ("LICENSE", "README.md")]})

    monkeypatch.setattr(local_llm, "download", fake_download)
    monkeypatch.setattr(local_llm.httpx, "Client", Client)
    store = ModelStore(tmp_path)
    existing = InstalledModel(id="mine", task=Task.LLM, path=str(tmp_path / "mine"), version="1")
    store.register([existing])
    model = local_llm.install_model(store, consent=True)
    assert calls[0][1:] == (local_llm.MODEL_SHA256, local_llm.MODEL_SIZE)
    assert all(local_llm.MODEL_REVISION in call[0] for call in calls)
    assert store.get(model.id) is not None and store.default_for(Task.LLM).id == "mine"
    assert (tmp_path / "llm/qwen3-4b-q4-k-m/metadata/SOURCE.json").exists()


def test_cancel_queued_setup_releases_lease_and_persists(prepared):
    client, state, manager, calls = prepared
    entered, release = threading.Event(), threading.Event()

    def occupy(job):
        entered.set()
        assert release.wait(5)

    with client:
        state.jobs.submit("install", occupy)
        try:
            assert entered.wait(5)
            jid = client.post("/v1/setup:start", json={"consent": True}).json()["id"]
            assert state.jobs.jobs[jid].status == "queued"
            client.post(f"/v1/jobs/{jid}:cancel")
        finally:
            release.set()
        assert wait_job(state, jid).status == "cancelled"
        assert json.loads(manager.journal.read_text())["status"] == "cancelled"
        assert not calls
        assert wait_job(state, client.post("/v1/setup:start", json={"consent": True}).json()["id"]).status == "done"


def test_runtime_missing_does_not_fall_back_to_path(tmp_path, monkeypatch):
    monkeypatch.setenv("LAHZA_BIN_DIR", str(tmp_path / "empty"))
    jobs = JobManager(EventBus())
    try:
        manager = Setup(ModelStore(tmp_path), jobs)
        ready, detail = manager._runtime(("ffmpeg", "ffprobe"))
        assert not ready and "desktop" in detail
    finally:
        jobs.shutdown()


def test_runtime_probes_cached_and_binary_change_invalidates(tmp_path, monkeypatch):
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    executable = binary_dir / ("llama-server.exe" if setup_backend.sys.platform == "win32" else "llama-server")
    executable.write_bytes(b"binary")
    monkeypatch.setenv("LAHZA_BIN_DIR", str(binary_dir))
    probes = []
    monkeypatch.setattr(setup_backend, "run", lambda args, **kw: (
        probes.append(args), SimpleNamespace(returncode=0, stdout=""))[1])
    jobs = JobManager(EventBus())
    try:
        manager = Setup(ModelStore(tmp_path / "models"), jobs)
        assert manager._runtime(("llama-server",)) == (True, None)
        assert manager._runtime(("llama-server",)) == (True, None)
        assert len(probes) == 1
        executable.write_bytes(b"repaired")
        assert manager._runtime(("llama-server",)) == (True, None)
        assert len(probes) == 2
    finally:
        jobs.shutdown()


def test_external_lease_deduplicates_and_cancels(prepared, monkeypatch):
    client, state, manager, calls = prepared
    entered, release = threading.Event(), threading.Event()

    def blocking(store, *, consent, progress):
        entered.set()
        assert release.wait(5)
        progress(1, 4)
        raise AssertionError("cancel must stop download")

    monkeypatch.setattr(setup_backend.bootstrap, "bootstrap", blocking)
    external_jobs = JobManager(EventBus())
    try:
        with client:
            original = manager.start(state.invalidate_services)
            try:
                assert entered.wait(5)
                external = Setup(ModelStore(state.store.root), external_jobs)
                assert external.external
                assert external.start(lambda: None).id == original.id
                external.cancel(original.id)
            finally:
                release.set()
            assert wait_job(state, original.id).status == "cancelled"
            assert external.status()["job"]["status"] == "cancelled"
    finally:
        release.set()
        external_jobs.shutdown()


def test_downloader_resumes_partial_without_restarting(tmp_path):
    path = tmp_path / "model"
    path.with_suffix(".part").write_bytes(b"abc")
    payload = b"abcdef"
    requests = []

    def respond(request):
        requests.append(request.headers.get("range"))
        return httpx.Response(206, content=payload[3:])

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        download(["https://test/model"], path, hashlib.sha256(payload).hexdigest(), 6, client=client)
    assert requests == ["bytes=3-"] and path.read_bytes() == payload


def test_asr_load_failure_and_broken_provenance_not_ready(tmp_path, monkeypatch):
    root = tmp_path / "asr"
    root.mkdir()
    (root / "model.bin").write_bytes(b"bad model")
    monkeypatch.setitem(setup_backend.sys.modules, "faster_whisper", SimpleNamespace(
        WhisperModel=lambda *a, **kw: (_ for _ in ()).throw(ValueError("unusable backend"))))
    jobs = JobManager(EventBus())
    try:
        manager = Setup(ModelStore(tmp_path), jobs)
        model = InstalledModel(id="mine", task=Task.ASR, version="1", path=str(root))
        assert "unusable backend" in manager._model(model)[1]
        (root / "provenance.json").write_text(json.dumps({"files": [{"path": "model.bin", "sha256": "0" * 64}]}))
        assert "sha256" in manager._model(model)[1]
    finally:
        jobs.shutdown()


@pytest.mark.parametrize("shape", ["external", pytest.param("symlink", marks=requires_symlink),
                                   "multiple", "wrong_suffix"])
def test_llm_readiness_matches_editing_agent_managed_paths(tmp_path, shape):
    store = ModelStore(tmp_path / "models")
    directory = store.root / "llm"
    directory.mkdir()
    outside = tmp_path / "outside.gguf"
    payload = b"GGUF" + struct.pack("<IQQ", 3, 1, 1) + b"model"
    outside.write_bytes(payload)
    if shape == "external":
        path = outside
    elif shape == "symlink":
        path = directory / "linked.gguf"
        path.symlink_to(outside)
    elif shape == "wrong_suffix":
        path = directory / "model.bin"
        path.write_bytes(payload)
    else:
        path = directory
        for name in ("a.gguf", "b.gguf"):
            (path / name).write_bytes(payload)
    model = InstalledModel(id="my-llm", task=Task.LLM, path=str(path), version="1")
    store.register([model])
    jobs = JobManager(EventBus())
    try:
        assert not Setup(store, jobs)._model(model)[0]
    finally:
        jobs.shutdown()


def test_llm_completed_install_is_reusable_offline(tmp_path, monkeypatch):
    store = ModelStore(tmp_path)
    root = store.root / "llm/qwen3-4b-q4-k-m"
    metadata = root / "metadata"
    metadata.mkdir(parents=True)
    weights = root / local_llm.MODEL_FILE
    weights.write_bytes(b"GGUFcomplete")
    monkeypatch.setattr(local_llm, "MODEL_SIZE", weights.stat().st_size)
    monkeypatch.setattr(local_llm, "MODEL_SHA256", hashlib.sha256(weights.read_bytes()).hexdigest())
    notices = []
    for name in ("LICENSE", "README.md"):
        (metadata / name).write_bytes(b"notice")
        notices.append({"file": name, "sha256": hashlib.sha256(b"notice").hexdigest()})
    source = {"repository": local_llm.MODEL_REPO, "revision": local_llm.MODEL_REVISION,
              "sha256": local_llm.MODEL_SHA256, "size_bytes": local_llm.MODEL_SIZE,
              "notices": notices}
    (metadata / "SOURCE.json").write_text(json.dumps(source))
    monkeypatch.setattr(local_llm.httpx, "Client", lambda *a, **kw: pytest.fail("network"))
    monkeypatch.setattr(local_llm, "download", lambda *a, **kw: pytest.fail("redownload"))
    result = local_llm.install_model(store, consent=True)
    assert result.id == local_llm.MODEL_ID and store.default_for(Task.LLM).id == result.id


def test_healthy_store_setup_is_offline_and_preserves_all_defaults(prepared, monkeypatch):
    client, state, manager, calls = prepared
    defaults = {}
    for task in (Task.ASR, Task.VAD, Task.LLM):
        path = state.store.root / f"mine-{task.value}"
        path.write_bytes(b"healthy")
        model = InstalledModel(id=path.name, task=task, version="1", path=str(path))
        state.store.register([model])
        defaults[task.value] = model.id
    monkeypatch.setattr(setup_backend.importlib, "import_module", lambda n: pytest.fail("unneeded dependency import"))
    with client:
        assert client.get("/v1/setup").json()["ready"]
        job = wait_job(state, client.post("/v1/setup:start", json={"consent": True}).json()["id"])
        assert job.status == "done" and calls == []
        assert state.store.load().defaults == defaults


def test_registry_wrong_task_cannot_report_ready(tmp_path):
    store = ModelStore(tmp_path)
    path = tmp_path / "not-an-asr.gguf"
    path.write_bytes(b"GGUF" + struct.pack("<IQQ", 3, 1, 1))
    model = InstalledModel(id="wrong", task=Task.LLM, version="1", path=str(path))
    store.register([model])
    registry = store.load()
    registry.defaults["asr"] = model.id
    store._save(registry)
    jobs = JobManager(EventBus())
    try:
        manager = Setup(store, jobs)
        assert manager._default(Task.ASR) is None
    finally:
        jobs.shutdown()
