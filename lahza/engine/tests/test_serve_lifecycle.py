"""`serve` to'xtashi: SIGTERM, ota jarayon kuzatuvchisi, bola jarayonlar (yetim engine xatosi, 0.2.1).

Haqiqiy subprocess bilan (`python -m lahza_engine serve --port 0`), faqat 127.0.0.1.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX signallari")

STOP_BUDGET_S = 5.0


def _env(tmp_path: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("LAHZA_")}
    env.update(LAHZA_TOKEN="lifecycle-token", LAHZA_DATA_DIR=str(tmp_path / "data"), LAHZA_DEV="0")
    return env


def _serve_cmd(*extra: str) -> list[str]:
    return [sys.executable, "-m", "lahza_engine", "serve", "--port", "0", *extra]


def _wait_ready(proc: subprocess.Popen[bytes], timeout: float = 60.0) -> int:
    assert proc.stdout is not None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = proc.stdout.readline().decode()
        if not line:
            break
        if line.startswith("LAHZA_READY port="):
            return int(line.strip().split("=", 1)[1])
    proc.kill()
    raise AssertionError("engine tayyor bo'lmadi")


def _open_ws(port: int) -> socket.socket:
    deadline = time.monotonic() + 15
    while True:  # LAHZA_READY port bog'lanishidan biroz oldin chiqadi
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=5)
            break
        except ConnectionRefusedError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.1)
    s.sendall((f"GET /v1/events?t=lifecycle-token HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
               "Upgrade: websocket\r\nConnection: Upgrade\r\n"
               "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n"
               ).encode())
    assert s.recv(64).startswith(b"HTTP/1.1 101")
    return s


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # Zombie (hali yig'ilmagan) - tirik emas.
    out = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout
    return bool(out.strip()) and not out.strip().startswith("Z")


def _wait_dead(pid: int, timeout: float) -> float | None:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if not _alive(pid):
            return time.monotonic() - t0
        time.sleep(0.05)
    return None


@pytest.mark.parametrize("client", ["open", "abandoned"])
def test_sigterm_exits_fast_with_websocket_client(tmp_path, client):
    """WebSocket obunachisi bo'lsa ham SIGTERM'dan keyin engine tez chiqadi (avval abadiy osilardi)."""
    proc = subprocess.Popen(_serve_cmd(), env=_env(tmp_path), stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    ws = None
    try:
        port = _wait_ready(proc)
        ws = _open_ws(port)
        if client == "abandoned":
            ws.close()  # webview o'ldi: TCP yopildi, handler esa hodisa kutmoqda
            ws = None
        time.sleep(0.3)
        t0 = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=STOP_BUDGET_S + 5)
        elapsed = time.monotonic() - t0
        assert elapsed < STOP_BUDGET_S, f"SIGTERM'dan keyin {elapsed:.2f} s"
    finally:
        if ws is not None:
            ws.close()
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_parent_pid_watchdog_stops_engine(tmp_path):
    """Soxta ota (Tauri o'rnida) SIGKILL bilan o'ldirilsa, engine o'zini o'chiradi."""
    parent_code = textwrap.dedent(f"""
        import os, subprocess, sys, time
        p = subprocess.Popen({_serve_cmd()!r} + ["--parent-pid", str(os.getpid())],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        for line in p.stdout:
            if line.startswith(b"LAHZA_READY"):
                print(p.pid, flush=True)
                break
        time.sleep(600)
    """)
    parent = subprocess.Popen([sys.executable, "-c", parent_code], env=_env(tmp_path),
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    engine_pid = None
    try:
        assert parent.stdout is not None
        engine_pid = int(parent.stdout.readline().decode().strip())
        assert _alive(engine_pid)
        parent.kill()
        parent.wait()
        took = _wait_dead(engine_pid, STOP_BUDGET_S)
        assert took is not None, "ota o'lgandan keyin engine tirik qoldi"
    finally:
        if parent.poll() is None:
            parent.kill()
        if engine_pid and _alive(engine_pid):
            os.kill(engine_pid, signal.SIGKILL)


def test_stdin_eof_watchdog_stops_engine(tmp_path):
    """Tauri stdin pipe'ini ushlab turadi; ota yopilsa EOF - engine chiqadi."""
    proc = subprocess.Popen(_serve_cmd("--watch-stdin"), env=_env(tmp_path), stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, stdin=subprocess.PIPE)
    try:
        port = _wait_ready(proc)
        ws = _open_ws(port)  # obunachi bo'lsa ham
        assert proc.stdin is not None
        time.sleep(1.5)
        assert proc.poll() is None  # EOF bo'lmaguncha ishlayveradi
        t0 = time.monotonic()
        proc.stdin.close()
        proc.wait(timeout=STOP_BUDGET_S + 5)
        assert time.monotonic() - t0 < STOP_BUDGET_S
        ws.close()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_kill_descendants_leaves_no_children(tmp_path):
    """`finish` yo'li: nevaralar (ffmpeg/llama-server o'rnida `sleep`) qolmaydi."""
    code = textwrap.dedent("""
        import subprocess, sys
        from lahza_engine.core import lifecycle
        kid = subprocess.Popen(["/bin/sh", "-c", "sleep 600 & wait"])
        import time; time.sleep(0.5)
        print(" ".join(str(p) for p in lifecycle.descendants()), flush=True)
        lifecycle.finish(0)
    """)
    r = subprocess.run([sys.executable, "-c", code], env=_env(tmp_path), capture_output=True,
                       text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    pids = [int(p) for p in r.stdout.split()]
    assert len(pids) >= 2  # sh + sleep
    for pid in pids:
        assert _wait_dead(pid, 3.0) is not None, f"bola jarayon {pid} qoldi"


def test_hard_exit_after_timeout(tmp_path):
    """Yumshoq to'xtash osilib qolsa ham `arm_hard_exit` jarayonni tugatadi."""
    code = textwrap.dedent("""
        import threading, time
        from lahza_engine.core import lifecycle
        threading.Thread(target=lambda: time.sleep(600)).start()  # non-daemon: odatda chiqishni to'sadi
        lifecycle.arm_hard_exit(0.5, code=7)
        lifecycle.arm_hard_exit(0.5, code=9)  # idempotent
    """)
    t0 = time.monotonic()
    r = subprocess.run([sys.executable, "-c", code], env=_env(tmp_path), capture_output=True,
                       text=True, timeout=30)
    assert r.returncode == 7, r.stderr
    assert time.monotonic() - t0 < 10


def test_watchdog_active_during_startup(tmp_path):
    """Ota engine yuklanayotganda o'lsa ham (stdin darhol EOF) engine o'zi chiqadi."""
    t0 = time.monotonic()
    r = subprocess.run(_serve_cmd("--watch-stdin"), env=_env(tmp_path), stdin=subprocess.DEVNULL,
                       capture_output=True, timeout=60)
    assert r.returncode == 0
    assert time.monotonic() - t0 < 30
