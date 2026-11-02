"""Windows: `--watch-stdin` kuzatuvchisi bola jarayonlarni osiltirmaydi va EOF'da ishlaydi."""
from __future__ import annotations

import subprocess
import sys
import textwrap
import threading
import time

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows pipe xatti-harakati")

CHILD = textwrap.dedent("""
    import subprocess, sys, threading
    from lahza_engine.core import lifecycle
    fired = threading.Event()
    lifecycle.ParentWatchdog(lambda r: fired.set(), watch_stdin=True, interval_s=0.1).start()
    out = subprocess.run([sys.executable, "-c", "print('sub')"], capture_output=True, text=True, timeout=20)
    print("sub:" + out.stdout.strip(), flush=True)
    print("fired" if fired.wait(20) else "not-fired", flush=True)
""")


def test_stdin_watchdog_does_not_hang_children_and_fires_on_eof():
    """Bloklovchi `os.read(stdin)` bo'lsa nevara jarayon CRT ishga tushishida osilib qolardi."""
    proc = subprocess.Popen([sys.executable, "-c", CHILD], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    lines: list[str] = []
    threading.Thread(target=lambda: lines.extend(proc.stdout), daemon=True).start()
    try:
        deadline = time.monotonic() + 30
        while not lines and time.monotonic() < deadline:
            time.sleep(0.05)
        assert lines and lines[0].strip() == "sub:sub"  # stdin hali ochiq - subprocess ishladi
        proc.stdin.close()  # ota yopildi -> EOF
        proc.wait(timeout=30)
        assert [ln.strip() for ln in lines] == ["sub:sub", "fired"]
    finally:
        if proc.poll() is None:
            proc.kill()
