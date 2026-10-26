"""Barqaror xato kodlari: yiqilgan vazifa / navbat elementi -> `error_code` + `error_params`.

UI xom matnni emas, kodni tarjima qiladi (app/src/lib/error-codes.ts). Xom matn (`error`)
orqaga moslik va "batafsil" uchun o'zgarishsiz saqlanadi.

Tasniflash tartibi (`classify`):
1. Istisnoning o'z `code` atributi (masalan, `UnsupportedCodec`, `YoutubeError`, `CodedError`).
2. Engine istisnolari (sinf nomi bo'yicha - `media/` va boshqa modullarni import qilmaslik uchun).
3. Python/OS istisnolari (FileNotFoundError, ENOSPC, MemoryError, TimeoutError, tarmoq ...).
4. Xabar matni bo'yicha (`classify_message`) - engine qayta ishga tushgach bazadagi eski
   navbat xatolari uchun ham ishlatiladi.

Parametrlarda faqat qisqa, xavfsiz qiymatlar (fayl nomi, vosita nomi, ffmpeg kodi) - to'liq yo'l
yoki transkript matni emas (NFR-02).
"""

from __future__ import annotations

import errno
import re
import subprocess
from pathlib import PurePath
from typing import Any

FILE_NOT_FOUND = "file_not_found"
MEDIA_INVALID = "media_invalid"
NO_AUDIO = "no_audio"
FFMPEG_FAILED = "ffmpeg_failed"
TOOL_MISSING = "tool_missing"
LIBASS_MISSING = "libass_missing"
MODEL_MISSING = "model_missing"
DISK_FULL = "disk_full"
PERMISSION_DENIED = "permission_denied"
OUT_OF_MEMORY = "out_of_memory"
TIMEOUT = "timeout"
NETWORK = "network"  # YoutubeError("network") bilan bir xil kod
DOWNLOAD_FAILED = "download_failed"
CANCELLED = "cancelled"
ALREADY_RUNNING = "already_running"
UNSUPPORTED_CODEC = "unsupported_codec"  # media/codec_check.py dagi bilan bir xil

CODES = (FILE_NOT_FOUND, MEDIA_INVALID, NO_AUDIO, FFMPEG_FAILED, TOOL_MISSING, LIBASS_MISSING,
         MODEL_MISSING, DISK_FULL, PERMISSION_DENIED, OUT_OF_MEMORY, TIMEOUT, NETWORK,
         DOWNLOAD_FAILED, CANCELLED, ALREADY_RUNNING, UNSUPPORTED_CODEC)

Coded = tuple[str, dict[str, str]]


class CodedError(RuntimeError):
    """Kodli xato: matn - o'zbekcha (eski `error` maydoni), `code`/`params` - UI tarjimasi uchun."""

    def __init__(self, code: str, message: str, **params: Any) -> None:
        super().__init__(message)
        self.code = code
        self.params = {k: str(v) for k, v in params.items() if v is not None}


def _name(path: Any) -> str:
    try:
        return PurePath(str(path)).name or str(path)
    except (TypeError, ValueError):
        return ""


def _mro_names(e: BaseException) -> set[str]:
    return {c.__name__ for c in type(e).__mro__}


_FFMPEG_RC = re.compile(r"ffmpeg\s+(-?\d+)", re.I)
_TOOL = re.compile(r"'([\w.-]+)' topilmadi")
_MISSING_FILE = re.compile(r"fayl(?:i)? topilmadi:?\s*(.*)", re.I)

# (kod, kichik harfdagi bo'laklar) - birinchi mos kelgani olinadi.
_MESSAGE_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    (UNSUPPORTED_CODEC, ("lahza uni hali o'qiy olmaydi",)),
    (DISK_FULL, ("no space left", "diskda joy", "disk full", "not enough space")),
    (OUT_OF_MEMORY, ("out of memory", "cannot allocate memory", "xotira yetmadi")),
    (MODEL_MISSING, ("modeli o'rnatilmagan", "model o'rnatilmagan", "model not installed")),
    (LIBASS_MISSING, ("libass",)),
    (NO_AUDIO, ("ovoz yo'lagi topilmadi",)),
    (FILE_NOT_FOUND, ("fayl topilmadi", "no such file or directory", "file not found")),
    (PERMISSION_DENIED, ("permission denied", "ruxsat yo'q", "operation not permitted")),
    (ALREADY_RUNNING, ("allaqachon tahlil qilinmoqda",)),
    (TIMEOUT, ("timed out", "timeout")),
    (NETWORK, ("getaddrinfo", "network is unreachable", "connection refused", "connection reset",
               "name or service not known", "temporary failure in name resolution")),
    (FFMPEG_FAILED, ("ffmpeg", "ffprobe")),
    (CANCELLED, ("bekor qilindi",)),
]


