"""Qurilma barmoq izi: OS mashina identifikatorining xeshi (tarmoqsiz, shaxsiy ma'lumotsiz).

Manbalar: macOS - IOPlatformUUID (`ioreg`), Windows - `MachineGuid` (reestr), Linux -
`/etc/machine-id`; topilmasa - MAC manzil (`uuid.getnode`). Xom identifikator saqlanmaydi va
yuborilmaydi: faqat `sha256("lahza-device/1:" + id)` ning boshidagi 10 bayt (base32, 16 belgi).
"""

from __future__ import annotations

import base64
import functools
import hashlib
import re
import subprocess
import sys
import uuid
from pathlib import Path


def _machine_id() -> str:
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],  # noqa: S607
                                 capture_output=True, text=True, timeout=5).stdout
            m = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
            if m:
                return m.group(1)
        elif sys.platform == "win32":
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as k:
                return str(winreg.QueryValueEx(k, "MachineGuid")[0])
        else:
            for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                f = Path(p)
                if f.is_file() and f.read_text().strip():
                    return f.read_text().strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return f"mac:{uuid.getnode():012x}"


def fingerprint_of(machine_id: str) -> str:
    h = hashlib.sha256(f"lahza-device/1:{machine_id}".encode()).digest()[:10]
    s = base64.b32encode(h).decode()  # 16 belgi, `=` siz
    return "-".join(s[i:i + 4] for i in range(0, 16, 4))


@functools.cache
def device_fingerprint() -> str:
    """Joriy qurilma barmoq izi, masalan `ABCD-EFGH-IJKL-MNOP`."""
    return fingerprint_of(_machine_id())
