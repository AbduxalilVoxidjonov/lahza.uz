"""YouTube import komponentlari (YT-1, ADR-0010 2-band): yt-dlp, yt-dlp-ejs va Deno.

* Ilovaga qo'shilmaydi: foydalanuvchi Sozlamalarda tugmani bosganda (rozilik bilan) bir marta
  yuklanadi. Boshlang'ich versiya, hajm va sha256 shu yerda mahkamlangan; mos kelmasa o'rnatilmaydi.
* Yangilanish ilova relizisiz: "Yangilanishni tekshirish" PyPI JSON API va GitHub releases API'dan
  oxirgi versiyani va e'lon qilingan sha256 ni oladi (`resolve_latest`); yt-dlp-ejs versiyasi
  yt-dlp'ning o'z `requires_dist` talabidan. Mahkamlangandan eski versiya o'rnatilmaydi.
* yt-dlp va yt-dlp-ejs - PyPI'dagi sof Python g'ildiraklari (Unlicense), rasmiy exe EMAS (exe'da
  GPLv3+ kod bor). Ular `<data_dir>/Components/yt-dlp` ga ochiladi - `media/youtube.py` shu yerdan
  qidiradi. Deno (MIT) - GitHub relizi, `<data_dir>/Components/deno/` ga.
* Joylash atomik: avval `.staging-*` papkaga, keyin almashtiriladi; yarim o'rnatish qolmaydi.
* Yuklangan arxivlar `Components/.downloads` da saqlanadi: uzilgan o'rnatish davom ettiriladi.
"""

from __future__ import annotations

import json
import platform
import re
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
_DENO_TRIPLE = {key: a.url.rsplit("deno-", 1)[1].removesuffix(".zip") for key, a in DENO.items()}

# ---- yangilanish manbalari: o'z serverimiz va imzo kaliti kerak emas -------------------------------
# Ishonch: PyPI/GitHub TLS va ular e'lon qilgan sha256 (pip bilan bir xil). Faqat shu paketlar, faqat
# sof Python g'ildiragi (exe emas - GPL), faqat denoland/deno relizi va 2.x; versiya pasaymaydi.
PYPI_JSON = "https://pypi.org/pypi/{name}/{version}json"
DENO_LATEST = "https://api.github.com/repos/denoland/deno/releases/latest"
WHEEL_HOST = "https://files.pythonhosted.org/"
DENO_DOWNLOAD = "https://github.com/denoland/deno/releases/download/"
DENO_MAJOR = 2
MAX_WHEEL = 64 * 1024 * 1024
MAX_DENO = 256 * 1024 * 1024

_LOCK = threading.Lock()
Progress = Callable[[float, dict[str, Any]], None]


class ComponentError(RuntimeError):
    pass


