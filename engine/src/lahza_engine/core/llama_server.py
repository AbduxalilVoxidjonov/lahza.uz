"""llama.cpp `llama-server` jarayonini boshqarish.

Server faqat highlight bosqichida ishga tushadi va tugagach to'xtatiladi - GPU xotirasini
tejash uchun modellar ketma-ket yuklanadi (TZ 4-bo'lim, "Resurs boshqaruvi").
"""

from __future__ import annotations

import socket
import subprocess
import sys
import threading
import time
from contextlib import suppress
from pathlib import Path

import httpx

from lahza_engine.media.tools import find_tool

_LLM_LOCK = threading.Lock()


class LlamaServerBusy(RuntimeError):
    """Another managed LLM owns the process-wide GPU slot; retry when it finishes."""


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class LlamaServer:
    def __init__(self, model_path: Path, ctx_size: int = 16384, gpu_layers: int = 999,
                 startup_timeout_s: float = 180.0) -> None:
        self.model_path = model_path
        self.ctx_size = ctx_size
        self.gpu_layers = gpu_layers
        self.startup_timeout_s = startup_timeout_s
        self.proc: subprocess.Popen[bytes] | None = None
        self.port = 0
        self._owns_llm_lock = False

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> str:
        if not _LLM_LOCK.acquire(blocking=False):
            raise LlamaServerBusy("Local LLM is busy with another request; retry after it finishes")
        self._owns_llm_lock = True
        try:
            self.port = free_port()
            exe = find_tool("llama-server")
            flags = 0x08000000 if sys.platform == "win32" else 0
            self.proc = subprocess.Popen(
                [str(exe), "-m", str(self.model_path), "--host", "127.0.0.1", "--port", str(self.port),
                 "-c", str(self.ctx_size), "-ngl", str(self.gpu_layers), "--parallel", "1"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags,
            )
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
            self.proc = None
            if self._owns_llm_lock:
                self._owns_llm_lock = False
                _LLM_LOCK.release()
