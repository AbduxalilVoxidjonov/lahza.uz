"""FFmpeg imkoniyatlarini aniqlash (filtrlar). Natija ffmpeg yo'li bo'yicha keshlanadi."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from lahza_engine.media.tools import run


class LibassMissing(RuntimeError):
    """FFmpeg libass'siz yig'ilgan - `ass` filtri yo'q, subtitrni videoga chizib bo'lmaydi."""

    def __init__(self, msg: str | None = None) -> None:
        super().__init__(
            msg
            or "FFmpeg libass'siz yig'ilgan: subtitrni videoga chizib bo'lmaydi. "
            "Dastur bilan kelgan FFmpeg'dan foydalaning yoki subtitrsiz eksportni tanlang."
        )


_FILTER_RE = re.compile(r"^\s*[T.][S.][C.]?\s+(\S+)\s+\S+->\S+")


@lru_cache(maxsize=8)
def list_filters(ffmpeg: str) -> frozenset[str]:
    r = run([ffmpeg, "-hide_banner", "-filters"], timeout=30)
    names = set()
    for line in r.stdout.splitlines():
        m = _FILTER_RE.match(line)
        if m:
            names.add(m.group(1))
    return frozenset(names)


def has_filter(ffmpeg: str | Path, name: str) -> bool:
    return name in list_filters(str(ffmpeg))
