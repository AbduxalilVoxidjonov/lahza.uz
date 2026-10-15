from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lahza_engine.api.app import create_app
from lahza_engine.config import Settings

TOKEN = "test-token"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LAHZA_DEV", "1")
    app = create_app(Settings(data_dir=tmp_path), token=TOKEN)
    with TestClient(app) as c:
        c.headers["Authorization"] = f"Bearer {TOKEN}"
        yield c


def test_auth_required(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path), token=TOKEN)
    with TestClient(app) as c:
        assert c.get("/v1/health").status_code == 401
        assert c.get("/v1/health", params={"t": TOKEN}).status_code == 200


def test_projects_flow(client: TestClient) -> None:
    p = client.post("/v1/projects", json={"name": "Biznes podkast"}).json()
    assert client.get("/v1/projects").json()[0]["id"] == p["id"]
    assert client.get(f"/v1/projects/{p['id']}/episodes").json() == []
    r = client.post("/v1/media:import", json={"project_id": p["id"], "path": "/yoq/fayl.mp4"})
    assert r.status_code == 400


def test_hardware_and_bundle(client: TestClient) -> None:
    hw = client.get("/v1/hardware").json()
    assert "tier" in hw and "profile" in hw
    b = client.get("/v1/catalog/bundle").json()
    tasks = {i["task"] for i in b["items"]}
    assert {"asr", "llm"} <= tasks


def test_install_requires_consent(client: TestClient) -> None:
    assert client.post("/v1/models:install", json={}).status_code == 400


def test_unknown_job_and_ws_auth(client: TestClient) -> None:
    assert client.get("/v1/jobs/yoq").status_code == 404
    with pytest.raises(Exception), client.websocket_connect("/v1/events?t=notogri") as ws:  # noqa: B017
        ws.receive_json()