def _arch() -> str:
    m = platform.machine().lower()
    return {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64"}.get(m, m)


def _vt(version: str) -> tuple[int, ...]:
    """`2026.10.26` / `0.8.0` / `v2.9.8` -> taqqoslanadigan raqamlar."""
    return tuple(int(x) for x in re.findall(r"\d+", version))


def deno_asset(plat: str = sys.platform, arch: str | None = None) -> Asset | None:
    return DENO.get((plat, arch or _arch()))


def root(data_dir: Path) -> Path:
    return data_dir / "Components"


def _marker(path: Path) -> dict[str, Any]:
    try:
        return json.loads((path / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def deno_current(data_dir: Path, plat: str = sys.platform) -> bool:
    """Ilovaning o'z Deno'si (PATH'dagi node/deno versiyasi noma'lum - unga tayanilmaydi)."""
    exe = "deno.exe" if plat == "win32" else "deno"
    return (root(data_dir) / DENO_DIR / exe).is_file()


def installed_versions(data_dir: Path, plat: str = sys.platform) -> dict[str, str]:
    """`Components/` dagi versiyalar (belgi fayllaridan; papka bo'lmasa - o'rnatilmagan)."""
    base = root(data_dir)
    out: dict[str, str] = {}
    # is_dir() avval: yo'q papkani PathFinder'ga bersak, sys.path_importer_cache "import'chi yo'q" deb
    # eslab qoladi va o'rnatilgandan keyin ham engine qayta ishga tushmaguncha topilmaydi.
    if (base / YTDLP_DIR).is_dir() and youtube.find_ytdlp([str(base / YTDLP_DIR)]) is not None:
        out.update(_marker(base / YTDLP_DIR).get("versions") or {})
    if deno_current(data_dir, plat):
        out.update(_marker(base / DENO_DIR).get("versions") or {})
    return {k: str(v) for k, v in out.items()}


def _newer(asset: Asset, have: dict[str, str]) -> bool:
    return asset.name not in have or _vt(asset.version) > _vt(have[asset.name])


def wheels_current(data_dir: Path) -> bool:
    """yt-dlp va yt-dlp-ejs o'rnatilgan va mahkamlangandan eski emas (yangilangani ham yaroqli)."""
    have = installed_versions(data_dir)
    return not any(_newer(a, have) for a in WHEELS)


def plan(data_dir: Path, plat: str = sys.platform, arch: str | None = None,
         assets: list[Asset] | None = None) -> list[Asset]:
    """Yuklanishi kerak bo'lgan qismlar; `assets` - yangilanish (`resolve_latest`) natijasi.

    yt-dlp va yt-dlp-ejs bitta papkada: bittasi yangilansa ikkalasi birga qayta joylanadi."""
    have = installed_versions(data_dir, plat)
    if assets is None:
        deno = deno_asset(plat, arch)
        wheels = list(WHEELS)
        assets = [*wheels, *([deno] if deno is not None else [])]
    wheels = [a for a in assets if a.name != "deno"]
    out = wheels if any(_newer(a, have) for a in wheels) else []
    return [*out, *(a for a in assets if a.name == "deno" and _newer(a, have))]


def status(data_dir: Path) -> dict[str, Any]:
    todo = plan(data_dir)
    return {"components_ready": not todo, "components_download_bytes": sum(a.size for a in todo),
            "component_versions": installed_versions(data_dir)}


def _pypi_wheel(client: httpx.Client, name: str, version: str | None, license: str) -> Asset:
    r = client.get(PYPI_JSON.format(name=name, version=f"{version}/" if version else ""))
    r.raise_for_status()
    data = r.json()
    ver = str(data["info"]["version"])
    for f in data.get("urls", []):
        if (f.get("packagetype") == "bdist_wheel" and f["filename"].endswith("-py3-none-any.whl")
                and f["url"].startswith(WHEEL_HOST) and 0 < f["size"] <= MAX_WHEEL
                and re.fullmatch(r"[0-9a-f]{64}", f["digests"].get("sha256", ""))):
            return Asset(name, ver, f["url"], f["digests"]["sha256"], f["size"], license)
    raise ComponentError(f"{name} {ver}: sof Python g'ildiragi topilmadi")


def _ejs_pin(client: httpx.Client, ytdlp_version: str) -> str | None:
    """yt-dlp o'zi talab qiladigan yt-dlp-ejs versiyasi (requires_dist: `yt-dlp-ejs==X`)."""
    r = client.get(PYPI_JSON.format(name="yt-dlp", version=f"{ytdlp_version}/"))
    r.raise_for_status()
    for req in r.json()["info"].get("requires_dist") or []:
        m = re.match(r"yt-dlp-ejs\s*==\s*([0-9][0-9.]*)", req)
        if m:
            return m.group(1)
    return None


def _deno_latest(client: httpx.Client, plat: str, arch: str) -> Asset | None:
    triple = _DENO_TRIPLE.get((plat, arch))
    if triple is None:
        return None
    r = client.get(DENO_LATEST, headers={"Accept": "application/vnd.github+json"})
    r.raise_for_status()
    data = r.json()
    ver = str(data["tag_name"]).removeprefix("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+", ver) or _vt(ver)[0] != DENO_MAJOR:
        raise ComponentError(f"Deno {ver}: kutilmagan versiya (faqat {DENO_MAJOR}.x)")
    name = f"deno-{triple}.zip"
    for a in data.get("assets", []):
        digest = str(a.get("digest") or "")
        if (a.get("name") == name and str(a["browser_download_url"]).startswith(DENO_DOWNLOAD)
                and 0 < a["size"] <= MAX_DENO and re.fullmatch(r"sha256:[0-9a-f]{64}", digest)):
            return Asset("deno", ver, a["browser_download_url"], digest.removeprefix("sha256:"),
                         a["size"], "MIT")
    raise ComponentError(f"Deno {ver}: {name} (sha256 bilan) topilmadi")


def resolve_latest(client: httpx.Client | None = None, plat: str = sys.platform,
                   arch: str | None = None) -> list[Asset]:
    """Oxirgi versiyalar (tarmoq; faqat foydalanuvchi so'raganda). Mahkamlangandan eskisi qaytmaydi."""
    arch = arch or _arch()
    own = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(20.0), follow_redirects=True)
    try:
        ytdlp = _pypi_wheel(client, "yt-dlp", None, "Unlicense")
        ejs = _pypi_wheel(client, "yt-dlp-ejs", _ejs_pin(client, ytdlp.version), "Unlicense")
        deno = _deno_latest(client, plat, arch)
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as e:
        raise ComponentError(f"yangilanish ma'lumotini olib bo'lmadi: {e}") from e
    finally:
        if own:
            client.close()
    out = [new if _vt(new.version) >= _vt(pin.version) else pin for new, pin in ((ytdlp, YTDLP), (ejs, EJS))]
    base = deno_asset(plat, arch)
    if deno is not None:
        out.append(deno if base is None or _vt(deno.version) >= _vt(base.version) else base)
    return out


def check_updates(data_dir: Path, client: httpx.Client | None = None) -> dict[str, Any]:
    latest = resolve_latest(client)
    todo = plan(data_dir, assets=latest)
    return {"installed": installed_versions(data_dir), "latest": {a.name: a.version for a in latest},
            "update_available": bool(todo), "download_bytes": sum(a.size for a in todo)}


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


def _write_marker(path: Path, assets: list[Asset]) -> None:
    (path / MARKER).write_text(json.dumps(
        {"versions": {a.name: a.version for a in assets},
         "files": [{"name": a.name, "url": a.url, "sha256": a.sha256, "license": a.license} for a in assets]},
        indent=2), encoding="utf-8")


def install(data_dir: Path, *, consent: bool, cancel: threading.Event | None = None,
            progress: Progress | None = None, client: httpx.Client | None = None,
            plat: str = sys.platform, arch: str | None = None, update: bool = False) -> dict[str, Any]:
    """Yetishmagan (`update=True` bo'lsa - eskirgan ham) komponentlarni yuklab, tekshirib, joylaydi."""
    if consent is not True:
        raise ComponentError("komponentlarni yuklash uchun rozilik kerak")
    with _LOCK:
        assets = resolve_latest(client, plat, arch) if update else None
        todo = plan(data_dir, plat, arch, assets)
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
        wheels = [a for a in todo if a.name != "deno"]
        if wheels:
            files = [fetch(a) for a in wheels]
            staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=base))
            try:
                for f in files:
                    _extract_wheel(f, staging)
                if youtube.find_ytdlp([str(staging)]) is None:
                    raise ComponentError("yt-dlp g'ildiragida yt_dlp paketi topilmadi")
                _write_marker(staging, wheels)
                _publish(staging, base / YTDLP_DIR)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
            installed += [a.name for a in wheels]
        deno = next((a for a in todo if a.name == "deno"), None)
        if deno is not None:
            f = fetch(deno)
            staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=base))
            try:
                _extract_deno(f, staging, "deno.exe" if plat == "win32" else "deno")
                _write_marker(staging, [deno])
                _publish(staging, base / DENO_DIR)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
            installed.append("deno")
        if progress:
            progress(1.0, {"component": None, "downloaded_bytes": total, "total_bytes": total})
        # Yuklangan arxivlar endi kerak emas (keyingi yangilanish yangi versiyani yuklaydi).
        shutil.rmtree(cache, ignore_errors=True)
        return {"components": installed, "component_versions": installed_versions(data_dir, plat),
                **youtube.status(data_dir)}


def uninstall(data_dir: Path) -> None:
    base = root(data_dir)
    for name in (YTDLP_DIR, DENO_DIR, ".downloads"):
        shutil.rmtree(base / name, ignore_errors=True)
