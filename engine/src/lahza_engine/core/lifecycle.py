"""`serve` jarayonining hayot sikli: tez to'xtash, ota jarayon kuzatuvchisi, bola jarayonlarni tozalash.

Muammo (0.2.1 gacha): ilova yopilgandan keyin `lahza-engine serve` yetim qolardi va SIGTERM'ga
javob bermasdi. Sabablar va himoya qatlamlari - docs/01-arxitektura.md "Engine hayot sikli".

* `ParentWatchdog` - Tauri `--parent-pid <pid> --watch-stdin` bilan ishga tushiradi. Ota jarayon
  o'lsa (force quit, crash, SIGKILL - Rust kodi ishlamaydigan holatlar), stdin pipe EOF bo'ladi
  yoki pid yo'qoladi; engine o'zini to'xtatadi. PyInstaller onefile'da `os.getppid()` bootloaderni
  ko'rsatadi, shuning uchun aniq pid uzatiladi; getppid o'zgarishi (bootloader o'ldirilib, launchd/
  init ga o'tish) ham alohida belgi.
* `arm_hard_exit` - yumshoq to'xtash belgilangan vaqtdan oshsa, bola jarayonlarni o'ldirib `os._exit`.
* `kill_descendants` - ffmpeg, llama-server, yt-dlp kabi bola jarayonlar qolib ketmasin.
"""

from __future__ import annotations

import contextlib
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable

from lahza_engine.core.discovery import pid_alive

log = logging.getLogger(__name__)

WATCH_INTERVAL_S = 1.0
HARD_EXIT_S = 5.0

_hard_exit_lock = threading.Lock()
_hard_exit_armed = False


def _child_map() -> dict[int, list[int]]:
    """ppid -> [pid] (POSIX, `ps` orqali; xato bo'lsa bo'sh)."""
    try:
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True,
                             timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    tree: dict[int, list[int]] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            tree.setdefault(int(parts[1]), []).append(int(parts[0]))
    return tree


def descendants(pid: int | None = None) -> list[int]:
    """Berilgan (standart: joriy) jarayonning barcha avlodlari, chuqurlik bo'yicha."""
    if sys.platform == "win32":  # pragma: no cover - Windows'da Job Object (Tauri) tozalaydi
        return []
    root = os.getpid() if pid is None else pid
    tree = _child_map()
    out: list[int] = []
    stack = list(tree.get(root, []))
    while stack:
        p = stack.pop()
        out.append(p)
        stack.extend(tree.get(p, []))
    return out


def kill_descendants(sig: int = signal.SIGKILL if hasattr(signal, "SIGKILL") else signal.SIGTERM
                     ) -> int:
    """Barcha avlod jarayonlarga signal (ffmpeg, llama-server, yt-dlp...). Qaytaradi: soni."""
    n = 0
    for p in descendants():
        try:
            os.kill(p, sig)
            n += 1
        except OSError:
            pass
    return n


def _flush_and_exit(code: int) -> None:
    # Windows'da `kill_descendants` bo'sh: issiq llama-server'ni bevosita o'ldiramiz (modul
    # yuklanmagan bo'lsa, server ham yo'q - import qilinmaydi).
    llama = sys.modules.get("lahza_engine.core.llama_server")
    if llama is not None:
        with contextlib.suppress(Exception):
            llama.kill_all()
    kill_descendants()
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):  # pipe yopiq bo'lishi mumkin
            stream.flush()
    os._exit(code)


def arm_hard_exit(timeout_s: float = HARD_EXIT_S, code: int = 0) -> None:
    """`timeout_s` dan keyin jarayon baribir tugaydi (idempotent; daemon oqim)."""
    global _hard_exit_armed
    with _hard_exit_lock:
        if _hard_exit_armed:
            return
        _hard_exit_armed = True

    def run() -> None:
        time.sleep(timeout_s)
        log.warning("yumshoq to'xtash %.1f s dan oshdi - majburiy chiqish", timeout_s)
        _flush_and_exit(code)

    threading.Thread(target=run, name="hard-exit", daemon=True).start()


def finish(code: int = 0) -> None:
    """`serve` oxiri: bola jarayonlarni o'ldirib, non-daemon oqimlarni (ThreadPool) kutmasdan chiqish."""
    logging.shutdown()
    _flush_and_exit(code)


class ParentWatchdog:
    """Ota jarayon yo'qolsa `on_lost(reason)` ni bir marta chaqiradi (daemon oqimlar)."""

    def __init__(self, on_lost: Callable[[str], None], parent_pid: int | None = None,
                 watch_stdin: bool = False, interval_s: float = WATCH_INTERVAL_S) -> None:
        self.on_lost = on_lost
        self.parent_pid = parent_pid
        self.watch_stdin = watch_stdin
        self.interval_s = interval_s
        self._initial_ppid = os.getppid()
        self._fired = threading.Event()

    def _fire(self, reason: str) -> None:
        if self._fired.is_set():
            return
        self._fired.set()
        log.warning("ota jarayon yo'qoldi (%s) - engine to'xtatilmoqda", reason)
        self.on_lost(reason)

    def start(self) -> None:
        threading.Thread(target=self._poll, name="parent-watchdog", daemon=True).start()
        if self.watch_stdin:
            threading.Thread(target=self._stdin, name="stdin-watchdog", daemon=True).start()

    def _poll(self) -> None:
        while not self._fired.is_set():
            if self.parent_pid and not pid_alive(self.parent_pid):
                self._fire(f"pid {self.parent_pid} yo'q")
                return
            # Bevosita ota (onefile'da bootloader) o'ldirilsa, jarayon init/launchd ga o'tadi.
            if sys.platform != "win32" and self._initial_ppid > 1 and os.getppid() != self._initial_ppid:
                self._fire("ppid o'zgardi")
                return
            time.sleep(self.interval_s)

    def _stdin(self) -> None:
        try:
            fd = sys.stdin.fileno() if sys.stdin is not None else -1
        except (OSError, ValueError):
            fd = -1
        if fd < 0:
            return
        if sys.platform == "win32":
            self._stdin_win32(fd)
            return
        try:
            while os.read(fd, 4096):
                pass  # ota hech narsa yozmaydi; faqat EOF kutiladi
        except OSError:
            pass
        self._fire("stdin EOF")

    def _stdin_win32(self, fd: int) -> None:
        """Windows: stdin pipe'ni bloklovchi o'qishsiz kuzatish (PeekNamedPipe so'rovi).

        Sinxron pipe'da tugamagan `ReadFile` turganda shu handle'ni meros qilgan har bir bola
        jarayon (ffmpeg, PyInstaller sidecar ichidagi `subprocess.run`) CRT ishga tushishida
        (`GetFileType`) osilib qoladi - engine `--watch-stdin` bilan umuman ko'tarilmasdi."""
        import _winapi
        import msvcrt

        try:
            handle = msvcrt.get_osfhandle(fd)
        except OSError:
            return
        while not self._fired.is_set():
            try:
                _winapi.PeekNamedPipe(handle, 0)
            except BrokenPipeError:
                break  # ota pipe'ni yopdi (EOF)
            except OSError:
                return  # stdin pipe emas (konsol, NUL, fayl) - kuzatib bo'lmaydi
            time.sleep(self.interval_s)
        self._fire("stdin EOF")
