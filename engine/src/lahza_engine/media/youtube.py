"""YouTube havolasidan import (YT-1, ADR-0010): yt-dlp alohida jarayonda.

* Tarmoq (NFR-01) faqat shu modul ishga tushiradigan **alohida jarayonda** va amal davomida
  ishlatiladi. Engine jarayoni `yt_dlp`ni import qilmaydi: bolaga faqat havola, chiqish papkasi va
  qo'shimcha sozlamalar (FFmpeg/JS runtime yo'llari) beriladi; u natijani Pipe orqali qaytaradi.
* yt-dlp - PyPI paketi Python kutubxonasi sifatida (`from yt_dlp import YoutubeDL`), rasmiy exe
  EMAS (exe'da GPLv3+ kod bor). Qidiruv tartibi: `LAHZA_YTDLP_PATH` (papka), keyin
  `<data_dir>/Components/yt-dlp` (katalog komponenti uchun joy, ADR-0010 2-band), keyin engine
  muhiti (`pip install -e "engine[youtube]"`).
* `remote_components` bo'sh: yt-dlp-ejs internetdan olinmaydi (u ham komponent sifatida keladi).
* Format: mp4, balandligi <= 1080. Video+audio alohida bo'lsa, loyihadagi FFmpeg bilan
  birlashtiriladi; FFmpeg topilmasa faqat bitta fayldagi (progressiv) mp4 tanlanadi.
* Uzilgan yuklash qayta urinishda davom ettiriladi (`continuedl`, `.part` fayllar saqlanadi);
  bekor qilinganda jarayon o'ldiriladi va qisman fayllar o'chiriladi.
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import json
import multiprocessing as mp
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from lahza_engine.core.runner import Cancelled

MAX_HEIGHT = 1080
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
SHORT_HOSTS = {"youtu.be", "www.youtu.be"}
LIST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{2,64}$")
HANDLE_RE = re.compile(r"^@[A-Za-z0-9._-]{1,100}$")
CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
CHANNEL_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
# Playlist/kanaldan ko'pi bilan shuncha video ko'rsatiladi (ko'pi - `truncated`).
MAX_ENTRIES = 50
RESOLVE_TIMEOUT_S = 120.0
JS_RUNTIMES = ("deno", "node", "bun")
# yt-dlp qo'llaydigan eng past JS runtime versiyalari. Manba - yt-dlp'ning o'zi:
# `yt_dlp/utils/_jsruntime.py` (`DenoJsRuntime/NodeJsRuntime/BunJsRuntime.MIN_SUPPORTED_VERSION`,
# yt-dlp 2026.10.x) va rasmiy wiki https://github.com/yt-dlp/yt-dlp/wiki/EJS (tekshirildi 2026-10-29:
# Deno >= 2.3.0, Node >= 22.0.0, Bun 1.2.11..1.3.14 - Bun eskirgan deb belgilangan). Eskisini yt-dlp
# "unsupported" deb tashlaydi - shuning uchun bunday runtime'ni bolaga bermaymiz.
JS_MIN_VERSIONS: dict[str, tuple[int, ...]] = {"deno": (2, 3, 0), "node": (22, 0, 0), "bun": (1, 2, 11)}
JS_MAX_VERSIONS: dict[str, tuple[int, ...]] = {"bun": (1, 3, 14)}
_JS_VERSION_RE = {"deno": re.compile(r"^deno\s+v?(\d+(?:\.\d+)*)", re.M),
                  "node": re.compile(r"^v?(\d+(?:\.\d+)*)", re.M),
                  "bun": re.compile(r"^v?(\d+(?:\.\d+)*)", re.M)}
# Epizod papkasidagi YouTube manba metama'lumoti (sarlavha, tavsif, boblar).
SOURCE_FILE = "youtube.json"
MAX_DESCRIPTION = 5000
MAX_CHAPTERS = 200
DONE_MARKER = "lahza-download.json"
# Ikki qismli yuklashda (video + audio) umumiy progressdagi ulushlar: video odatda ancha katta.
PART_WEIGHTS = (0.85, 0.15)

# yt-dlp format ifodasi: avval H.264 (avc1) video + m4a audio (FFmpeg bilan birlashtiriladi), keyin
# VP9, oxirgi chora - istalgan kodek. YouTube 1080p'da ko'pincha AV1 ni "eng yaxshi" deb beradi,
# lekin LGPL FFmpeg'imizda dav1d yo'q: AV1 faqat apparat (VideoToolbox) bilan dekodlanadi va
# render "Function not implemented" bilan yiqiladi (jonli sinov, 0.2.1). FFmpeg yo'q bo'lsa -
# faqat bitta fayldagi variant.
_H = f"[height<={MAX_HEIGHT}]"
FORMAT_MERGE = (f"bv{_H}[vcodec^=avc1]+ba[ext=m4a]/"
                f"bv{_H}[vcodec^=vp09]+ba[ext=m4a]/bv{_H}[vcodec^=vp9]+ba[ext=m4a]/"
                f"b{_H}[ext=mp4][vcodec^=avc1]/bv*{_H}[ext=mp4]+ba[ext=m4a]/b{_H}[ext=mp4]/"
                f"bv*{_H}+ba/b{_H}")
FORMAT_SINGLE = f"b{_H}[ext=mp4][vcodec^=avc1]/b{_H}[ext=mp4]/b{_H}"
# Tayyor-fayl belgisi versiyasi: format tanlovi o'zgarsa eski (masalan, AV1) yuklamalar qayta
# ishlatilmaydi - bir marta qayta yuklanadi.
MARKER_VERSION = 2


class InvalidUrl(ValueError):
    """Havola YouTube videosiga ishora qilmaydi (API: 400)."""


class YoutubeError(RuntimeError):
    """Yuklash xatosi: `code` - UI tarjimasi uchun, matn - o'zbekcha tushuntirish."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


