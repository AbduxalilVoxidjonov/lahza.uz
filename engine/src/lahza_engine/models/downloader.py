"""Ishonchli yuklab olish: to'xtasa davom etadi (HTTP Range), disk tekshiruvi, sha256 (TZ 13-bo'lim).

Faqat foydalanuvchi model o'rnatishni boshlaganda chaqiriladi (NFR-01).
"""

from __future__ import annotations

import hashlib
import os
import shutil
from collections.abc import Callable
from pathlib import Path

import httpx

ProgressFn = Callable[[int, int | None], None]


class DownloadError(RuntimeError):
    pass


def sha256_file(path: Path, chunk: int = 4 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def _download_one(
    client: httpx.Client, url: str, part: Path, expected_size: int | None, progress: ProgressFn | None
) -> None:
    have = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    with client.stream("GET", url, headers=headers, follow_redirects=True) as r:
        if r.status_code == 416 and expected_size is not None and have == expected_size:
            return  # allaqachon to'liq
        if r.status_code not in (200, 206):
            raise DownloadError(f"HTTP {r.status_code}: {url}")
        mode = "ab"
        if have and r.status_code == 200:  # server Range'ni qo'llamadi - boshidan
            have, mode = 0, "wb"
        total = expected_size
        if total is None:
            cl = r.headers.get("content-length")
            total = (int(cl) + have) if cl else None
        with part.open(mode) as f:
            for chunk in r.iter_bytes(1024 * 1024):
                f.write(chunk)
                have += len(chunk)
                if progress:
                    progress(have, total)


def download(
    urls: list[str],
    dest: Path,
    sha256: str | None,
    size_bytes: int | None,
    progress: ProgressFn | None = None,
    client: httpx.Client | None = None,
) -> Path:
    if not urls:
        raise DownloadError("URL yo'q")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if size_bytes is not None:
        free = shutil.disk_usage(dest.parent).free
        if free < size_bytes * 1.05:
            raise DownloadError("diskda joy yetarli emas")
    part = dest.with_suffix(dest.suffix + ".part")
    own = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(30.0, read=120.0))
    errors: list[str] = []
    try:
        for url in urls:
            try:
                _download_one(client, url, part, size_bytes, progress)
                break
            except (httpx.HTTPError, DownloadError) as e:
                errors.append(f"{url}: {e}")
        else:
            raise DownloadError("barcha manzillar muvaffaqiyatsiz: " + "; ".join(errors))
    finally:
        if own:
            client.close()
    if size_bytes is not None and part.stat().st_size != size_bytes:
        raise DownloadError(f"hajm mos emas: {part.stat().st_size} != {size_bytes}")
    if sha256 is not None:
        got = sha256_file(part)
        if got.lower() != sha256.lower():
            part.unlink(missing_ok=True)
            raise DownloadError("sha256 mos emas - fayl buzilgan yoki almashtirilgan")
    os.replace(part, dest)
    return dest
