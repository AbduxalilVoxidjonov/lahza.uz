"""llama.cpp `llama-server` jarayonini boshqarish.

Highlight serveri vazifa davomida ishlaydi va tugagach to'xtatiladi - GPU xotirasini tejash
uchun modellar ketma-ket yuklanadi (TZ 4-bo'lim, "Resurs boshqaruvi"). Montaj rejasi esa
`WarmLlamaServer` orqali issiq serverni qayta ishlatadi (yuklash + system prompt keshi);
bo'sh turgan issiq server slotni boshqa LLM so'rasa darhol bo'shatadi.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import threading
import time
import weakref
from collections.abc import Callable, Hashable, Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Protocol

import httpx

from lahza_engine.media.tools import find_tool

log = logging.getLogger(__name__)

_LLM_LOCK = threading.Lock()
IDLE_ENV = "LAHZA_LLM_IDLE_S"
DEFAULT_IDLE_S = 300.0

# Ishlab turgan barcha llama-server jarayonlari: `lifecycle` majburiy chiqishda o'ldiradi.
_LIVE: set[subprocess.Popen[bytes]] = set()
_LIVE_LOCK = threading.Lock()
_WARM_POOLS: weakref.WeakSet[WarmLlamaServer] = weakref.WeakSet()
_JOB: int | None = None  # None - hali yaratilmagan, 0 - yaratib bo'lmadi
_JOB_LOCK = threading.Lock()


class LlamaServerBusy(RuntimeError):
    """Another managed LLM owns the process-wide GPU slot; retry when it finishes."""


def idle_timeout_s() -> float:
    """Issiq server bo'sh turish muddati (`LAHZA_LLM_IDLE_S`, standart 300 s; 0 - o'chiq)."""
    raw = os.environ.get(IDLE_ENV, "").strip()
    try:
        value = float(raw) if raw else DEFAULT_IDLE_S
    except ValueError:
        return DEFAULT_IDLE_S
    if value != value:  # NaN
        return DEFAULT_IDLE_S
    return max(0.0, value)


def _kill_on_close_job() -> int | None:
    """Windows: engine yopilganda (hatto TerminateProcess/crash) bolalarni o'ldiradigan Job Object.

    Tauri Job Object'i ilova engine'ni to'xtatganda ishlaydi; engine o'zi yiqilsa yoki
    `os._exit` qilsa (Windows'da `kill_descendants` bo'sh) issiq llama-server yetim qolmasin.
    Handle ataylab yopilmaydi: engine tugaganda OS yopadi va job ichidagilar o'ladi."""
    global _JOB
    with _JOB_LOCK:
        if _JOB is not None:
            return _JOB or None
        _JOB = 0
        import ctypes
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD), ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", ctypes.c_uint64 * 6),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                                                wintypes.DWORD]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        # 9 = JobObjectExtendedLimitInformation
        if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            k32.CloseHandle(job)
            return None
        _JOB = int(job)
        return _JOB


def _bind_to_engine(proc: subprocess.Popen[bytes]) -> None:
    """Jarayonni engine umriga bog'lash (Windows Job Object); xato bo'lsa jim o'tadi."""
    handle = getattr(proc, "_handle", None)
    if sys.platform != "win32" or not isinstance(handle, int):
        return
    try:
        import ctypes
        from ctypes import wintypes

        job = _kill_on_close_job()
        if job is None:
            return
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        if not k32.AssignProcessToJobObject(job, handle):
            log.debug("llama-server Job Object'ga qo'shilmadi: %s", ctypes.get_last_error())
    except (OSError, AttributeError, TypeError, ValueError) as exc:
        log.debug("Job Object xatosi: %s", exc)


