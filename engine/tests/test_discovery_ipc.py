"""Fayl-IPC (`lahza.ipc/1`) va `--discovery` rejimining qat'iy portlari (47600..47602)."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import stat
import sys
import time
from pathlib import Path

import pytest

from lahza_engine.api.app import create_app
from lahza_engine.config import Settings
from lahza_engine.core import discovery as d
from lahza_engine.core import ipc

TOKEN = "ipc-token"


def _server(tmp_path: Path) -> ipc.IpcServer:
    app = create_app(Settings(data_dir=tmp_path / "data"), token=TOKEN)
    srv = ipc.IpcServer(app, tmp_path / "data")
    srv.prepare()
    return srv


def _put(srv: ipc.IpcServer, rid: str, req: dict | bytes) -> Path:
    data = req if isinstance(req, bytes) else json.dumps(req).encode()
    tmp = srv.req_dir / f"{rid}.json.tmp"
    tmp.write_bytes(data)
    final = srv.req_dir / f"{rid}.json"
    os.replace(tmp, final)
    return final


def _req(rid: str, path: str = "/v1/hostplan/schema", token: str = TOKEN, method: str = "GET",
         body=None) -> dict:
    return {"v": 1, "id": rid, "method": method, "path": path,
            "headers": {"Authorization": f"Bearer {token}"}, "body": body,
            "created_at": "2026-10-22T10:00:00.000Z"}


def _run(srv: ipc.IpcServer) -> None:
    async def go():
        tasks = await srv.tick()
        await asyncio.gather(*tasks)

    asyncio.run(go())


def _resp(srv: ipc.IpcServer, rid: str) -> dict:
    return json.loads((srv.res_dir / f"{rid}.json").read_text(encoding="utf-8"))


def test_request_response_roundtrip(tmp_path):
    srv = _server(tmp_path)
    if sys.platform != "win32":
        for p in (srv.root, srv.req_dir, srv.res_dir):
            assert stat.S_IMODE(p.stat().st_mode) == 0o700
    req_file = _put(srv, "abcdef12-ok", _req("abcdef12-ok"))
    (srv.req_dir / "pending01.json.tmp").write_text("{")  # yozilayotgan - e'tiborsiz
    _run(srv)
    assert not req_file.exists() and (srv.req_dir / "pending01.json.tmp").exists()
    r = _resp(srv, "abcdef12-ok")
    assert r == {"v": 1, "id": "abcdef12-ok", "status": 200,
                 "body": {"schema": "lahza.hostplan/1", "engine": r["body"]["engine"]}}
    assert not list(srv.res_dir.glob("*.tmp"))


def test_post_body_and_validation_errors_pass_through(tmp_path):
    srv = _server(tmp_path)
    _put(srv, "post0001", _req("post0001", "/v1/projects", method="POST", body={"name": "Premiere"}))
    _put(srv, "post0002", _req("post0002", "/v1/projects", method="POST", body={"name": "  "}))
    _run(srv)
    assert _resp(srv, "post0001")["status"] == 200 and _resp(srv, "post0001")["body"]["name"] == "Premiere"
    assert _resp(srv, "post0002") == {"v": 1, "id": "post0002", "status": 400,
                                      "body": {"detail": "loyiha nomi bo'sh"}}


def test_wrong_token_gives_401_response(tmp_path):
    srv = _server(tmp_path)
    _put(srv, "badtoken1", _req("badtoken1", token="notogri"))
    _run(srv)
    r = _resp(srv, "badtoken1")
    assert r["status"] == 401 and r["body"] == {"detail": "token noto'g'ri"}


@pytest.mark.parametrize("name", ["short.json", "bad_id_under.json", "x.y12345678.json", "a" * 65 + ".json",
                                  "noext12345"])
def test_invalid_id_rejected_without_response(tmp_path, name):
    srv = _server(tmp_path)
    p = srv.req_dir / Path(name).name
    p.write_text(json.dumps(_req("whatever1")))
    _run(srv)
    assert not p.exists() and not list(srv.res_dir.iterdir())


def test_large_and_malformed_requests(tmp_path):
    srv = _server(tmp_path)
    _put(srv, "bigfile01", b"{" + b" " * (ipc.MAX_REQUEST_BYTES + 1) + b"}")
    _put(srv, "notjson01", b"salom")
    _put(srv, "mismatch1", _req("boshqa-id"))
    _put(srv, "badpath01", _req("badpath01", path="/boshqa"))
    _put(srv, "oldver001", {**_req("oldver001"), "v": 2})
    _run(srv)
    assert _resp(srv, "bigfile01")["status"] == 413
    assert {r: _resp(srv, r)["status"] for r in ("notjson01", "mismatch1", "badpath01", "oldver001")} == \
        {"notjson01": 400, "mismatch1": 400, "badpath01": 400, "oldver001": 400}
    assert not list(srv.req_dir.iterdir())


def test_non_json_endpoint_gives_502(tmp_path, monkeypatch):
    srv = _server(tmp_path)
    from fastapi.responses import Response

    srv.app.add_api_route("/v1/_rasm", lambda: Response(b"\xff\xd8", media_type="image/jpeg"))
    _put(srv, "image0001", _req("image0001", "/v1/_rasm"))
    _run(srv)
    r = _resp(srv, "image0001")
    assert r["status"] == 502 and "JSON emas" in r["body"]["detail"]


def test_old_files_cleaned(tmp_path):
    srv = _server(tmp_path)
    old = time.time() - ipc.MAX_AGE_S - 10
    stale = [srv.res_dir / "eski0001.json", srv.req_dir / "eski0002.json.tmp"]
    for p in stale:
        p.write_text("{}")
        os.utime(p, (old, old))
    fresh = srv.res_dir / "yangi001.json"
    fresh.write_text("{}")
    assert srv.cleanup() == 2
    assert not any(p.exists() for p in stale) and fresh.exists()


def test_background_loop_runs_in_server_lifespan(tmp_path):
    from fastapi.testclient import TestClient

    srv = _server(tmp_path)
    srv.poll_s = 0.02
    srv.app.state.background.append(srv.run)
    _put(srv, "lifespan1", _req("lifespan1"))
    with TestClient(srv.app):
        end = time.time() + 5
        while time.time() < end and not (srv.res_dir / "lifespan1.json").exists():
            time.sleep(0.02)
    assert _resp(srv, "lifespan1")["status"] == 200


# ---- Qat'iy portlar ----------------------------------------------------------------------


def test_pick_discovery_port_skips_busy():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        taken = busy.getsockname()[1]
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            free = probe.getsockname()[1]
        assert d.pick_discovery_port((taken, free)) == free
        assert d.pick_discovery_port((taken,)) is None


@pytest.fixture
def serve_env(tmp_path, monkeypatch):
    import signal

    import uvicorn

    from lahza_engine.core import logs

    monkeypatch.setattr(logs, "setup_file_logging", lambda *_a, **_k: None)
    monkeypatch.setenv("LAHZA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("LAHZA_DISCOVERY", raising=False)
    monkeypatch.delenv("LAHZA_IPC", raising=False)
    seen: dict = {}

    def fake_run(app, host, port, log_level):
        seen["port"] = port
        seen["background"] = len(app.state.background)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    hup = getattr(signal, "SIGHUP", None)
    old = signal.getsignal(hup) if hup is not None else None
    yield seen
    if hup is not None:
        signal.signal(hup, old)


def test_serve_discovery_fixed_ports(serve_env, monkeypatch, capsys):
    from lahza_engine import cli

    busy = {47600}
    monkeypatch.setattr(d, "port_free", lambda p, host="127.0.0.1": p not in busy)
    assert cli.main(["serve", "--discovery"]) == 0
    assert serve_env["port"] == 47601 and serve_env["background"] == 1  # IPC yoqilgan
    busy |= {47601, 47602}
    serve_env.clear()
    assert cli.main(["serve", "--discovery"]) == 2
    assert "port" not in serve_env
    assert "47600, 47601 va 47602" in capsys.readouterr().err


def test_serve_sidecar_mode_unchanged(serve_env, monkeypatch):
    from lahza_engine import cli

    monkeypatch.setattr(d, "port_free", lambda *_a, **_k: pytest.fail("sidecar rejimida chaqirilmasin"))
    assert cli.main(["serve", "--port", "0", "--token", "t"]) == 0
    assert serve_env["background"] == 0  # IPC o'chiq
    monkeypatch.setenv("LAHZA_IPC", "1")
    assert cli.main(["serve", "--port", "45001", "--token", "t"]) == 0
    assert serve_env["port"] == 45001 and serve_env["background"] == 1
