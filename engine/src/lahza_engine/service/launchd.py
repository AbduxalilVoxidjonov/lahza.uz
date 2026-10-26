"""macOS LaunchAgent (`~/Library/LaunchAgents/uz.lahza.engine.plist`).

Manba: `man launchd.plist` (Label, ProgramArguments, RunAtLoad, KeepAlive.SuccessfulExit, ThrottleInterval,
StandardOutPath/StandardErrorPath, LimitLoadToSessionType), `man launchctl` (bootstrap/bootout/print, `gui/<uid>`).
Foydalanuvchi domeni (`gui/<uid>`) - sudo kerak emas, tizim fayllari o'zgarmaydi.
"""

from __future__ import annotations

import os
import plistlib
import re
from pathlib import Path
from typing import Any

from lahza_engine.service import SERVICE_LABEL
from lahza_engine.service.spec import ServiceSpec

THROTTLE_S = 10
"""launchd qayta ishga tushirishlar orasidagi eng kam vaqt (s); qo'shimcha cheklov - runtime.record_start."""


def plist_path(home: Path | None = None) -> Path:
    return (Path.home() if home is None else Path(home)) / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist"


def domain(uid: int | None = None) -> str:
    return f"gui/{os.getuid() if uid is None else uid}"


def service_target(uid: int | None = None) -> str:
    return f"{domain(uid)}/{SERVICE_LABEL}"


def build_plist(spec: ServiceSpec) -> dict[str, Any]:
    d: dict[str, Any] = {
        "Label": SERVICE_LABEL,
        "ProgramArguments": spec.args,
        "RunAtLoad": True,
        # Muvaffaqiyatli chiqish (0: boshqa engine allaqachon ishlayapti, qulash cheklovi) - qayta
        # ishga tushirilmaydi; qulash (nol bo'lmagan kod, signal) - qayta ishga tushiriladi.
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": THROTTLE_S,
        # Faqat grafik sessiyada (Adobe ilovalari shu yerda); SSH sessiyasida yuklanmaydi.
        "LimitLoadToSessionType": "Aqua",
        "ProcessType": "Interactive",
        "WorkingDirectory": str(spec.data_dir),
        "StandardOutPath": str(spec.stdout_log),
        "StandardErrorPath": str(spec.stderr_log),
    }
    if spec.env:
        d["EnvironmentVariables"] = dict(sorted(spec.env.items()))
    return d


def render_plist(spec: ServiceSpec) -> bytes:
    return plistlib.dumps(build_plist(spec), fmt=plistlib.FMT_XML, sort_keys=True)


def install_commands(path: Path, uid: int | None = None) -> list[list[str]]:
    """Avval eski nusxa tushiriladi (xato e'tiborsiz - yuklanmagan bo'lishi mumkin), so'ng yuklanadi."""
    return [["launchctl", "bootout", service_target(uid)],
            ["launchctl", "bootstrap", domain(uid), str(path)]]


def uninstall_commands(uid: int | None = None) -> list[list[str]]:
    return [["launchctl", "bootout", service_target(uid)]]


def status_command(uid: int | None = None) -> list[str]:
    return ["launchctl", "print", service_target(uid)]


def parse_print(out: str) -> dict[str, Any]:
    """`launchctl print` chiqishidan holat (format barqaror API emas - faqat ma'lumot uchun)."""
    res: dict[str, Any] = {}
    if m := re.search(r"^\s*state = (\S+)", out, re.M):
        res["state"] = m.group(1)
    if m := re.search(r"^\s*pid = (\d+)", out, re.M):
        res["pid"] = int(m.group(1))
    if m := re.search(r"^\s*last exit code = (.+)$", out, re.M):
        res["last_exit"] = m.group(1).strip()
    return res
