"""Jonli integratsiya tekshiruvida topilgan UI <-> engine xatolari uchun regressiya testlari."""

from pathlib import Path

import pytest
from _api_helpers import TOKEN, make_client, seed_episode
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from lahza_engine.api.app import create_app
from lahza_engine.config import Settings
from lahza_engine.db import store as db


def _clip_id(c: TestClient, eid: str) -> str:
    return c.post(f"/v1/episodes/{eid}/clips",
                  json={"start_sentence_id": 1, "end_sentence_id": 3}).json()["id"]


def test_patch_clip_validation(tmp_path: Path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    _, eid, pdir = seed_episode(st, tmp_path)
    cid = _clip_id(c, eid)
    # Noma'lum klip - 404 (avval jim 200 qaytardi).
    assert c.patch(f"/v1/episodes/{eid}/clips/yoq", json={"title": "x"}).status_code == 404
    # Noto'g'ri status - 422 (avval sqlite CHECK -> 500 va ulanish uzilardi).
    assert c.patch(f"/v1/episodes/{eid}/clips/{cid}", json={"status": "bad"}).status_code == 422
    # Teskari chegaralar - 400.
    clip = next(x for x in c.get(f"/v1/episodes/{eid}/clips").json() if x["id"] == cid)
    r = c.patch(f"/v1/episodes/{eid}/clips/{cid}", json={"end_ms": clip["start_ms"]})
    assert r.status_code == 400
    # To'g'ri tahrir saqlanadi, status feedback'ga yoziladi.
    assert c.patch(f"/v1/episodes/{eid}/clips/{cid}",
                   json={"status": "qabul", "title": "Yangi"}).json() == {"ok": True}
    conn = db.open_project(pdir)
    got = db.get_clip(conn, eid, cid)
    conn.close()
    assert got is not None and got.status.value == "qabul" and got.title == "Yangi"


def test_ws_bad_token_closes_with_4401(tmp_path: Path, monkeypatch) -> None:
    c, _ = make_client(tmp_path, monkeypatch)
    with c.websocket_connect("/v1/events?t=notogri") as ws, pytest.raises(WebSocketDisconnect) as e:
        ws.receive_json()
    assert e.value.code == 4401


@pytest.mark.parametrize("origin, dev, allowed", [
    ("tauri://localhost", "0", True),
    ("http://tauri.localhost", "0", True),
    ("http://127.0.0.1:1420", "1", True),
    ("http://127.0.0.1:1420", "0", False),
    ("https://evil.example", "1", False),
])
def test_cors_preflight(tmp_path: Path, monkeypatch, origin: str, dev: str, allowed: bool) -> None:
    """UI (Tauri webview / Vite dev) engine'ga boshqa origin'dan murojaat qiladi: preflight o'tishi shart."""
    monkeypatch.setenv("LAHZA_DEV", dev)
    app = create_app(Settings(data_dir=tmp_path / "d"), token=TOKEN)
    with TestClient(app) as c:
        r = c.options("/v1/health", headers={
            "Origin": origin, "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type"})
        assert (r.status_code == 200) is allowed
        assert (r.headers.get("access-control-allow-origin") == origin) is allowed
        # Token baribir majburiy.
        assert c.get("/v1/health", headers={"Origin": origin}).status_code == 401


def test_uvicorn_has_websocket_backend() -> None:
    """`websockets` engine bog'liqligi: busiz uvicorn /v1/events ni qo'llay olmaydi."""
    from uvicorn.protocols.websockets.auto import AutoWebSocketsProtocol

    assert AutoWebSocketsProtocol is not None
