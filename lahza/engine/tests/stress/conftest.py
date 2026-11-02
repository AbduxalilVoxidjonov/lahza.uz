"""V1-1 chidamlilik (stress) testlari uchun umumiy sozlamalar.

Oddiy `pytest` da bu testlar YIG'ILADI, lekin tanlovdan chiqariladi (deselect) - o'tgan/skip
sonlari o'zgarmaydi. Ishga tushirish: `make test-stress` yoki `pytest -m stress tests/stress`
(yoki `LAHZA_STRESS=1`).

Parametrlar (muhit o'zgaruvchilari):
  LAHZA_STRESS_HOURS     sintetik uzun videoning davomiyligi, soat (standart 4)
  LAHZA_STRESS_EPISODES  navbatdagi epizodlar soni (standart 20)
  LAHZA_STRESS_EP_MIN    navbatdagi har epizod davomiyligi, daqiqa (standart 3)
  LAHZA_STRESS_RSS_MB    uzun video uchun RSS cho'qqisi chegarasi, MB (standart: 1500 + 600*soat)
  LAHZA_STRESS_LEAK_MB   navbatda 5-epizoddan 20-gacha RSS o'sishi chegarasi, MB (standart 150)
  LAHZA_STRESS_REPORT    JSON hisobot yo'li (standart: <tizim temp>/lahza-stress-report.json)
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

STRESS_MARK = "stress"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "stress: uzoq davom etadigan chidamlilik testlari (V1-1); faqat `-m stress` "
                   "yoki LAHZA_STRESS=1 bilan ishga tushadi")


def _enabled(config: pytest.Config) -> bool:
    return os.environ.get("LAHZA_STRESS") == "1" or STRESS_MARK in (config.option.markexpr or "")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _enabled(config):
        return
    keep, drop = [], []
    for it in items:
        (drop if it.get_closest_marker(STRESS_MARK) else keep).append(it)
    if drop:
        config.hook.pytest_deselected(items=drop)
        items[:] = keep


def env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


# --- hisobot -------------------------------------------------------------------------------

_REPORT: dict[str, Any] = {}


def report_path() -> Path:
    env = os.environ.get("LAHZA_STRESS_REPORT")
    return Path(env) if env else Path(tempfile.gettempdir()) / "lahza-stress-report.json"


@pytest.fixture(scope="session")
def stress_report() -> Any:
    _REPORT.update({
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "host": {"machine": platform.machine(), "system": platform.system(),
                 "release": platform.release(), "python": platform.python_version(),
                 "cpu": _cpu_name()},
        "ffmpeg": shutil.which("ffmpeg"),
        "results": {},
    })
    yield _REPORT["results"]
    path = report_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_REPORT, ensure_ascii=False, indent=2), encoding="utf-8")


def _cpu_name() -> str:
    try:
        r = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True,
                           text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return platform.processor() or platform.machine()


# --- resurs kuzatuvchisi -------------------------------------------------------------------

class RssSampler:
    """Jarayon RSS'ini fon oqimida o'lchaydi (cho'qqi + vaqt qatori). ffmpeg bolalari alohida."""

    def __init__(self, interval_s: float = 0.25) -> None:
        import psutil

        self.proc = psutil.Process()
        self.interval_s = interval_s
        self.peak = 0
        self.peak_children = 0
        self.samples: list[tuple[float, int]] = []
        self._stop = threading.Event()
        self._t0 = time.monotonic()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="rss-sampler")

    def rss(self) -> int:
        return int(self.proc.memory_info().rss)

    def _loop(self) -> None:
        last_keep = -10.0
        while not self._stop.is_set():
            r = self.rss()
            self.peak = max(self.peak, r)
            try:
                ch = sum(c.memory_info().rss for c in self.proc.children(recursive=True))
            except Exception:  # noqa: BLE001 - bola jarayon o'lchash paytida tugashi mumkin
                ch = 0
            self.peak_children = max(self.peak_children, ch)
            t = time.monotonic() - self._t0
            if t - last_keep >= 5.0:
                self.samples.append((round(t, 1), r))
                last_keep = t
            self._stop.wait(self.interval_s)

    def __enter__(self) -> RssSampler:
        self.peak = self.rss()
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=5)


def mb(n: int | float) -> float:
    return round(n / 2**20, 1)


# --- sintetik video -------------------------------------------------------------------------

def make_synthetic_video(path: Path, seconds: int, size: str = "320x180", fps: int = 5) -> Path:
    """Past o'lchamli test video: testsrc2 + 220 Hz sinus "nutq" (8 s) va jimlik (2 s) navbati."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg yo'q")
    audio = "aevalsrc='0.4*sin(2*PI*220*t)*gt(mod(t\\,10)\\,2)':s=16000:d=" + str(seconds)
    r = subprocess.run(
        [ffmpeg, "-hide_banner", "-v", "error", "-y",
         "-f", "lavfi", "-i", f"testsrc2=s={size}:r={fps}:d={seconds}",
         "-f", "lavfi", "-i", audio,
         "-c:v", "libx264", "-preset", "ultrafast", "-g", str(fps * 10),
         "-c:a", "aac", "-b:a", "32k", "-shortest", str(path)],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-500:])
    return path


@pytest.fixture(scope="session")
def stress_tmp() -> Any:
    """Katta fayllar uchun worktree tashqarisidagi tizim temp papkasi; oxirida o'chiriladi
    (pytest tmp_path oxirgi 3 ishga tushirishni saqlab qoladi - GB'lik fayllar uchun mos emas)."""
    d = Path(tempfile.mkdtemp(prefix="lahza-stress-"))
    yield d
    shutil.rmtree(d, ignore_errors=True)
