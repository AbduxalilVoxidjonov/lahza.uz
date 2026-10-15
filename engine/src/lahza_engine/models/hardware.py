"""Apparatni aniqlash va daraja (tier) tanlash (TZ 2-bo'lim).

Darajalar jadvali (TZ):
| Daraja   | Mac                 | Windows                                   |
| Lite     | M1/M2, 8 GB         | 16 GB RAM, GPU yo'q                       |
| Standard | M-seriya, 16 GB     | NVIDIA 8 GB VRAM, 16 GB RAM               |
| Pro      | M-Pro/Max, 32 GB+   | NVIDIA 16 GB+ VRAM, 32 GB RAM             |
Intel Mac qo'llanmaydi.
"""

from __future__ import annotations

import platform
import shutil
import sys
from dataclasses import asdict, dataclass, field
from enum import StrEnum

from lahza_engine.media.tools import run

GB = 1024**3


class Tier(StrEnum):
    UNSUPPORTED = "unsupported"
    LITE = "lite"
    STANDARD = "standard"
    PRO = "pro"


@dataclass
class Gpu:
    vendor: str  # apple | nvidia | amd | intel | unknown
    name: str
    vram_gb: float | None  # Apple: unified memory -> None (RAM bilan umumiy)


@dataclass
class HardwareProfile:
    os: str  # darwin | win32 | linux
    os_version: str
    arch: str  # arm64 | x86_64
    cpu: str
    ram_gb: float
    free_disk_gb: float
    gpus: list[Gpu] = field(default_factory=list)

    @property
    def apple_silicon(self) -> bool:
        return self.os == "darwin" and self.arch == "arm64"

    def best_gpu(self) -> Gpu | None:
        if not self.gpus:
            return None
        return max(self.gpus, key=lambda g: (g.vendor == "nvidia", g.vram_gb or 0))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TierDecision:
    tier: Tier
    reasons: list[str]


def classify(hw: HardwareProfile) -> TierDecision:
    reasons: list[str] = []
    if hw.os == "darwin":
        if not hw.apple_silicon:
            return TierDecision(Tier.UNSUPPORTED, ["Intel Mac qo'llanmaydi (Apple Silicon kerak)"])
        if hw.ram_gb >= 32:
            return TierDecision(Tier.PRO, ["Apple Silicon, >= 32 GB"])
        if hw.ram_gb >= 16:
            return TierDecision(Tier.STANDARD, ["Apple Silicon, >= 16 GB"])
        if hw.ram_gb >= 8:
            return TierDecision(Tier.LITE, ["Apple Silicon, >= 8 GB"])
        return TierDecision(Tier.UNSUPPORTED, ["Apple Silicon, lekin RAM 8 GB dan kam"])
    if hw.os == "win32":
        g = hw.best_gpu()
        vram = g.vram_gb if g and g.vendor == "nvidia" else None
        if vram is not None and vram >= 16 and hw.ram_gb >= 32:
            return TierDecision(Tier.PRO, [f"NVIDIA {vram:.0f} GB VRAM, {hw.ram_gb:.0f} GB RAM"])
        if vram is not None and vram >= 8 and hw.ram_gb >= 16:
            return TierDecision(Tier.STANDARD, [f"NVIDIA {vram:.0f} GB VRAM, {hw.ram_gb:.0f} GB RAM"])
        if hw.ram_gb >= 16:
            reasons.append("16 GB+ RAM; mos NVIDIA GPU yo'q - CPU/Vulkan rejimi")
            return TierDecision(Tier.LITE, reasons)
        return TierDecision(Tier.UNSUPPORTED, ["Windows uchun kamida 16 GB RAM kerak"])
    return TierDecision(Tier.UNSUPPORTED, [f"{hw.os} v1.0 da qo'llanmaydi (faqat dasturchi muhiti)"])


def _ram_gb() -> float:
    try:
        import psutil

        return psutil.virtual_memory().total / GB
    except Exception:  # pragma: no cover
        return 0.0


def _cpu_name() -> str:
    if sys.platform == "darwin":
        r = run(["sysctl", "-n", "machdep.cpu.brand_string"])
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    return platform.processor() or platform.machine()


def _nvidia() -> list[Gpu]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return []
    r = run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], timeout=10)
    out = []
    if r.returncode == 0:
        for line in r.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 2:
                try:
                    out.append(Gpu("nvidia", parts[0], float(parts[1]) / 1024))
                except ValueError:
                    continue
    return out


def _windows_other_gpus() -> list[Gpu]:
    """AMD/Intel nomlarini olish. AdapterRAM 4 GB da cheklangan bo'lgani uchun VRAM yozilmaydi."""
    r = run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
        timeout=15,
    )
    out = []
    for name in r.stdout.splitlines() if r.returncode == 0 else []:
        n = name.strip()
        low = n.lower()
        if not n or "nvidia" in low:
            continue
        vendor = "amd" if ("amd" in low or "radeon" in low) else "intel" if "intel" in low else "unknown"
        out.append(Gpu(vendor, n, None))
    return out


def detect(disk_path: str = ".") -> HardwareProfile:
    os_name = sys.platform if sys.platform in ("darwin", "win32") else "linux"
    arch = platform.machine().lower()
    arch = "arm64" if arch in ("arm64", "aarch64") else "x86_64" if arch in ("x86_64", "amd64") else arch
    gpus: list[Gpu] = []
    if os_name == "darwin" and arch == "arm64":
        gpus.append(Gpu("apple", "Apple Silicon GPU", None))
    else:
        gpus.extend(_nvidia())
        if os_name == "win32":
            gpus.extend(_windows_other_gpus())
    return HardwareProfile(
        os=os_name,
        os_version=platform.release(),
        arch=arch,
        cpu=_cpu_name(),
        ram_gb=round(_ram_gb(), 1),
        free_disk_gb=round(shutil.disk_usage(disk_path).free / GB, 1),
        gpus=gpus,
    )