MESSAGES: dict[str, str] = {
    "not_installed": "yt-dlp komponenti o'rnatilmagan. Sozlamalar -> YouTube havolasidan import -> "
                     "\"Komponentlarni o'rnatish\" (dasturchi muhitida: `pip install -e \"engine[youtube]\"`).",
    "network": "Internetga ulanib bo'lmadi. Tarmoqni tekshirib, qayta urinib ko'ring - "
               "yuklangan qism saqlanadi va davom ettiriladi.",
    "private": "Video yopiq (private). Faqat egasi yoki ruxsat berilgan hisob ko'ra oladi - "
               "YouTube Studio orqali yuklab oling.",
    "age_restricted": "Videoda yosh cheklovi bor - hisobsiz yuklab bo'lmaydi. "
                      "Asl fayl yoki YouTube Studio'dan foydalaning.",
    "login_required": "YouTube hisobga kirishni talab qilmoqda (a'zolar uchun yoki bot tekshiruvi). "
                      "Asl fayl yoki YouTube Studio'dan foydalaning.",
    "unavailable": "Video mavjud emas (o'chirilgan, bloklangan yoki havola noto'g'ri).",
    "live": "Jonli efir yoki hali boshlanmagan premyera yuklab olinmaydi.",
    "js_runtime": "YouTube uchun JavaScript runtime (Deno 2.3+) va yt-dlp-ejs kerak - "
                  "ular topilmadi.",
    "format_unavailable": "Mos format (mp4, <= 1080p) topilmadi. Ko'pincha sababi - JavaScript "
                          "runtime (Deno) yoki yt-dlp-ejs yo'qligi.",
    "ffmpeg": "Video va audioni birlashtirish uchun FFmpeg topilmadi.",
    "crashed": "Yuklovchi jarayon kutilmaganda to'xtadi.",
    "invalid_url": "Havola YouTube videosiga ishora qilmaydi.",
    "js_outdated": "Topilgan JavaScript runtime yt-dlp uchun juda eski: Deno 2.3+ (yoki Node 22+) kerak. "
                   "Sozlamalarda komponentlarni o'rnating yoki tizimdagi Deno'ni yangilang.",
    "timeout": "YouTube belgilangan vaqtda javob bermadi. Tarmoqni tekshirib, qayta urinib ko'ring.",
    "empty": "Playlist yoki kanalda yuklab olinadigan video topilmadi.",
    "incompatible": "O'rnatilgan yt-dlp versiyasi Lahza'ning bu versiyasi bilan ishlamaydi (kerakli modul "
                    "yetishmayapti). Lahza'ni yangilang yoki Sozlamalar -> YouTube havolasidan import -> "
                    "komponentlarni qayta o'rnating.",
}

_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    # Muzlatilgan ilovada yt-dlp kutgan modul (stdlib yoki bog'liqlik) yo'q - yuklash paytida ham chiqishi mumkin.
    ("incompatible", ("no module named",)),
    ("private", ("private video", "playlist is private")),
    ("age_restricted", ("confirm your age", "age-restricted", "age restricted",
                        "inappropriate for some users")),
    ("login_required", ("not a bot", "login required", "sign in to", "members-only",
                        "join this channel", "use --cookies")),
    ("live", ("live event", "premieres in", "is_live", "this live stream")),
    ("js_runtime", ("javascript runtime", "js runtime", "n challenge", "signature solving",
                    "yt-dlp-ejs", "ejs")),
    ("format_unavailable", ("requested format is not available",)),
    ("ffmpeg", ("ffmpeg not found", "ffmpeg is not installed", "ffprobe and ffmpeg not found",
                "ffmpeg could not be found")),
    ("network", ("getaddrinfo", "name or service not known", "nodename nor servname",
                 "temporary failure in name resolution", "network is unreachable",
                 "connection refused", "timed out", "urlopen error", "connection reset",
                 "failed to resolve", "transporterror", "unable to download webpage",
                 "connectionerror", "no route to host", "ssl")),
    ("unavailable", ("video unavailable", "has been removed", "not available",
                     "copyright", "does not exist", "unsupported url", "404")),
]


def classify_error(text: str) -> tuple[str, str]:
    """yt-dlp xato matni -> (kod, foydalanuvchi uchun o'zbekcha matn)."""
    low = text.lower()
    for code, needles in _PATTERNS:
        if any(n in low for n in needles):
            return code, MESSAGES[code]
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "noma'lum xato")
    first = first.removeprefix("ERROR:").strip()
    return "unknown", f"YouTube'dan yuklab bo'lmadi: {first[:300]}"


