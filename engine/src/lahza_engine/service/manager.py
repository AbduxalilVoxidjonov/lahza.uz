"""`lahza install-service` / `uninstall-service` / `service-status` mantig'i.

Har amal avval **reja** (qadamlar ro'yxati) sifatida quriladi; `dry_run=True` - reja qaytariladi,
hech narsa yozilmaydi va hech qanday buyruq (`launchctl`, `schtasks`) chaqirilmaydi. Tashqi buyruqlar
`runner` orqali - testlarda almashtiriladi.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lahza_engine.service import SERVICE_LABEL, WINDOWS_TASK_NAME, launchd, winsched
from lahza_engine.service.runtime import alias_dir, find_live_engine
from lahza_engine.service.spec import ServiceSpec

Runner = Callable[[list[str]], subprocess.CompletedProcess]


def default_runner(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)


class ServiceError(RuntimeError):
    pass


def platform_kind(platform: str | None = None) -> str:
    p = sys.platform if platform is None else platform
    if p == "darwin":
        return "macos"
    if p == "win32":
        return "windows"
    raise ServiceError(f"servis faqat macOS va Windows uchun (joriy platforma: {p})")


# ---- Reja ------------------------------------------------------------------------------------

def install_plan(spec: ServiceSpec, platform: str | None = None, home: Path | None = None,
                 uid: int | None = None) -> list[dict[str, Any]]:
    kind = platform_kind(platform)
    steps: list[dict[str, Any]] = [{"op": "mkdir", "path": str(spec.logs_dir)},
                                   {"op": "mkdir", "path": str(spec.state_dir)}]
    if kind == "macos":
        path = launchd.plist_path(home)
        steps.append({"op": "write", "path": str(path), "mode": 0o644,
                      "content": launchd.render_plist(spec).decode("utf-8")})
        cmds = launchd.install_commands(path, uid)
        steps.append({"op": "run", "cmd": cmds[0], "ignore_error": True})
        steps.append({"op": "run", "cmd": cmds[1]})
    else:
        if spec.env:
            steps.append({"op": "write", "path": str(winsched.env_file(spec)), "mode": 0o600,
                          "content": json.dumps(spec.env, ensure_ascii=False, indent=2)})
        xml_path = winsched.task_xml_path(spec)
        steps.append({"op": "write", "path": str(xml_path), "mode": 0o600, "encoding": "utf-16",
                      "content": winsched.build_task_xml(spec)})
        for cmd in winsched.install_commands(xml_path):
            steps.append({"op": "run", "cmd": cmd})
    return steps


def uninstall_plan(data_dir: Path, platform: str | None = None, home: Path | None = None,
                   uid: int | None = None, purge_logs: bool = False) -> list[dict[str, Any]]:
    kind = platform_kind(platform)
    spec = ServiceSpec(program=[], data_dir=Path(data_dir))
    steps: list[dict[str, Any]] = []
    if kind == "macos":
        steps += [{"op": "run", "cmd": c, "ignore_error": True} for c in launchd.uninstall_commands(uid)]
        steps.append({"op": "remove", "path": str(launchd.plist_path(home))})
    else:
        cmds = winsched.uninstall_commands()
        steps.append({"op": "run", "cmd": cmds[0], "ignore_error": True})
        steps.append({"op": "run", "cmd": cmds[1], "ignore_error": True})
    # Servis holati (start jurnali, Windows env/XML nusxasi) va eskirgan taxalluslar.
    steps.append({"op": "remove", "path": str(spec.state_dir)})
    steps.append({"op": "remove", "path": str(alias_dir(data_dir))})
    if purge_logs:
        steps += [{"op": "remove", "path": str(spec.stdout_log)}, {"op": "remove", "path": str(spec.stderr_log)}]
    return steps


# ---- Bajarish --------------------------------------------------------------------------------

def execute(steps: list[dict[str, Any]], runner: Runner = default_runner) -> list[dict[str, Any]]:
    done: list[dict[str, Any]] = []
    for st in steps:
        op = st["op"]
        res: dict[str, Any] = {k: v for k, v in st.items() if k != "content"}
        if op == "mkdir":
            Path(st["path"]).mkdir(parents=True, exist_ok=True)
        elif op == "write":
            p = Path(st["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + ".tmp")
            tmp.write_text(st["content"], encoding=st.get("encoding", "utf-8"))
            if sys.platform != "win32":
                os.chmod(tmp, st.get("mode", 0o644))
            os.replace(tmp, p)
        elif op == "remove":
            p = Path(st["path"])
            res["existed"] = p.exists() or p.is_symlink()
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p, ignore_errors=True)
            else:
                with contextlib.suppress(FileNotFoundError):
                    p.unlink()
        elif op == "run":
            try:
                cp = runner(st["cmd"])
                rc, err = cp.returncode, (cp.stderr or "").strip()
            except (OSError, subprocess.SubprocessError) as e:
                rc, err = -1, str(e)
            res["returncode"] = rc
            if rc != 0:
                res["stderr"] = err[:500]
                if not st.get("ignore_error"):
                    done.append(res)
                    raise ServiceError(f"buyruq xato bilan tugadi ({rc}): {' '.join(st['cmd'])}: {err[:300]}",
                                       ) from None
        done.append(res)
    return done


def install(spec: ServiceSpec, dry_run: bool = False, platform: str | None = None,
            home: Path | None = None, uid: int | None = None, runner: Runner = default_runner
            ) -> dict[str, Any]:
    steps = install_plan(spec, platform, home, uid)
    out: dict[str, Any] = {"action": "install", "platform": platform_kind(platform),
                           "label": SERVICE_LABEL if platform_kind(platform) == "macos" else WINDOWS_TASK_NAME,
                           "program": spec.args, "dry_run": dry_run}
    if dry_run:
        out["plan"] = steps
        return out
    exe = Path(spec.program[0])
    if not exe.exists():
        raise ServiceError(f"engine dasturi topilmadi: {exe} (--program bilan ko'rsating)")
    out["steps"] = execute(steps, runner)
    return out


def uninstall(data_dir: Path, dry_run: bool = False, platform: str | None = None, home: Path | None = None,
              uid: int | None = None, purge_logs: bool = False, runner: Runner = default_runner
              ) -> dict[str, Any]:
    steps = uninstall_plan(data_dir, platform, home, uid, purge_logs)
    out: dict[str, Any] = {"action": "uninstall", "platform": platform_kind(platform), "dry_run": dry_run}
    if dry_run:
        out["plan"] = steps
        return out
    out["steps"] = execute(steps, runner)
    return out


def status(data_dir: Path, platform: str | None = None, home: Path | None = None, uid: int | None = None,
           runner: Runner = default_runner, health=None) -> dict[str, Any]:
    kind = platform_kind(platform)
    out: dict[str, Any] = {"platform": kind}
    if kind == "macos":
        path = launchd.plist_path(home)
        out.update(label=SERVICE_LABEL, unit=str(path), installed=path.exists())
        try:
            cp = runner(launchd.status_command(uid))
            out["loaded"] = cp.returncode == 0
            if cp.returncode == 0:
                out.update(launchd.parse_print(cp.stdout or ""))
        except (OSError, subprocess.SubprocessError):
            out["loaded"] = None
    else:
        out.update(label=WINDOWS_TASK_NAME)
        try:
            cp = runner(winsched.status_command())
            out["installed"] = out["loaded"] = cp.returncode == 0
            if cp.returncode == 0:
                out["details"] = (cp.stdout or "").strip()[:2000]
        except (OSError, subprocess.SubprocessError):
            out["installed"] = out["loaded"] = None
    live = find_live_engine(Path(data_dir), health=health, attempts=1)
    # Token chiqarilmaydi.
    out["engine"] = ({"running": True, "pid": live["pid"], "port": live["port"], "version": live.get("version")}
                     if live else {"running": False})
    return out
