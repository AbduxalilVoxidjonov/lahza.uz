"""Tashqi bajariladigan fayllarni topish (ffmpeg, ffprobe, whisper-cli, llama-server).

Qidiruv tartibi:
1. LAHZA_BIN_DIR muhit o'zgaruvchisi (Tauri ilova resurslar papkasini shu orqali beradi).
2. Engine bajariladigan faylining yonidagi `bin/` papkasi (PyInstaller sidecar).
3. PATH (faqat dasturchi muhiti uchun).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


class ToolNotFound(RuntimeError):
    pass


def _exe(name: str) -> str:
    return name + ".exe" if sys.platform == "win32" else name


def find_tool(name: str) -> Path:
    candidates: list[Path] = []
    env = os.environ.get("LAHZA_BIN_DIR")
    if env:
        candidates.append(Path(env) / _exe(name))
    base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    candidates.append(base / "bin" / _exe(name))
    for c in candidates:
        if c.is_file():
            return c
    found = shutil.which(name)
    if found:
        return Path(found)
    raise ToolNotFound(f"'{name}' topilmadi. LAHZA_BIN_DIR yoki PATH ni tekshiring.")


def run(args: list[str | os.PathLike[str]], timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    """Shell'siz, argumentlar massivi bilan (NFR-08)."""
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    return subprocess.run(
        [str(a) for a in args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        **kwargs,
    )