def kill_all() -> None:
    """Majburiy chiqish (`lifecycle`) uchun: tirik llama-server'larni kutmasdan o'ldiradi."""
    with _LIVE_LOCK:
        procs = list(_LIVE)
    for proc in procs:
        with suppress(OSError):
            proc.kill()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class LlamaServer:
    def __init__(self, model_path: Path, ctx_size: int = 16384, gpu_layers: int = 999,
                 startup_timeout_s: float = 180.0, parallel: int = 1,
                 thinking: bool | None = None, cache_ram_mib: int | None = None) -> None:
        """`ctx_size` - jami kontekst; llama-server uni `parallel` slotga teng bo'ladi.
        `thinking=False` - server darajasida "o'ylash"ni o'chiradi (`--reasoning-budget 0`),
        None - model standarti. `cache_ram_mib` - `--cache-ram` (RAM'dagi qo'shimcha prompt
        keshi chegarasi; None - llama.cpp standarti, b11669 da 8192 MiB)."""
        self.model_path = model_path
        self.ctx_size = ctx_size
        self.gpu_layers = gpu_layers
        self.startup_timeout_s = startup_timeout_s
        self.parallel = max(1, parallel)
        self.thinking = thinking
        self.cache_ram_mib = cache_ram_mib
        self.proc: subprocess.Popen[bytes] | None = None
        self.port = 0
        self._owns_llm_lock = False

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> str:
        # Slotni bo'sh turgan issiq server (montaj rejasi) band qilgan bo'lsa, u bo'shatiladi.
        if not (_LLM_LOCK.acquire(blocking=False)
                or (evict_idle_servers() and _LLM_LOCK.acquire(blocking=False))):
            raise LlamaServerBusy("Local LLM is busy with another request; retry after it finishes")
        self._owns_llm_lock = True
        try:
            self.port = free_port()
            exe = find_tool("llama-server")
            flags = 0x08000000 if sys.platform == "win32" else 0
            args = [str(exe), "-m", str(self.model_path), "--host", "127.0.0.1",
                    "--port", str(self.port), "-c", str(self.ctx_size), "-ngl", str(self.gpu_layers),
                    "--parallel", str(self.parallel)]
            if self.thinking is False:
                args += ["--reasoning-budget", "0"]
            if self.cache_ram_mib is not None:
                args += ["--cache-ram", str(self.cache_ram_mib)]
            self.proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags,
            )
            with _LIVE_LOCK:
                _LIVE.add(self.proc)
            _bind_to_engine(self.proc)
            deadline = time.monotonic() + self.startup_timeout_s
            while (remaining := deadline - time.monotonic()) > 0:
                if self.proc.poll() is not None:
                    raise RuntimeError("llama-server ishga tushmadi (model yoki xotira muammosi)")
                try:
                    if httpx.get(f"{self.url}/health", timeout=min(2.0, remaining)).status_code == 200:
                        return self.url
                except httpx.HTTPError:
                    pass
                time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
            raise TimeoutError("llama-server o'z vaqtida tayyor bo'lmadi")
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *exc: object) -> None:
        proc = self.proc
        try:
            if proc is None:
                return
            if proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # Child may exit between the timed wait and kill.
                    with suppress(ProcessLookupError):
                        proc.kill()
                    proc.wait()
                except ProcessLookupError:
                    proc.wait()
            else:
                proc.wait()
        finally:
            if proc is not None:
                with _LIVE_LOCK:
                    _LIVE.discard(proc)
            self.proc = None
            if self._owns_llm_lock:
                self._owns_llm_lock = False
                _LLM_LOCK.release()


class _Server(Protocol):
    def __enter__(self) -> str: ...

    def __exit__(self, *exc: object) -> None: ...


def _alive(server: _Server) -> bool:
    proc = getattr(server, "proc", None)
    return proc is not None and proc.poll() is None


def _stop(server: _Server) -> None:
    with suppress(Exception):  # to'xtatish xatosi chaqiruvchini (shutdown, taymer) yiqitmasin
        server.__exit__(None, None, None)


def evict_idle_servers() -> bool:
    """Bo'sh turgan issiq serverlarni to'xtatadi (slot boshqa LLM'ga kerak). True - biri to'xtadi."""
    return any([pool.evict_idle() for pool in list(_WARM_POOLS)])


def stop_warm_servers() -> None:
    """Engine to'xtashida (lifespan): barcha issiq serverlarni to'xtatish."""
    for pool in list(_WARM_POOLS):
        pool.stop()


