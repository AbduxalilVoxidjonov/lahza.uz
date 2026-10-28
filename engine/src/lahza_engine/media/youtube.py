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
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from lahza_engine.core.runner import Cancelled

MAX_HEIGHT = 1080
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
SHORT_HOSTS = {"youtu.be", "www.youtu.be"}
JS_RUNTIMES = ("deno", "node", "bun")
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
}

_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("private", ("private video",)),
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


# ---- havola ------------------------------------------------------------------------------
def parse_video_id(url: str) -> str:
    """youtube.com/watch?v=, youtube.com/shorts/, youtu.be/ havolalaridan video ID.
    Boshqa domenlar, playlist/kanal havolalari va noto'g'ri ID - `InvalidUrl`."""
    raw = (url or "").strip()
    if not raw:
        raise InvalidUrl("havola bo'sh")
    if "://" not in raw:
        raw = "https://" + raw
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https"):
        raise InvalidUrl("havola http(s) bo'lishi kerak")
    if parts.username or parts.password or parts.port not in (None, 80, 443):
        raise InvalidUrl("havolada login yoki port bo'lmasligi kerak")
    host = (parts.hostname or "").lower().rstrip(".")
    segs = [p for p in parts.path.split("/") if p]
    vid: str | None = None
    if host in SHORT_HOSTS:
        vid = segs[0] if len(segs) == 1 else None
    elif host in YOUTUBE_HOSTS:
        if segs == ["watch"]:
            vals = parse_qs(parts.query).get("v", [])
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


def find_js_runtime(data_dir: Path | None) -> tuple[str, Path] | None:
    from lahza_engine.media.tools import ToolNotFound, find_tool

    for name in JS_RUNTIMES:
        if data_dir is not None:
            exe = name + (".exe" if sys.platform == "win32" else "")
            local = data_dir / "Components" / name / exe
            if local.is_file():
                return name, local
        try:
            return name, find_tool(name)
        except ToolNotFound:
            continue
    return None


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
    js = find_js_runtime(data_dir)
    return {"installed": pkg is not None, "version": _version(pkg) if pkg else None,
            "ejs": ejs, "js_runtime": js[0] if js else None, "ffmpeg": find_ffmpeg() is not None}


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


def child_main(url: str, out_dir: str, params: dict[str, Any], sys_paths: list[str],
               conn: Any) -> None:
    """Alohida jarayon kirish nuqtasi. Xabarlar (`conn.send`, Pipe; testda `queue.put` ham):
    ("info"|"progress"|"done"|"error", dict)."""
    sys.path[:0] = sys_paths
    q = _Sender(conn)
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        q.put(("error", {"code": "not_installed", "message": MESSAGES["not_installed"]}))
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
            q.put(("info", {"id": info.get("id"), "title": info.get("title"),
                            "duration": info.get("duration")}))
            info = ydl.process_ie_result(info, download=True)
        path = _final_path(info or {}, out)
        if path is None:
            raise RuntimeError("yuklangan fayl topilmadi")
        q.put(("done", {"path": str(path), "title": (info or {}).get("title"),
                        "id": (info or {}).get("id"), "duration": (info or {}).get("duration")}))
    except BaseException as e:  # noqa: BLE001 - har qanday xato ota jarayonga matn sifatida
        text = "\n".join([str(e), *logger.last])
        code, msg = classify_error(text)
        q.put(("error", {"code": code, "message": msg}))


# ---- ota jarayon -------------------------------------------------------------------------
@dataclass
class DownloadResult:
    path: Path
    title: str | None
    video_id: str
    duration_s: float | None = None
    reused: bool = False


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
    return DownloadResult(path, data.get("title"), video_id, data.get("duration"), reused=True)


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
    js = find_js_runtime(data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    params = build_params(out_dir, str(ffmpeg) if ffmpeg else None,
                          (js[0], str(js[1])) if js else None)

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
                res = DownloadResult(path, data.get("title"), video_id, data.get("duration"))
                (out_dir / DONE_MARKER).write_text(json.dumps(
                    {"v": MARKER_VERSION, "id": video_id, "path": str(path), "title": res.title,
                     "duration": res.duration_s}, ensure_ascii=False), encoding="utf-8")
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
