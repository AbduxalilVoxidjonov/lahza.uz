"""llama.cpp `llama-server` jarayonini boshqarish.

Server faqat highlight bosqichida ishga tushadi va tugagach to'xtatiladi - GPU xotirasini
tejash uchun modellar ketma-ket yuklanadi (TZ 4-bo'lim, "Resurs boshqaruvi").
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

from lahza_engine.media.tools import find_tool


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

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> str:
        self.port = free_port()
        exe = find_tool("llama-server")
        flags = 0x08000000 if sys.platform == "win32" else 0
        self.proc = subprocess.Popen(
            [str(exe), "-m", str(self.model_path), "--host", "127.0.0.1", "--port", str(self.port),
             "-c", str(self.ctx_size), "-ngl", str(self.gpu_layers)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags,
        )
        deadline = time.monotonic() + self.startup_timeout_s
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("llama-server ishga tushmadi (model yoki xotira muammosi)")
            try:
                if httpx.get(f"{self.url}/health", timeout=2).status_code == 200:
                    return self.url
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        self.__exit__(None, None, None)
        raise TimeoutError("llama-server o'z vaqtida tayyor bo'lmadi")

    def __exit__(self, *exc: object) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
