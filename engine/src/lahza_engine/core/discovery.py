"""Engine'ni topish (discovery) fayli: `<data_dir>/engine.json` (docs/04 "Adobe plaginlari").

`lahza serve --discovery` (yoki `LAHZA_DISCOVERY=1`) ishga tushganda yoziladi; Premiere/After Effects
plaginlari shu faylni o'qib engine'ga ulanadi:

    {"port": 51234, "token": "...", "pid": 4321, "version": "0.1.0", "started_at": "2026-...Z"}

* fayl huquqi 0600 (Windows'da - foydalanuvchi profilining odatiy ACL'i, %LOCALAPPDATA% ichida);
* atomar yozish: shu papkadagi vaqtinchalik fayl + `os.replace`;
* to'xtaganda o'chiriladi - faqat fayldagi pid o'zimizniki bo'lsa (boshqa engine faylini o'chirmaymiz);
* eski fayl (pid o'lik) ustiga yoziladi; tirik boshqa engine fayli ham ustiga yoziladi (oxirgisi
  ustun) - ogohlantirish logga.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DISCOVERY_FILE = "engine.json"
DISCOVERY_PORTS = (47600, 47601, 47602)
"""`--discovery` rejimidagi qat'iy portlar (UXP manifest `network.domains` ularni oldindan sanaydi)."""


def port_free(port: int, host: str = "127.0.0.1") -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if sys.platform != "win32":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # uvicorn ham shunday bind qiladi
        try:
            s.bind((host, port))
        except OSError:
            return False
    return True


def pick_discovery_port(ports: tuple[int, ...] = DISCOVERY_PORTS) -> int | None:
    """Birinchi bo'sh port (tartib bilan); hammasi band - None."""
    return next((p for p in ports if port_free(p)), None)


def discovery_enabled(flag: bool = False) -> bool:
    return flag or os.environ.get("LAHZA_DISCOVERY", "").strip().lower() in ("1", "true", "yes")


def discovery_path(data_dir: Path) -> Path:
    return Path(data_dir) / DISCOVERY_FILE


def pid_alive(pid: int) -> bool:
    """Jarayon tirikmi (o'z huquqimiz bo'lmasa ham - tirik deb hisoblanadi)."""
    if pid <= 0:
        return False
    if sys.platform == "win32":  # pragma: no cover - Windows'da tekshiriladi
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def read_discovery(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_discovery(path: Path, port: int, token: str, version: str, pid: int | None = None
                    ) -> dict[str, Any]:
    """Faylni atomar yozadi (0600). Qaytaradi: yozilgan ma'lumot."""
    path = Path(path)
    pid = os.getpid() if pid is None else pid
    old = read_discovery(path)
    if old and isinstance(old.get("pid"), int) and old["pid"] != pid and pid_alive(old["pid"]):
        log.warning("engine.json: boshqa tirik engine (pid %s) fayli ustiga yozilmoqda", old["pid"])
    data = {"port": int(port), "token": token, "pid": pid, "version": version,
            "started_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".engine-", suffix=".json.tmp", dir=path.parent)
    try:
        if sys.platform != "win32":
            os.fchmod(fd, 0o600)  # mkstemp allaqachon 0600, umask'dan qat'i nazar aniq
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    return data


def remove_discovery(path: Path, pid: int | None = None) -> bool:
    """Faylni o'chiradi, faqat u shu pid'niki bo'lsa. Takroriy chaqiruv xavfsiz."""
    path = Path(path)
    pid = os.getpid() if pid is None else pid
    data = read_discovery(path)
    if data is None or data.get("pid") != pid:
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


class Discovery:
    """`serve` uchun: yozish va chiqishda (atexit, SIGHUP, lifespan, finally) o'chirish."""

    def __init__(self, data_dir: Path, port: int, token: str, version: str) -> None:
        self.path = discovery_path(data_dir)
        self.port, self.token, self.version = port, token, version
        self.pid = os.getpid()

    def start(self) -> dict[str, Any]:
        import atexit

        data = write_discovery(self.path, self.port, self.token, self.version, self.pid)
        atexit.register(self.stop)
        self._install_signals()
        return data

    def stop(self) -> None:
        with contextlib.suppress(OSError):
            remove_discovery(self.path, self.pid)

    def _install_signals(self) -> None:
        """SIGINT/SIGTERM'ni uvicorn o'zi ushlaydi (graceful -> lifespan/finally). SIGHUP'da
        (terminal yopildi) faylni o'chirib, odatiy xatti-harakatga qaytamiz."""
        import signal

        sighup = getattr(signal, "SIGHUP", None)
        if sighup is None:
            return

        def on_hup(signum, _frame) -> None:
            self.stop()
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)

        with contextlib.suppress(ValueError):  # asosiy oqim emas
            signal.signal(sighup, on_hup)
