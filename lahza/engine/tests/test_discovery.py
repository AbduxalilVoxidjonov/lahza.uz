"""Engine discovery (`<data_dir>/engine.json`): yozish (0600, atomar), o'chirish, eski fayl, `serve --discovery`."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lahza_engine import __version__
from lahza_engine.core import discovery as d


@pytest.fixture(autouse=True)
def _keep_signals(monkeypatch):
    """Discovery.start SIGHUP ishlovchisini o'rnatadi - test jarayonida asl holatga qaytaramiz;
    serve testlari global fayl logini yoqmasin."""
    import signal

    from lahza_engine.core import logs

    monkeypatch.setattr(logs, "setup_file_logging", lambda *_a, **_k: None)
    hup = getattr(signal, "SIGHUP", None)
    old = signal.getsignal(hup) if hup is not None else None
    yield
    if hup is not None:
        signal.signal(hup, old)


def _dead_pid() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def test_write_read_permissions_and_atomic(tmp_path):
    path = d.discovery_path(tmp_path / "data")
    data = d.write_discovery(path, 51234, "tok", "0.1.0")
    assert json.loads(path.read_text()) == data
    assert set(data) == {"port", "token", "pid", "version", "started_at"}
    assert data["pid"] == os.getpid() and data["started_at"].endswith("Z")
    if sys.platform != "win32":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert [p.name for p in path.parent.iterdir()] == ["engine.json"]  # vaqtinchalik fayl qolmadi


def test_remove_only_own_pid(tmp_path):
    path = d.discovery_path(tmp_path)
    d.write_discovery(path, 1, "t", "v", pid=os.getpid() + 100000)
    assert d.remove_discovery(path) is False and path.exists()
    d.write_discovery(path, 1, "t", "v")
    assert d.remove_discovery(path) is True and not path.exists()
    assert d.remove_discovery(path) is False  # takroriy chaqiruv xavfsiz


def test_stale_file_overwritten(tmp_path):
    path = d.discovery_path(tmp_path)
    dead = _dead_pid()
    assert not d.pid_alive(dead) and d.pid_alive(os.getpid())
    path.write_text(json.dumps({"port": 1, "token": "eski", "pid": dead}))
    d.write_discovery(path, 2, "yangi", "v")
    assert json.loads(path.read_text())["token"] == "yangi"


def test_enabled_by_env(monkeypatch):
    monkeypatch.delenv("LAHZA_DISCOVERY", raising=False)
    assert not d.discovery_enabled() and d.discovery_enabled(True)
    monkeypatch.setenv("LAHZA_DISCOVERY", "1")
    assert d.discovery_enabled()


@pytest.mark.parametrize("via_env", [False, True])
def test_serve_discovery_writes_and_removes(tmp_path, monkeypatch, via_env):
    from lahza_engine import cli

    monkeypatch.setenv("LAHZA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("LAHZA_TOKEN", raising=False)
    seen: dict = {}

    def fake_run(app, host, port, log_level):
        path = tmp_path / "data" / "engine.json"
        seen.update(json.loads(path.read_text()))
        seen["host"] = host
        seen["hooks"] = len(app.state.shutdown_hooks)
        seen["auth_ok"] = TestClient(app).get(
            "/v1/health", headers={"Authorization": f"Bearer {seen['token']}"}).status_code

    # Haqiqiy server os._exit bilan tugaydi - testda `_run_server` almashtiriladi.
    monkeypatch.setattr(cli, "_run_server",
                        lambda app, port, a, cleanup: fake_run(app, cli.SERVE_HOST, port, "warning"))
    argv = ["serve", "--port", "45678"]
    if via_env:
        monkeypatch.setenv("LAHZA_DISCOVERY", "1")
    else:
        monkeypatch.delenv("LAHZA_DISCOVERY", raising=False)
        argv.append("--discovery")
    assert cli.main(argv) == 0
    assert seen["port"] == 45678 and seen["version"] == __version__ and len(seen["token"]) >= 20
    assert seen["host"] == "127.0.0.1" and seen["hooks"] == 1 and seen["auth_ok"] == 200
    assert not (tmp_path / "data" / "engine.json").exists()  # chiqishda o'chirildi


def test_serve_without_discovery_writes_nothing(tmp_path, monkeypatch):
    from lahza_engine import cli

    monkeypatch.setenv("LAHZA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("LAHZA_DISCOVERY", raising=False)
    monkeypatch.setattr(cli, "_run_server", lambda *a, **k: None)
    assert cli.main(["serve", "--port", "45679", "--token", "x"]) == 0
    assert not (tmp_path / "data" / "engine.json").exists()


def test_lifespan_runs_shutdown_hooks(tmp_path):
    from lahza_engine.api.app import create_app
    from lahza_engine.config import Settings

    app = create_app(Settings(data_dir=tmp_path), token="t")
    path = d.discovery_path(tmp_path)
    d.write_discovery(path, 1, "t", "v")
    app.state.shutdown_hooks.append(lambda: d.remove_discovery(path))
    with TestClient(app):
        assert path.exists()
    assert not path.exists()


def test_discovery_handle_stop_idempotent(tmp_path):
    h = d.Discovery(Path(tmp_path), 5, "tok", "v")
    h.start()
    assert h.path.exists()
    h.stop()
    h.stop()
    assert not h.path.exists()
