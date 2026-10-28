"""YouTube import komponentlari (YT-1, ADR-0010 2-band): yt-dlp, yt-dlp-ejs va Deno.

* Ilovaga qo'shilmaydi: foydalanuvchi Sozlamalarda tugmani bosganda (rozilik bilan) bir marta
  yuklanadi. Versiya, hajm va sha256 shu yerda mahkamlangan; mos kelmasa o'rnatilmaydi.
* yt-dlp va yt-dlp-ejs - PyPI'dagi sof Python g'ildiraklari (Unlicense), rasmiy exe EMAS (exe'da
  GPLv3+ kod bor). Ular `<data_dir>/Components/yt-dlp` ga ochiladi - `media/youtube.py` shu yerdan
  qidiradi. Deno (MIT) - GitHub relizi, `<data_dir>/Components/deno/` ga.
* Joylash atomik: avval `.staging-*` papkaga, keyin almashtiriladi; yarim o'rnatish qolmaydi.
* Yuklangan arxivlar `Components/.downloads` da saqlanadi: uzilgan o'rnatish davom ettiriladi.
"""

from __future__ import annotations

import json
import platform
import shutil
import stat
import sys
import tempfile
import threading
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import httpx

from lahza_engine.core.runner import Cancelled
from lahza_engine.media import youtube
from lahza_engine.models.downloader import download

YTDLP_DIR = "yt-dlp"
DENO_DIR = "deno"
MARKER = "lahza-component.json"


@dataclass(frozen=True)
class Asset:
    name: str
    version: str
    url: str
    sha256: str
    size: int
    license: str


YTDLP = Asset(
    "yt-dlp", "2026.10.26",
    "https://files.pythonhosted.org/packages/7f/3d/16ea7d5638cf585991f2c5705e8083688dde633d32d0871f2404e0f4d827/"
    "yt_dlp-2026.10.26-py3-none-any.whl",
    "a05c5b5d8562f7e8a62f5334348b406af4930d56d3a65f8021d14af0e22339ae", 3186201, "Unlicense")
EJS = Asset(
    "yt-dlp-ejs", "0.8.0",
    "https://files.pythonhosted.org/packages/e3/bd/520769863744b669440a924271a6159ddd82ad5ae26b4ac4d4b69e9f8d44/"
    "yt_dlp_ejs-0.8.0-py3-none-any.whl",
    "79300e5fca7f937a1eeede11f0456862c1b41107ce1d726871e0207424f4bdb4", 53443, "Unlicense")
WHEELS = (YTDLP, EJS)

_DENO_URL = "https://github.com/denoland/deno/releases/download/v2.9.8/deno-{}.zip"
DENO: dict[tuple[str, str], Asset] = {
    ("win32", "x86_64"): Asset("deno", "2.9.8", _DENO_URL.format("x86_64-pc-windows-msvc"),
                               "cba84b26e0df5ae7f74fc66b86a95b866872a86292ebd84fa1e959927edd93bf", 42917472, "MIT"),
    ("darwin", "arm64"): Asset("deno", "2.9.8", _DENO_URL.format("aarch64-apple-darwin"),
                               "9f0bf660393da2eaff044cdc7444cb08c73f235849b61d224d825a194ce7c98e", 38770795, "MIT"),
    ("darwin", "x86_64"): Asset("deno", "2.9.8", _DENO_URL.format("x86_64-apple-darwin"),
                                "4b2f5edd2639b7470f034238b321d7002d8dfb4726d8558f52c17afac370eb2c", 42797031, "MIT"),
    ("linux", "x86_64"): Asset("deno", "2.9.8", _DENO_URL.format("x86_64-unknown-linux-gnu"),
                               "e890975bc2549807bbcc0b584ffafda72cc7c93349dd99c80483dd784f6c4609", 41963064, "MIT"),
}

_LOCK = threading.Lock()
Progress = Callable[[float, dict[str, Any]], None]


class ComponentError(RuntimeError):
    pass


