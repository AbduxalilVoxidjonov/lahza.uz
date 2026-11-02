"""Claude Code CLI va Claude Desktop'ni topish. Tarmoq yo'q; natija qisqa muddat keshlanadi.

macOS'da GUI ilovaga foydalanuvchi shell PATH'i berilmaydi, shuning uchun PATH'dan tashqari
odatiy o'rnatish joylari ham tekshiriladi (rasmiy o'rnatuvchi `~/.local/bin/claude`).
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import threading
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

from lahza_engine.claude_bridge import ClaudeError, proc

CACHE_TTL_S = 15.0
VERSION_RE = re.compile(r"(\d+\.\d+\.\d+(?:[-.][0-9A-Za-z.]+)?)")


@dataclass(frozen=True)
class CliInfo:
    installed: bool
    path: str | None
    version: str | None


@dataclass(frozen=True)
class DesktopInfo:
    installed: bool
    path: str | None


@dataclass(frozen=True)
class Detection:
    cli: CliInfo
    desktop: DesktopInfo

    def to_dict(self) -> dict:
        return {"cli": asdict(self.cli), "desktop": asdict(self.desktop)}


def _home(environ: Mapping[str, str]) -> Path:
    return Path(environ.get("HOME") or environ.get("USERPROFILE") or Path.home())


def cli_dirs(environ: Mapping[str, str], platform: str = sys.platform) -> list[Path]:
    """PATH'dan keyin tekshiriladigan qo'shimcha papkalar (tartib muhim)."""
    home = _home(environ)
    dirs = [home / ".local" / "bin", home / ".claude" / "local"]
    if platform == "win32":
        if environ.get("APPDATA"):
            dirs.append(Path(environ["APPDATA"]) / "npm")
        if environ.get("LOCALAPPDATA"):
            local = Path(environ["LOCALAPPDATA"])
            dirs += [local / "Programs" / "claude", local / "claude"]
    else:
        dirs += [Path("/opt/homebrew/bin"), Path("/usr/local/bin")]
    return dirs


def find_cli(environ: Mapping[str, str] | None = None, platform: str = sys.platform) -> str | None:
    environ = os.environ if environ is None else environ
    names = ["claude"] if platform != "win32" else ["claude.exe", "claude.cmd", "claude"]
    path_env = environ.get("PATH", "")
    for name in names:
        hit = shutil.which(name, path=path_env) if path_env else None
        if hit:
            return str(Path(hit))
    for d in cli_dirs(environ, platform):
        for name in names:
            cand = d / name
            if cand.is_file() and (platform == "win32" or os.access(cand, os.X_OK)):
                return str(cand)
    return None


def parse_version(text: str) -> str | None:
    """`2.1.310 (Claude Code)` -> `2.1.310`."""
    m = VERSION_RE.search(text or "")
    return m.group(1) if m else None


def cli_version(path: str, runner: proc.Runner | None = None) -> str | None:
    runner = runner or proc.run
    try:
        res = runner([path, "--version"], timeout=10)
    except (ClaudeError, OSError, ValueError):
        return None
    return parse_version(res.stdout) if res.returncode == 0 else None


def find_desktop(environ: Mapping[str, str] | None = None, platform: str = sys.platform) -> str | None:
    environ = os.environ if environ is None else environ
    home = _home(environ)
    if platform == "darwin":
        cands = [Path("/Applications/Claude.app"), home / "Applications" / "Claude.app"]
    elif platform == "win32":
        cands = [Path(environ["LOCALAPPDATA"]) / "AnthropicClaude"] if environ.get("LOCALAPPDATA") else []
    else:
        cands = []  # Linux uchun rasmiy Claude Desktop yo'q
    for c in cands:
        if c.exists():
            return str(c)
    return None


_lock = threading.Lock()
_cache: dict[tuple, tuple[float, Detection]] = {}


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def detect(environ: Mapping[str, str] | None = None, platform: str = sys.platform,
           runner: proc.Runner | None = None, refresh: bool = False) -> Detection:
    environ = os.environ if environ is None else environ
    key = (platform, environ.get("PATH"), environ.get("HOME"), environ.get("USERPROFILE"),
           environ.get("APPDATA"), environ.get("LOCALAPPDATA"))
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and not refresh and now - hit[0] < CACHE_TTL_S:
            return hit[1]
    path = find_cli(environ, platform)
    version = cli_version(path, runner) if path else None
    desktop = find_desktop(environ, platform)
    result = Detection(cli=CliInfo(installed=path is not None, path=path, version=version),
                       desktop=DesktopInfo(installed=desktop is not None, path=desktop))
    with _lock:
        _cache[key] = (now, result)
    return result
