"""Lokal alfa modelini UI'dan o'rnatish: rozilik, navbat, bekor qilish."""

import threading

from _api_helpers import make_client, wait_job

from lahza_engine.models.catalog import Task
from lahza_engine.models.store import InstalledModel


def test_bootstrap_requires_auth_and_consent(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    with client:
        assert client.post("/v1/models:bootstrap", json={}).status_code == 400
        assert client.post("/v1/models:bootstrap", json={"consent": True, "entry_ids": []}).status_code == 400
        client.headers.pop("Authorization")
        assert client.post("/v1/models:bootstrap", json={"consent": True}).status_code == 401


def test_bootstrap_registers_without_catalog_approval(tmp_path, monkeypatch):
    client, state = make_client(tmp_path, monkeypatch)

    def fake_bootstrap(store, *, consent, progress):
        assert consent is True
        progress(5, 10)
        model = InstalledModel(id="local-baseline", task=Task.ASR, version="test",
                               path=str(store.root / "baseline"), source="custom", verified=False)
        store.register([model])
        return model

    monkeypatch.setattr("lahza_engine.models.local_bootstrap.bootstrap", fake_bootstrap)
    with client:
        response = client.post("/v1/models:bootstrap", json={"consent": True})
        assert response.status_code == 200
        job = wait_job(state, response.json()["id"])
        assert job.status == "done"
        assert job.result == {"installed": ["local-baseline"], "catalog_approved": False}
        assert state.store.default_for(Task.ASR).verified is False
        assert state._services is None


def test_bootstrap_failure_does_not_claim_installed(tmp_path, monkeypatch):
    client, state = make_client(tmp_path, monkeypatch)

    def failed(*args, **kwargs):
        raise OSError("download unavailable")

    monkeypatch.setattr("lahza_engine.models.local_bootstrap.bootstrap", failed)
    with client:
        response = client.post("/v1/models:bootstrap", json={"consent": True})
        job = wait_job(state, response.json()["id"])
        assert job.status == "failed"
        assert state.store.load().models == []


def test_bootstrap_cancel_stops_before_registration(tmp_path, monkeypatch):
    client, state = make_client(tmp_path, monkeypatch)
    started, release = threading.Event(), threading.Event()

    def downloading(store, *, consent, progress):
        started.set()
        if not release.wait(5):
            raise TimeoutError("test release")
        progress(1, 2)
        raise AssertionError("cancelled progress must stop registration")

    monkeypatch.setattr("lahza_engine.models.local_bootstrap.bootstrap", downloading)
    with client:
        response = client.post("/v1/models:bootstrap", json={"consent": True})
        jid = response.json()["id"]
        try:
            assert started.wait(5)
            state.jobs.cancel(jid)
        finally:
            release.set()
        assert wait_job(state, jid).status == "cancelled"
        assert state.store.load().models == []