def _arch() -> str:
    m = platform.machine().lower()
    return {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64"}.get(m, m)


def deno_asset(plat: str = sys.platform, arch: str | None = None) -> Asset | None:
    return DENO.get((plat, arch or _arch()))


def root(data_dir: Path) -> Path:
    return data_dir / "Components"


def _marker(path: Path) -> dict[str, Any]:
    try:
        return json.loads((path / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def wheels_current(data_dir: Path) -> bool:
    """Komponent papkasidagi yt-dlp/yt-dlp-ejs aynan mahkamlangan versiyami."""
    want = {a.name: a.version for a in WHEELS}
    return _marker(root(data_dir) / YTDLP_DIR).get("versions") == want


def deno_current(data_dir: Path, plat: str = sys.platform) -> bool:
    """Ilovaning o'z Deno'si (PATH'dagi node/deno versiyasi noma'lum - unga tayanilmaydi)."""
    exe = "deno.exe" if plat == "win32" else "deno"
    return (root(data_dir) / DENO_DIR / exe).is_file()


def plan(data_dir: Path, plat: str = sys.platform, arch: str | None = None) -> list[Asset]:
    """Yuklanishi kerak bo'lgan qismlar (allaqachon o'rnatilganlari o'tkazib yuboriladi)."""
    out: list[Asset] = [] if wheels_current(data_dir) else list(WHEELS)
    deno = deno_asset(plat, arch)
    if deno is not None and not deno_current(data_dir, plat):
        out.append(deno)
    return out


def status(data_dir: Path) -> dict[str, Any]:
    todo = plan(data_dir)
    return {"components_ready": not todo, "components_download_bytes": sum(a.size for a in todo)}


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    out = []
    for info in archive.infolist():
        p = PurePosixPath(info.filename)
        if p.is_absolute() or ".." in p.parts or "\\" in info.filename or ":" in info.filename:
            raise ComponentError(f"arxivda xavfli yo'l: {info.filename}")
        out.append(info)
    return out


def _extract_wheel(path: Path, dest: Path) -> None:
    with zipfile.ZipFile(path) as z:
        for info in _safe_members(z):
            if not info.is_dir():
                z.extract(info, dest)


def _extract_deno(path: Path, dest: Path, exe: str) -> Path:
    with zipfile.ZipFile(path) as z:
        members = [i for i in _safe_members(z) if i.filename == exe]
        if not members:
            raise ComponentError(f"Deno arxivida {exe} yo'q")
        target = Path(z.extract(members[0], dest))
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return target


def _publish(staging: Path, final: Path) -> None:
    """Eski papkani yangisi bilan almashtiradi (Windows'da band papkaga os.replace ishlamaydi)."""
    old = final.with_name(final.name + ".old")
    shutil.rmtree(old, ignore_errors=True)
    if final.exists():
        final.rename(old)
    staging.rename(final)
    shutil.rmtree(old, ignore_errors=True)


def install(data_dir: Path, *, consent: bool, cancel: threading.Event | None = None,
            progress: Progress | None = None, client: httpx.Client | None = None,
            plat: str = sys.platform, arch: str | None = None) -> dict[str, Any]:
    """Yetishmagan komponentlarni yuklab, tekshirib, joylaydi. Tarmoq faqat shu yerda."""
    if consent is not True:
        raise ComponentError("komponentlarni yuklash uchun rozilik kerak")
    with _LOCK:
        todo = plan(data_dir, plat, arch)
        base = root(data_dir)
        cache = base / ".downloads"
        total = sum(a.size for a in todo) or 1
        done = 0

        def fetch(asset: Asset) -> Path:
            nonlocal done
            start = done

            def report(have: int, _total: int | None) -> None:
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                if progress:
                    progress(min(1.0, (start + have) / total),
                             {"component": asset.name, "downloaded_bytes": start + have, "total_bytes": total})

            path = download([asset.url], cache / Path(asset.url).name, asset.sha256, asset.size,
                            progress=report, client=client)
            done = start + asset.size
            return path

        installed: list[str] = []
        base.mkdir(parents=True, exist_ok=True)
        wheels = [a for a in todo if a in WHEELS]
        if wheels:
            files = [fetch(a) for a in wheels]
            staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=base))
            try:
                for f in files:
                    _extract_wheel(f, staging)
                if youtube.find_ytdlp([str(staging)]) is None:
                    raise ComponentError("yt-dlp g'ildiragida yt_dlp paketi topilmadi")
                (staging / MARKER).write_text(json.dumps(
                    {"versions": {a.name: a.version for a in WHEELS},
                     "files": [{"name": a.name, "url": a.url, "sha256": a.sha256, "license": a.license}
                               for a in WHEELS]}, indent=2), encoding="utf-8")
                _publish(staging, base / YTDLP_DIR)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
            installed += [a.name for a in wheels]
        deno = next((a for a in todo if a.name == "deno"), None)
        if deno is not None:
            f = fetch(deno)
            exe = "deno.exe" if plat == "win32" else "deno"
            staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=base))
            try:
                _extract_deno(f, staging, exe)
                (staging / MARKER).write_text(json.dumps(
                    {"versions": {"deno": deno.version}, "files": [
                        {"name": "deno", "url": deno.url, "sha256": deno.sha256, "license": deno.license}]},
                    indent=2), encoding="utf-8")
                _publish(staging, base / DENO_DIR)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
            installed.append("deno")
        if progress:
            progress(1.0, {"component": None, "downloaded_bytes": total, "total_bytes": total})
        # Yuklangan arxivlar endi kerak emas (keyingi yangilanish yangi versiyani yuklaydi).
        if not plan(data_dir, plat, arch):
            shutil.rmtree(cache, ignore_errors=True)
        return {"components": installed, **youtube.status(data_dir)}


def uninstall(data_dir: Path) -> None:
    base = root(data_dir)
    for name in (YTDLP_DIR, DENO_DIR, ".downloads"):
        shutil.rmtree(base / name, ignore_errors=True)