class WarmLlamaServer:
    """Bitta issiq `llama-server`: birinchi so'rovda ishga tushadi, oxirgi so'rovdan keyin
    `idle_s()` soniya (standart `LAHZA_LLM_IDLE_S`, 300 s) bo'sh tursa to'xtaydi.

    * bir vaqtda bitta ijara (`lease`) - ikkinchisi `LlamaServerBusy`;
    * kalit (model fayli/parametrlar) o'zgarsa yoki jarayon o'lgan bo'lsa - qayta ishga tushadi;
    * ijara ichida ValueError'dan boshqa xato (HTTP, timeout) - holati noma'lum, server yopiladi;
    * server tirik turgan butun vaqt `_LLM_LOCK` ni ushlaydi (RAM/GPU band), lekin bo'sh
      turganda boshqa `LlamaServer` (highlight) so'rasa `evict_idle` orqali darhol bo'shatadi;
    * `stop()` - engine to'xtashi; davom etayotgan ijara tugashi bilan server yopiladi.
    """

    def __init__(self, idle_s: Callable[[], float] = idle_timeout_s) -> None:
        self._idle_s = idle_s
        self._lock = threading.Lock()  # faqat holat uchun; jarayonni kutish lock tashqarisida
        self._server: _Server | None = None
        self._key: Hashable = None
        self._url = ""
        self._in_use = False
        self._epoch = 0  # stop() oshiradi: o'sha paytdagi ijara oxirida server yopiladi
        self._timer: threading.Timer | None = None
        self._timer_token = 0
        _WARM_POOLS.add(self)

    @property
    def running(self) -> bool:
        with self._lock:
            return self._server is not None

    def _cancel_timer(self) -> None:
        self._timer_token += 1
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _expire(self, token: int) -> None:
        with self._lock:
            if token != self._timer_token or self._in_use or self._server is None:
                return
            server, self._server, self._timer = self._server, None, None
        log.info("issiq llama-server bo'sh turdi - to'xtatildi")
        _stop(server)

    @contextmanager
    def lease(self, key: Hashable, factory: Callable[[], _Server]) -> Iterator[str]:
        """Issiq server URL'i; server yo'q/eskirgan bo'lsa `factory()` bilan ishga tushiradi."""
        with self._lock:
            if self._in_use:
                raise LlamaServerBusy("Local LLM is busy with another request; retry after it finishes")
            self._in_use = True
            epoch = self._epoch
            self._cancel_timer()
            stale = None
            if self._server is not None and (self._key != key or not _alive(self._server)):
                stale, self._server = self._server, None
        keep = False
        try:
            if stale is not None:
                _stop(stale)
            if self._server is None:
                server = factory()
                try:
                    url = server.__enter__()
                except BaseException:
                    _stop(server)  # qisman ishga tushgan jarayon ham yopiladi
                    raise
                with self._lock:
                    self._server, self._key, self._url = server, key, url
            yield self._url
            keep = True
        except ValueError:
            keep = True  # model javobi yaroqsiz, server esa sog'
            raise
        finally:
            with self._lock:
                self._in_use = False
                server = self._server
                idle = self._idle_s() if keep and epoch == self._epoch else 0.0
                if server is not None and idle > 0:
                    self._timer = threading.Timer(idle, self._expire, args=(self._timer_token,))
                    self._timer.daemon = True
                    self._timer.start()
                    server = None
                else:
                    self._server = None
            if server is not None:
                _stop(server)

    def evict_idle(self) -> bool:
        """Bo'sh turgan serverni darhol to'xtatadi; ijara davom etsa - False."""
        with self._lock:
            if self._in_use or self._server is None:
                return False
            self._cancel_timer()
            server, self._server = self._server, None
        _stop(server)
        return True

    def stop(self) -> None:
        with self._lock:
            self._epoch += 1
            self._cancel_timer()
            server = None
            if not self._in_use:
                server, self._server = self._server, None
        if server is not None:
            _stop(server)