def incompatible_error(e: BaseException) -> dict[str, str]:
    """yt-dlp topildi, lekin import qilinmadi: xabarga yetishmayotgan modul nomi qo'shiladi."""
    module = (e.name or "") if isinstance(e, ModuleNotFoundError) else ""
    detail = f"yetishmayotgan modul: {module}" if module else f"{type(e).__name__}: {str(e)[:200]}"
    return {"code": "incompatible", "message": f"{MESSAGES['incompatible']} ({detail})", "module": module}


# ---- havola ------------------------------------------------------------------------------
def _split_url(url: str) -> tuple[str, list[str], str]:
    """Umumiy tekshiruv: (host, yo'l bo'laklari, query). Faqat http(s), login va portsiz."""
    raw = (url or "").strip()
    if not raw:
        raise InvalidUrl("havola bo'sh")
    if "://" not in raw:
        raw = "https://" + raw
    try:
        parts = urlsplit(raw)
        port = parts.port
    except ValueError:
        raise InvalidUrl("havola noto'g'ri") from None
    if parts.scheme not in ("http", "https"):
        raise InvalidUrl("havola http(s) bo'lishi kerak")
    if parts.username or parts.password or port not in (None, 80, 443):
        raise InvalidUrl("havolada login yoki port bo'lmasligi kerak")
    host = (parts.hostname or "").lower().rstrip(".")
    return host, [p for p in parts.path.split("/") if p], parts.query


def parse_video_id(url: str) -> str:
    """youtube.com/watch?v=, youtube.com/shorts/, youtu.be/ havolalaridan video ID.
    Boshqa domenlar, playlist/kanal havolalari va noto'g'ri ID - `InvalidUrl`."""
    host, segs, query = _split_url(url)
    vid: str | None = None
    if host in SHORT_HOSTS:
        vid = segs[0] if len(segs) == 1 else None
    elif host in YOUTUBE_HOSTS:
        if segs == ["watch"]:
            vals = parse_qs(query).get("v", [])
            vid = vals[0] if len(vals) == 1 else None
        elif len(segs) == 2 and segs[0] in ("shorts", "live"):
            vid = segs[1]
    else:
        raise InvalidUrl("faqat youtube.com va youtu.be havolalari qabul qilinadi")
    if not vid or not VIDEO_ID_RE.match(vid):
        raise InvalidUrl("havolada YouTube video ID topilmadi (watch?v=, youtu.be/ yoki shorts/)")
    return vid


def canonical_url(video_id: str) -> str:
    """Bolaga faqat shu kanonik havola beriladi (playlist va boshqa parametrlarsiz)."""
    return f"https://www.youtube.com/watch?v={video_id}"


@dataclass(frozen=True)
class SourceUrl:
    """Tekshirilgan havola: `kind` - video | playlist | channel; `url` - bolaga beriladigan kanonik shakl."""

    kind: str
    url: str
    id: str


def parse_source_url(url: str) -> SourceUrl:
    """Video, playlist (`/playlist?list=`) yoki kanal (`/@nom`, `/channel/UC...`, `/c/nom`, `/user/nom`)
    havolasi. Kanal uchun faqat "Videolar" bo'limi olinadi (shorts/jonli efirlar bo'limlari emas).
    `watch?v=...&list=...` - video sifatida (mavjud qoida: playlist parametri tashlanadi)."""
    host, segs, query = _split_url(url)
    if host not in YOUTUBE_HOSTS and host not in SHORT_HOSTS:
        raise InvalidUrl("faqat youtube.com va youtu.be havolalari qabul qilinadi")
    try:
        vid = parse_video_id(url)
    except InvalidUrl:
        vid = None
    if vid is not None:
        return SourceUrl("video", canonical_url(vid), vid)
    if host in YOUTUBE_HOSTS:
        if segs == ["playlist"]:
            vals = parse_qs(query).get("list", [])
            if len(vals) == 1 and LIST_ID_RE.match(vals[0]):
                return SourceUrl("playlist", f"https://www.youtube.com/playlist?list={vals[0]}", vals[0])
            raise InvalidUrl("playlist havolasida `list` identifikatori topilmadi")
        base: list[str] | None = None
        if segs and HANDLE_RE.match(segs[0]):
            base, rest = segs[:1], segs[1:]
        elif len(segs) >= 2 and ((segs[0] == "channel" and CHANNEL_ID_RE.match(segs[1]))
                                 or (segs[0] in ("c", "user") and CHANNEL_NAME_RE.match(segs[1]))):
            base, rest = segs[:2], segs[2:]
        if base is not None:
            if rest not in ([], ["videos"], ["featured"]):
                raise InvalidUrl("kanaldan faqat \"Videolar\" bo'limi qabul qilinadi")
            path = "/".join(base)
            return SourceUrl("channel", f"https://www.youtube.com/{path}/videos", path)
    raise InvalidUrl("havola YouTube videosi, playlist yoki kanalga ishora qilmaydi")


# ---- komponentlar ------------------------------------------------------------------------
def component_paths(data_dir: Path | None) -> list[str]:
    """yt-dlp (va yt-dlp-ejs) qidiriladigan qo'shimcha papkalar (mavjudlari)."""
    out: list[str] = []
    env = os.environ.get("LAHZA_YTDLP_PATH")
    if env:
        out += [p for p in env.split(os.pathsep) if p]
    if data_dir is not None:
        out.append(str(data_dir / "Components" / "yt-dlp"))
    return [p for p in out if Path(p).is_dir()]


