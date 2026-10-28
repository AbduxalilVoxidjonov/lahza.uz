"""Lahza MCP serverini Claude Code / Claude Desktop'ga ulash va uzish.

* Claude Code: `claude mcp add --scope user lahza [-e K=V ...] -- <buyruq>` /
  `claude mcp remove --scope user lahza` (bayroqlar `claude mcp add --help`, 2.1.310 dan).
  Holat `~/.claude.json` (yoki `$CLAUDE_CONFIG_DIR/.claude.json`) -> `mcpServers.lahza` dan
  o'qiladi: `claude mcp list/get` har serverni ishga tushirib health-check qiladi, shuning uchun
  har GET status'da chaqirilmaydi.
* Claude Desktop: `claude_desktop_config.json` -> `mcpServers.lahza`; boshqa yozuvlar saqlanadi,
  yozishdan oldin `.bak` zaxira, yozish atomik (vaqtinchalik fayl + `os.replace`).
* `dry_run=True` hech narsa yozmaydi va hech qanday jarayon ishga tushirmaydi.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from lahza_engine.claude_bridge import ClaudeError, proc
from lahza_engine.service.spec import build_spec

SERVER_NAME = "lahza"
TARGETS = ("claude_code", "claude_desktop")


def mcp_command(data_dir: Path, environ: Mapping[str, str] | None = None,
                program: str | None = None) -> tuple[list[str], dict[str, str]]:
    """MCP buyrug'i va muhiti: packaged - sidecar binari + `mcp`; dev - `python -m lahza_engine mcp`.

    Dastur yo'li ADB-7 servis mantiqidan (`service.spec.default_program`) olinadi.
    """
    spec = build_spec(data_dir, program=program, environ=dict(environ) if environ is not None else None)
    env = dict(spec.env)
    env["LAHZA_DATA_DIR"] = str(Path(data_dir))
    return [*spec.program, "mcp"], env


# ---- Claude Code ---------------------------------------------------------------------------

def claude_code_config(environ: Mapping[str, str] | None = None) -> Path:
    environ = os.environ if environ is None else environ
    if environ.get("CLAUDE_CONFIG_DIR"):
        return Path(environ["CLAUDE_CONFIG_DIR"]) / ".claude.json"
    home = environ.get("HOME") or environ.get("USERPROFILE")
    return (Path(home) if home else Path.home()) / ".claude.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        raise ClaudeError("claude_config_invalid", f"{path.name} o'qilmadi: {e}") from e
    if not isinstance(data, dict):
        raise ClaudeError("claude_config_invalid", f"{path.name} JSON obyekt emas")
    return data


def claude_code_connected(environ: Mapping[str, str] | None = None) -> bool:
    try:
        data = _read_json(claude_code_config(environ)) or {}
    except ClaudeError:
        return False
    servers = data.get("mcpServers")
    return isinstance(servers, dict) and SERVER_NAME in servers


def _code_actions(cli: str, command: list[str], env: dict[str, str], connect: bool,
                  connected: bool) -> list[list[str]]:
    remove = [cli, "mcp", "remove", "--scope", "user", SERVER_NAME]
    if not connect:
        return [remove] if connected else []
    add = [cli, "mcp", "add", "--scope", "user", SERVER_NAME]
    for k, v in sorted(env.items()):
        add += ["-e", f"{k}={v}"]
    add += ["--", *command]
    # `mcp add` mavjud nomni qayta yozmaydi: yangilash = olib tashlash + qo'shish.
    return [remove, add] if connected else [add]


def _cmdline(args: list[str]) -> str:
    """Foydalanuvchiga ko'rsatiladigan buyruq: Windows'da cmd qoidalari, boshqa joyda POSIX shell."""
    return subprocess.list2cmdline(args) if sys.platform == "win32" else shlex.join(args)


def run_claude_code(cli: str | None, command: list[str], env: dict[str, str], connect: bool,
                    dry_run: bool, environ: Mapping[str, str] | None = None,
                    runner: proc.Runner | None = None) -> list[str]:
    if not cli:
        raise ClaudeError("claude_not_installed", "Claude Code CLI (`claude`) topilmadi")
    plan = _code_actions(cli, command, env, connect, claude_code_connected(environ))
    actions = [_cmdline(a) for a in plan]
    if dry_run:
        return actions
    runner = runner or proc.run
    for args in plan:
        res = runner(args, timeout=30)
        if res.returncode != 0:
            tail = (res.stderr or res.stdout).strip()[-300:]
            raise ClaudeError("claude_error", f"`{_cmdline(args[1:4])}` xato ({res.returncode}): {tail}")
    return actions


# ---- Claude Desktop ------------------------------------------------------------------------

def desktop_config(environ: Mapping[str, str] | None = None, platform: str = sys.platform) -> Path:
    environ = os.environ if environ is None else environ
    home = Path(environ.get("HOME") or environ.get("USERPROFILE") or Path.home())
    if platform == "darwin":
        return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if platform == "win32":
        appdata = environ.get("APPDATA")
        base = Path(appdata) if appdata else home / "AppData" / "Roaming"
        return base / "Claude" / "claude_desktop_config.json"
    return home / ".config" / "Claude" / "claude_desktop_config.json"


def claude_desktop_connected(environ: Mapping[str, str] | None = None, platform: str = sys.platform) -> bool:
    try:
        data = _read_json(desktop_config(environ, platform)) or {}
    except ClaudeError:
        return False
    servers = data.get("mcpServers")
    return isinstance(servers, dict) and SERVER_NAME in servers


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".lahza-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def run_claude_desktop(command: list[str], env: dict[str, str], connect: bool, dry_run: bool,
                       environ: Mapping[str, str] | None = None, platform: str = sys.platform) -> list[str]:
    path = desktop_config(environ, platform)
    data = _read_json(path)
    exists = data is not None
    data = data or {}
    servers = data.get("mcpServers", {})
    if not isinstance(servers, dict):
        raise ClaudeError("claude_config_invalid", f"{path.name}: mcpServers obyekt emas")
    entry = {"command": command[0], "args": command[1:], "env": env}
    if connect:
        if servers.get(SERVER_NAME) == entry:
            return []
    elif SERVER_NAME not in servers:
        return []
    actions = []
    if exists:
        actions.append(f"backup {path} -> {path}.bak")
    actions.append(f"{'set' if connect else 'remove'} mcpServers.{SERVER_NAME} in {path}")
    if dry_run:
        return actions
    if exists:
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    servers = dict(servers)
    if connect:
        servers[SERVER_NAME] = entry
    else:
        servers.pop(SERVER_NAME, None)
    _atomic_write_json(path, {**data, "mcpServers": servers})
    return actions
