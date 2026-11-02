"""Tashqi `claude` jarayonlari: shell'siz, argumentlar ro'yxat, timeout va bekor qilish bilan."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from lahza_engine.claude_bridge import ClaudeError


@dataclass(frozen=True)
class Result:
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[..., Result]
"""`runner(args, timeout=..., input=None, cwd=None, cancel=None) -> Result` (testlarda soxtasi)."""

_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


def run(args: list[str], timeout: float, input: str | None = None, cwd: str | None = None,
        cancel: threading.Event | None = None) -> Result:
    """Jarayonni ishga tushirib kutadi. Timeout -> `claude_timeout`, bekor -> `claude_cancelled`."""
    if not args or not isinstance(args, list):
        raise ValueError("args must be a non-empty list")
    try:
        proc = subprocess.Popen(args, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace", cwd=cwd, env=dict(os.environ),
                                creationflags=_FLAGS)
    except OSError as e:
        raise ClaudeError("claude_not_installed", f"claude ishga tushmadi: {e}") from e
    deadline = time.monotonic() + timeout
    pending = input
    while True:
        try:
            out, err = proc.communicate(pending, timeout=0.2)
            return Result(proc.returncode, out or "", err or "")
        except subprocess.TimeoutExpired:
            pending = None  # kiritma birinchi chaqiruvda yuborilgan
            reason = None
            if cancel is not None and cancel.is_set():
                reason = ClaudeError("claude_cancelled", "so'rov bekor qilindi")
            elif time.monotonic() >= deadline:
                reason = ClaudeError("claude_timeout", f"claude {timeout:.0f} s ichida javob bermadi")
            if reason is not None:
                proc.kill()
                proc.communicate()
                raise reason from None