def find_ytdlp(paths: list[str]) -> Path | None:
    """`yt_dlp` paketi papkasi (import qilinmaydi - faqat qidiriladi)."""
    spec = importlib.machinery.PathFinder.find_spec("yt_dlp", [*paths, *sys.path])
    if spec is None or not spec.submodule_search_locations:
        return None
    return Path(next(iter(spec.submodule_search_locations)))


def _version(pkg: Path) -> str | None:
    try:
        m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)", (pkg / "version.py").read_text("utf-8"))
    except OSError:
        return None
    return m.group(1) if m else None


@dataclass(frozen=True)
class JsRuntime:
    name: str
    path: Path
    version: str | None
    supported: bool
    bundled: bool  # ilovaning o'z Deno'si (`Components/deno`)


_JS_VERSION_CACHE: dict[tuple[str, int, float], str | None] = {}


def _vtuple(version: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", version)[:3])


def js_runtime_version(name: str, exe: Path) -> str | None:
    """`<exe> --version` (5 s ichida) -> "2.9.8"; aniqlanmasa None. Fayl o'zgarmasa keshdan."""
    from lahza_engine.media.tools import run

    try:
        st = exe.stat()
    except OSError:
        return None
    key = (str(exe), st.st_size, st.st_mtime)
    if key in _JS_VERSION_CACHE:
        return _JS_VERSION_CACHE[key]
    try:
        out = run([exe, "--version"], timeout=5)
        m = _JS_VERSION_RE[name].search((out.stdout or "") + "\n" + (out.stderr or ""))
        ver = m.group(1) if m and out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        ver = None
    _JS_VERSION_CACHE[key] = ver
    return ver


def js_supported(name: str, version: str | None) -> bool:
    if not version:
        return False  # yt-dlp ham versiyasi aniqlanmagan runtime'ni ishlatmaydi
    vt = _vtuple(version)
    if vt < JS_MIN_VERSIONS[name]:
        return False
    top = JS_MAX_VERSIONS.get(name)
    return top is None or vt[:len(top)] <= top


def js_runtimes(data_dir: Path | None) -> list[JsRuntime]:
    """Topilgan barcha JS runtime'lar afzallik tartibida: avval ilovaning o'z Deno'si, keyin PATH'dagi
    deno/node/bun. Har biri versiyasi bilan (`supported` - yt-dlp talabiga mos)."""
    from lahza_engine.media.tools import ToolNotFound, find_tool

    out: list[JsRuntime] = []
    seen: set[str] = set()

    def add(name: str, path: Path, bundled: bool) -> None:
        k = str(path)
        if k in seen:
            return
        seen.add(k)
        ver = js_runtime_version(name, path)
        out.append(JsRuntime(name, path, ver, js_supported(name, ver), bundled))

    if data_dir is not None:
        for name in JS_RUNTIMES:
            local = data_dir / "Components" / name / (name + (".exe" if sys.platform == "win32" else ""))
            if local.is_file():
                add(name, local, True)
    for name in JS_RUNTIMES:
        try:
            add(name, find_tool(name), False)
        except ToolNotFound:
            continue
    return out


def find_js_runtime(data_dir: Path | None) -> tuple[str, Path] | None:
    """yt-dlp talabiga mos birinchi runtime (eski versiyalar o'tkazib yuboriladi)."""
    return next(((r.name, r.path) for r in js_runtimes(data_dir) if r.supported), None)


def js_outdated_message(found: list[JsRuntime]) -> str:
    olds = ", ".join(f"{r.name} {r.version or '?'}" for r in found)
    return (f"Topilgan JavaScript runtime yt-dlp uchun juda eski ({olds}). Kerak: Deno 2.3+ (yoki Node 22+). "
            "Sozlamalar -> YouTube havolasidan import -> \"Komponentlarni o'rnatish\" ilovaning o'z Deno'sini "
            "o'rnatadi, yoki tizimdagi Deno'ni yangilang (`deno upgrade`).")


def find_ffmpeg() -> Path | None:
    from lahza_engine.media.tools import ToolNotFound, find_tool

    try:
        return find_tool("ffmpeg")
    except ToolNotFound:
        return None


def status(data_dir: Path | None) -> dict[str, Any]:
    """Komponentlar holati (UI: "komponent o'rnatilmagan" va ogohlantirishlar)."""
    paths = component_paths(data_dir)
    pkg = find_ytdlp(paths)
    ejs = importlib.machinery.PathFinder.find_spec("yt_dlp_ejs", [*paths, *sys.path]) is not None
    found = js_runtimes(data_dir)
    js = next((r for r in found if r.supported), None)
    own = data_dir / "Components" / "yt-dlp" if data_dir is not None else None
    ytdlp_source = None
    if pkg is not None:
        ytdlp_source = "components" if own is not None and pkg.is_relative_to(own) else "system"
    return {"installed": pkg is not None, "version": _version(pkg) if pkg else None,
            "ejs": ejs, "js_runtime": js.name if js else None, "ffmpeg": find_ffmpeg() is not None,
            # UI: tizimdagi (venv/PATH) komponentlar ishlatilayotganini va versiyasini ko'rsatish uchun.
            "ytdlp_source": ytdlp_source,
            "js_runtime_version": js.version if js else None,
            "js_runtime_source": ("components" if js.bundled else "system") if js else None,
            "js_runtime_outdated": [{"name": r.name, "version": r.version} for r in found if not r.supported]}


# ---- bola jarayoni -----------------------------------------------------------------------
def build_params(out_dir: Path, ffmpeg: str | None, js_runtime: tuple[str, str] | None) -> dict[str, Any]:
    """YoutubeDL parametrlari (progress hook va logger bolada qo'shiladi)."""
    params: dict[str, Any] = {
        "format": FORMAT_MERGE if ffmpeg else FORMAT_SINGLE,
        "merge_output_format": "mp4",
        "outtmpl": {"default": str(out_dir / "%(id)s.%(ext)s")},
        "continuedl": True,
        "noplaylist": True,
        "overwrites": False,
        "windowsfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "color": "no_color",
        "remote_components": [],  # ejs internetdan olinmaydi (ADR-0010: komponent)
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
    }
    if ffmpeg:
        params["ffmpeg_location"] = ffmpeg
    if js_runtime:
        params["js_runtimes"] = {js_runtime[0]: {"path": js_runtime[1]}}
    return params


class _Sender:
    def __init__(self, conn: Any) -> None:
        self.put = getattr(conn, "send", None) or conn.put


class _Logger:
    """yt-dlp logger: debug/info yutiladi, ogohlantirish va xatolar oxirgi matn sifatida saqlanadi."""

    def __init__(self) -> None:
        self.last: list[str] = []

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        self.last = (self.last + [str(msg)])[-5:]

    def error(self, msg: str) -> None:
        self.last = (self.last + [str(msg)])[-5:]


def _final_path(info: dict[str, Any], out_dir: Path) -> Path | None:
    for d in info.get("requested_downloads") or []:
        fp = d.get("filepath") or d.get("_filename")
        if fp and Path(fp).is_file():
            return Path(fp)
    vid = info.get("id")
    for ext in ("mp4", "mkv", "webm", "mov"):
        p = out_dir / f"{vid}.{ext}"
        if p.is_file():
            return p
    return None


def _import_ytdlp(q: _Sender) -> Any:
    """Bolada `YoutubeDL` klassi; import bo'lmasa xato ota jarayonga yuboriladi va None qaytadi."""
    try:
        from yt_dlp import YoutubeDL
    except Exception as e:  # noqa: BLE001 - import xatosi ota jarayonga kod sifatida
        if find_ytdlp([]) is None or (isinstance(e, ModuleNotFoundError) and e.name == "yt_dlp"):
            q.put(("error", {"code": "not_installed", "message": MESSAGES["not_installed"]}))
        else:
            # Paket bor, lekin u import qiladigan modul yo'q (masalan, muzlatilgan ilovaga kirmagan
            # stdlib moduli) yoki API mos emas: yangi yt-dlp eski Lahza bilan ishlamaydi.
            q.put(("error", incompatible_error(e)))
        return None
    return YoutubeDL


def _ms(v: Any) -> int | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return int(round(f * 1000)) if f >= 0 and f == f else None


def normalize_chapters(raw: Any, duration_s: Any = None) -> list[dict[str, Any]]:
    """yt-dlp `chapters` ([{start_time, end_time, title}], soniya) -> [{start_ms, end_ms, title}].
    Noto'g'ri yozuvlar tashlanadi; tartiblanadi; `end_ms` yo'q bo'lsa keyingi bob boshi/davomiylik."""
    if not isinstance(raw, list):
        return []
    items: list[tuple[int, int | None, str]] = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        start = _ms(c.get("start_time"))
        if start is None:
            continue
        title = str(c.get("title") or "").strip()[:200]
        items.append((start, _ms(c.get("end_time")), title))
    items.sort(key=lambda x: x[0])
    total = _ms(duration_s)
    out: list[dict[str, Any]] = []
    for i, (start, end, title) in enumerate(items[:MAX_CHAPTERS]):
        nxt = items[i + 1][0] if i + 1 < len(items) else total
        end = end if end is not None and end > start else nxt
        if end is None or end <= start:
            continue
        out.append({"start_ms": start, "end_ms": end, "title": title})
    return out


def video_meta(info: dict[str, Any]) -> dict[str, Any]:
    """Bitta video metama'lumoti (Pipe orqali yuboriladigan, kichik va pickle'lanadigan)."""
    desc = info.get("description")
    return {"id": info.get("id"), "title": info.get("title"), "duration": info.get("duration"),
            "description": str(desc)[:MAX_DESCRIPTION] if desc else None,
            "uploader": info.get("uploader") or info.get("channel"),
            "chapters": normalize_chapters(info.get("chapters"), info.get("duration"))}


def child_main(url: str, out_dir: str, params: dict[str, Any], sys_paths: list[str],
               conn: Any) -> None:
    """Alohida jarayon kirish nuqtasi. Xabarlar (`conn.send`, Pipe; testda `queue.put` ham):
    ("info"|"progress"|"done"|"error", dict)."""
    sys.path[:0] = sys_paths
    q = _Sender(conn)
    YoutubeDL = _import_ytdlp(q)  # noqa: N806 - klass
    if YoutubeDL is None:
        return
    out = Path(out_dir)
    parts = 2 if params.get("format") == FORMAT_MERGE else 1
    seen: list[str] = []

    def hook(d: dict[str, Any]) -> None:
        fn = str(d.get("filename") or d.get("tmpfilename") or "")
        if fn and fn not in seen:
            seen.append(fn)
        idx = max(0, min(len(seen), parts) - 1)
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        done = d.get("downloaded_bytes") or 0
        frac = 1.0 if d.get("status") == "finished" else (min(1.0, done / total) if total else 0.0)
        overall = frac if parts == 1 else sum(PART_WEIGHTS[:idx]) + PART_WEIGHTS[idx] * frac
        q.put(("progress", {"fraction": round(overall, 4), "downloaded_bytes": done,
                            "total_bytes": total, "speed": d.get("speed"), "eta": d.get("eta"),
                            "part": idx + 1, "parts": parts}))

    logger = _Logger()
    p = dict(params, progress_hooks=[hook], logger=logger)
    try:
        with YoutubeDL(p) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                raise RuntimeError("video ma'lumoti olinmadi")
            if info.get("_type") in ("playlist", "multi_video"):
                q.put(("error", {"code": "invalid_url", "message": MESSAGES["invalid_url"]}))
                return
            if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
                q.put(("error", {"code": "live", "message": MESSAGES["live"]}))
                return
            meta = video_meta(info)
            q.put(("info", meta))
            info = ydl.process_ie_result(info, download=True)
        path = _final_path(info or {}, out)
        if path is None:
            raise RuntimeError("yuklangan fayl topilmadi")
        q.put(("done", {**meta, "path": str(path)}))
    except BaseException as e:  # noqa: BLE001 - har qanday xato ota jarayonga matn sifatida
        if isinstance(e, ImportError):  # yt-dlp ichidagi kechiktirilgan import (extractor va h.k.)
            q.put(("error", incompatible_error(e)))
            return
        text = "\n".join([str(e), *logger.last])
        code, msg = classify_error(text)
        q.put(("error", {"code": code, "message": msg}))


PRIVATE_TITLES = {"[private video]": "private", "[deleted video]": "unavailable"}
PRIVATE_AVAILABILITY = {"private", "needs_auth", "subscriber_only", "premium_only"}


def _thumbnail(e: dict[str, Any]) -> str | None:
    """Faqat YouTube rasm serveridagi https havola (boshqa domen qaytarilmaydi)."""
    thumbs = e.get("thumbnails") or []
    for t in reversed(thumbs if isinstance(thumbs, list) else []):
        url = str((t or {}).get("url") or "") if isinstance(t, dict) else ""
        try:
            host = (urlsplit(url).hostname or "").lower()
        except ValueError:
            continue
        if url.startswith("https://") and (host == "ytimg.com" or host.endswith(".ytimg.com")):
            return url
    return None


def flat_entry(e: Any) -> dict[str, Any] | None:
    """`extract_flat` elementi -> {id, url, title, duration_s, thumbnail_url, skip}. Video bo'lmagan
    (ichki playlist, kanal bo'limi) element - None. `skip` - nega import qilinmaydi:
    short | live | upcoming | private | unavailable (None - import qilsa bo'ladi)."""
    if not isinstance(e, dict):
        return None
    vid = str(e.get("id") or "")
    if not VIDEO_ID_RE.match(vid) or e.get("_type") not in (None, "url", "video"):
        return None
    title = e.get("title")
    url = str(e.get("url") or "")
    live = e.get("live_status")
    skip: str | None = None
    if isinstance(title, str) and title.strip().lower() in PRIVATE_TITLES:
        skip = PRIVATE_TITLES[title.strip().lower()]
    elif e.get("availability") in PRIVATE_AVAILABILITY:
        skip = "private"
    elif live == "is_live":
        skip = "live"
    elif live == "is_upcoming":
        skip = "upcoming"
    elif "/shorts/" in url:
        skip = "short"
    dur = e.get("duration")
    try:
        duration_s = float(dur) if dur is not None else None
    except (TypeError, ValueError):
        duration_s = None
    return {"id": vid, "url": canonical_url(vid), "title": str(title) if title else None,
            "duration_s": duration_s, "thumbnail_url": _thumbnail(e), "skip": skip}


def listing(info: dict[str, Any], kind: str) -> dict[str, Any]:
    """yt-dlp playlist/kanal natijasi -> API javobi (ko'pi bilan `MAX_ENTRIES`, takrorlarsiz)."""
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    raw = info.get("entries") or []
    count = 0
    for e in raw:
        item = flat_entry(e)
        if item is None or item["id"] in seen:
            continue
        seen.add(item["id"])
        count += 1
        if count <= MAX_ENTRIES:
            entries.append(item)
    total = info.get("playlist_count")
    truncated = count > MAX_ENTRIES or (isinstance(total, int) and total > MAX_ENTRIES)
    return {"kind": kind, "title": info.get("title"), "entries": entries, "truncated": truncated}


def resolve_params(js_runtime: tuple[str, str] | None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "extract_flat": "in_playlist",  # har video sahifasi ochilmaydi - faqat ro'yxat
        "playlistend": MAX_ENTRIES + 1,  # +1: ko'pligini (`truncated`) bilish uchun
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "color": "no_color",
        "remote_components": [],
        "retries": 3,
        "socket_timeout": 30,
    }
    if js_runtime:
        params["js_runtimes"] = {js_runtime[0]: {"path": js_runtime[1]}}
    return params


def resolve_child_main(url: str, kind: str, params: dict[str, Any], sys_paths: list[str], conn: Any) -> None:
    """Playlist/kanal ro'yxatini olish (alohida jarayon). Xabarlar: ("done"|"error", dict)."""
    sys.path[:0] = sys_paths
    q = _Sender(conn)
    YoutubeDL = _import_ytdlp(q)  # noqa: N806 - klass
    if YoutubeDL is None:
        return
    logger = _Logger()
    try:
        with YoutubeDL(dict(params, logger=logger)) as ydl:
            info = ydl.extract_info(url, download=False)
        if info is None:
            raise RuntimeError("ro'yxat ma'lumoti olinmadi")
        q.put(("done", listing(info, kind)))
    except BaseException as e:  # noqa: BLE001 - har qanday xato ota jarayonga matn sifatida
        if isinstance(e, ImportError):
            q.put(("error", incompatible_error(e)))
            return
        code, msg = classify_error("\n".join([str(e), *logger.last]))
        q.put(("error", {"code": code, "message": msg}))


# ---- ota jarayon -------------------------------------------------------------------------
@dataclass
class DownloadResult:
    path: Path
    title: str | None
    video_id: str
    duration_s: float | None = None
    reused: bool = False
    description: str | None = None
    chapters: list[dict[str, Any]] = field(default_factory=list)
    uploader: str | None = None


def _js_for_child(data_dir: Path | None) -> tuple[str, str] | None:
    """Bolaga beriladigan JS runtime. Faqat eski runtime topilgan bo'lsa - aniq xato (yt-dlp uni
    baribir tashlaydi va keyin tushunarsiz "format topilmadi" chiqadi)."""
    found = js_runtimes(data_dir)
    ok = next((r for r in found if r.supported), None)
    if ok is not None:
        return ok.name, str(ok.path)
    if found:
        raise YoutubeError("js_outdated", js_outdated_message(found))
    return None


def resolve(url: str, *, data_dir: Path | None = None, cancel: threading.Event | None = None,
            timeout_s: float = RESOLVE_TIMEOUT_S, target: Callable[..., None] | None = None,
            poll_s: float = 0.2) -> dict[str, Any]:
    """Havola -> {kind, title, entries, truncated}. Bitta video - tarmoqsiz (ro'yxatda bitta element);
    playlist/kanal - yt-dlp `extract_flat` bilan alohida jarayonda. Xato - `YoutubeError`."""
    src = parse_source_url(url)
    if src.kind == "video":
        return {"kind": "video", "title": None, "truncated": False,
                "entries": [{"id": src.id, "url": src.url, "title": None, "duration_s": None,
                             "thumbnail_url": None, "skip": None}]}
    paths = component_paths(data_dir)
    if find_ytdlp(paths) is None:
        raise YoutubeError("not_installed", MESSAGES["not_installed"])
    params = resolve_params(_js_for_child(data_dir))
    ctx = mp.get_context("spawn")
    reader, writer = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=target or resolve_child_main, args=(src.url, src.kind, params, paths, writer),
                       name="lahza-youtube-resolve", daemon=True)
    proc.start()
    writer.close()
    deadline = time.monotonic() + timeout_s
    try:
        while True:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            if time.monotonic() > deadline:
                raise YoutubeError("timeout", MESSAGES["timeout"])
            if not reader.poll(poll_s):
                continue
            try:
                kind, data = reader.recv()
            except (EOFError, OSError):
                raise YoutubeError("crashed", MESSAGES["crashed"]) from None
            if kind == "error":
                raise YoutubeError(str(data.get("code") or "unknown"),
                                   str(data.get("message") or MESSAGES["crashed"]))
            if kind == "done":
                return data
    finally:
        if proc.is_alive():
            proc.join(1)
        if proc.is_alive():
            _kill(proc)
        with contextlib.suppress(Exception):
            reader.close()