def classify_message(text: str | None) -> Coded | None:
    """Xabar matni bo'yicha taxminiy tasnif (kod yozilmagan eski yozuvlar uchun)."""
    if not text:
        return None
    if m := _TOOL.search(text):
        return TOOL_MISSING, {"tool": m.group(1)}
    low = text.lower()
    for code, needles in _MESSAGE_PATTERNS:
        if any(n in low for n in needles):
            params: dict[str, str] = {}
            if code == FILE_NOT_FOUND and (m := _MISSING_FILE.search(text)) and m.group(1).strip():
                params["path"] = _name(m.group(1).strip().split(",")[0].strip())
            elif code == FFMPEG_FAILED and (m := _FFMPEG_RC.search(text)):
                params["rc"] = m.group(1)
            return code, params
    return None


def _from_os_error(e: OSError) -> Coded | None:
    if isinstance(e, FileNotFoundError) or e.errno == errno.ENOENT:
        return FILE_NOT_FOUND, ({"path": _name(e.filename)} if e.filename else {})
    if e.errno in (errno.ENOSPC, getattr(errno, "EDQUOT", -1)):
        return DISK_FULL, {}
    if isinstance(e, PermissionError) or e.errno in (errno.EACCES, errno.EPERM):
        return PERMISSION_DENIED, ({"path": _name(e.filename)} if e.filename else {})
    if isinstance(e, TimeoutError) or e.errno == errno.ETIMEDOUT:
        return TIMEOUT, {}
    if isinstance(e, ConnectionError):
        return NETWORK, {}
    return None


def classify(e: BaseException) -> Coded | None:
    """Istisno -> (kod, parametrlar) yoki tanilmasa None."""
    code = getattr(e, "code", None)
    if isinstance(code, str) and code:
        params = getattr(e, "params", None)
        return code, ({str(k): str(v) for k, v in params.items()} if isinstance(params, dict) else {})
    names = _mro_names(e)
    msg = str(e)
    if names & {"Cancelled", "AnalysisCancelled"}:
        return CANCELLED, {}
    if "MissingModel" in names:
        return MODEL_MISSING, {}
    if "LibassMissing" in names:
        return LIBASS_MISSING, {}
    if "ToolNotFound" in names:
        m = _TOOL.search(msg)
        return TOOL_MISSING, ({"tool": m.group(1)} if m else {})
    if "DownloadError" in names:  # models/downloader.py
        return classify_message(msg) if "diskda joy" in msg else (DOWNLOAD_FAILED, {})
    if "MediaError" in names:
        found = classify_message(msg)
        if found and found[0] in (FILE_NOT_FOUND, NO_AUDIO):
            return found
        return MEDIA_INVALID, {}
    if isinstance(e, subprocess.TimeoutExpired):
        return TIMEOUT, {}
    if isinstance(e, subprocess.CalledProcessError):
        return FFMPEG_FAILED, {"rc": str(e.returncode)}
    if isinstance(e, MemoryError):
        return OUT_OF_MEMORY, {}
    if isinstance(e, OSError) and (found := _from_os_error(e)):
        return found
    if names & {"URLError", "ConnectError", "ConnectTimeout", "ReadTimeout", "NetworkError",
                "TransportError", "gaierror"}:
        return (TIMEOUT, {}) if "Timeout" in "".join(names) else (NETWORK, {})
    return classify_message(msg)


def annotate(meta: dict[str, Any], e: BaseException) -> None:
    """Vazifa meta'siga `error_code`/`error_params` (allaqachon yozilgan bo'lsa tegmaydi)."""
    if "error_code" in meta:
        return
    found = classify(e)
    if found is not None:
        meta["error_code"], meta["error_params"] = found[0], dict(found[1])