# ---- epizod manbasi (cache/youtube.json) ---------------------------------------------------
def source_path(project_dir: Path) -> Path:
    return project_dir / "cache" / SOURCE_FILE


def write_source(project_dir: Path, url: str, res: DownloadResult) -> dict[str, Any]:
    """Epizod papkasiga YouTube manbasi: havola, ID, sarlavha, tavsif, boblar."""
    data = {"kind": "youtube", "url": url, "video_id": res.video_id, "title": res.title,
            "uploader": res.uploader, "duration_s": res.duration_s, "description": res.description,
            "chapters": res.chapters}
    p = source_path(project_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def read_source(project_dir: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(source_path(project_dir).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("kind") != "youtube":
        return None
    data["chapters"] = [c for c in data.get("chapters") or [] if isinstance(c, dict)
                        and isinstance(c.get("start_ms"), int) and isinstance(c.get("end_ms"), int)]
    return data


def chapter_starts(project_dir: Path) -> list[int]:
    """Lite highlight uchun bob boshlanishlari (ms). Manba YouTube bo'lmasa - bo'sh."""
    src = read_source(project_dir)
    return [int(c["start_ms"]) for c in src["chapters"]] if src else []


ProgressFn = Callable[[float, dict[str, Any]], None]


def _kill(proc: Any) -> None:
    with contextlib.suppress(Exception):
        proc.terminate()
        proc.join(3)
    if proc.is_alive():
        with contextlib.suppress(Exception):
            proc.kill()
            proc.join(3)


def cleanup_partial(out_dir: Path) -> None:
    """Bekor qilinganda: shu video uchun ajratilgan papka butunlay o'chiriladi."""
    shutil.rmtree(out_dir, ignore_errors=True)


def _reuse(out_dir: Path, video_id: str) -> DownloadResult | None:
    """Oldin to'liq yuklangan bo'lsa - tarmoqsiz qayta ishlatiladi."""
    marker = out_dir / DONE_MARKER
    try:
        data = json.loads(marker.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    path = Path(data.get("path") or "")
    if data.get("id") != video_id or data.get("v") != MARKER_VERSION or not path.is_file():
        return None
    return DownloadResult(path, data.get("title"), video_id, data.get("duration"), reused=True,
                          description=data.get("description"), chapters=list(data.get("chapters") or []),
                          uploader=data.get("uploader"))


def download(url: str, out_dir: Path, *, cancel: threading.Event,
             on_progress: ProgressFn | None = None,
             on_info: Callable[[dict[str, Any]], None] | None = None,
             data_dir: Path | None = None,
             keep_partial: Callable[[], bool] | None = None,
             target: Callable[..., None] | None = None,
             poll_s: float = 0.2) -> DownloadResult:
    """Videoni `out_dir` ga yuklaydi (alohida jarayonda). `cancel` o'rnatilsa jarayon o'ldiriladi
    va qisman fayllar o'chiriladi (`keep_partial()` True bo'lsa - masalan, engine to'xtayotganda -
    qoldiriladi, keyingi urinish davom ettiradi). Xato - `YoutubeError`, bekor - `Cancelled`."""
    video_id = parse_video_id(url)
    url = canonical_url(video_id)
    reused = _reuse(out_dir, video_id)
    if reused is not None:
        if on_progress:
            on_progress(1.0, {"fraction": 1.0, "reused": True})
        return reused
    if (out_dir / DONE_MARKER).exists():
        # Eski versiyadagi tayyor yuklama: yt-dlp mavjud `<id>.mp4` ni "allaqachon yuklangan" deb
        # qaytarmasligi uchun papka tozalanadi (qisman fayl yo'q - yuklama to'liq tugagan edi).
        cleanup_partial(out_dir)
    paths = component_paths(data_dir)
    if find_ytdlp(paths) is None:
        raise YoutubeError("not_installed", MESSAGES["not_installed"])
    ffmpeg = find_ffmpeg()
    js = _js_for_child(data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    params = build_params(out_dir, str(ffmpeg) if ffmpeg else None, js)

    ctx = mp.get_context("spawn")
    # Pipe (semaforsiz): bola o'lsa o'qishda EOFError - "crashed".
    reader, writer = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=target or child_main, args=(url, str(out_dir), params, paths, writer),
                       name=f"lahza-youtube-{video_id}", daemon=True)
    proc.start()
    writer.close()  # ota jarayonda yozuvchi uchi yopiladi, aks holda EOF kelmaydi
    last = 0.0
    try:
        while True:
            if cancel.is_set():
                _kill(proc)
                if not (keep_partial and keep_partial()):
                    cleanup_partial(out_dir)
                raise Cancelled()
            if not reader.poll(poll_s):
                continue
            try:
                kind, data = reader.recv()
            except (EOFError, OSError):
                raise YoutubeError("crashed", MESSAGES["crashed"]) from None
            if kind == "progress":
                last = max(last, float(data.get("fraction") or 0.0))
                if on_progress:
                    on_progress(min(last, 0.999), data)
            elif kind == "info":
                if on_info:
                    on_info(data)
            elif kind == "error":
                raise YoutubeError(str(data.get("code") or "unknown"),
                                   str(data.get("message") or MESSAGES["crashed"]))
            elif kind == "done":
                path = Path(data["path"])
                res = DownloadResult(path, data.get("title"), video_id, data.get("duration"),
                                     description=data.get("description"),
                                     chapters=list(data.get("chapters") or []), uploader=data.get("uploader"))
                (out_dir / DONE_MARKER).write_text(json.dumps(
                    {"v": MARKER_VERSION, "id": video_id, "path": str(path), "title": res.title,
                     "duration": res.duration_s, "description": res.description, "chapters": res.chapters,
                     "uploader": res.uploader}, ensure_ascii=False), encoding="utf-8")
                if on_progress:
                    on_progress(1.0, {"fraction": 1.0})
                return res
    finally:
        if proc.is_alive():
            proc.join(5)
            if proc.is_alive():
                _kill(proc)
        with contextlib.suppress(Exception):
            reader.close()
