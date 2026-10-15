from __future__ import annotations

import functools
import os
import shutil
import socket
import subprocess

import pytest

from lahza_engine.types import Sentence, Word


def make_words(text: str, start_ms: int = 0, word_ms: int = 300, gap_ms: int = 50,
               speaker: str | None = None) -> list[Word]:
    out, t = [], start_ms
    for tok in text.split():
        out.append(Word(text=tok, start_ms=t, end_ms=t + word_ms, speaker=speaker))
        t += word_ms + gap_ms
    return out


def make_sentences(n: int, dur_ms: int = 6000, pause_ms: int = 400, words: int = 12) -> list[Sentence]:
    out, t = [], 0
    word_ms = dur_ms // words
    for i in range(n):
        ws = [Word(text=f"so'z{i}_{k}" + ("." if k == words - 1 else ""), start_ms=t + k * word_ms,
                   end_ms=t + (k + 1) * word_ms - 20) for k in range(words)]
        out.append(Sentence(id=i, start_ms=ws[0].start_ms, end_ms=ws[-1].end_ms, words=ws))
        t += dur_ms + pause_ms
    return out


HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

requires_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg yo'q")


@functools.cache
def ffmpeg_filters() -> frozenset[str]:
    """`ffmpeg -filters` dagi filtr nomlari (ffmpeg yo'q yoki xato bo'lsa - bo'sh)."""
    if not HAS_FFMPEG:
        return frozenset()
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True,
                           timeout=30)
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    names = set()
    for line in r.stdout.splitlines():
        parts = line.split()
        # Qator ko'rinishi: " TS ass   V->V   Render ASS subtitles..."
        if len(parts) >= 3 and "->" in parts[2]:
            names.add(parts[1])
    return frozenset(names)


def has_libass() -> bool:
    return "ass" in ffmpeg_filters()


# Subtitr (ASS) yoqib yozadigan testlar: ffmpeg `--enable-libass` bilan yig'ilgan bo'lishi shart.
# Homebrew'ning standart `ffmpeg` formulasi libass'siz bo'lishi mumkin (docs/03-dasturchi-muhiti.md).
# CI'da LAHZA_REQUIRE_LIBASS=1: skip o'rniga test ishlaydi (va yiqiladi) - jimgina o'tkazib yuborilmaydi.
requires_libass = pytest.mark.skipif(
    not has_libass() and os.environ.get("LAHZA_REQUIRE_LIBASS") != "1",
    reason="ffmpeg libass'siz yig'ilgan (`ffmpeg -filters` da `ass` filtri yo'q) - "
           "subtitr render testlari o'tkazib yuborildi; docs/03-dasturchi-muhiti.md ga qarang",
)


# --- NFR-01: tarmoqsiz rejim -------------------------------------------------------------
# LAHZA_NO_NETWORK=1 bo'lsa har bir test davomida loopback'dan boshqa manzilga ulanish taqiqlanadi.
# CI'dagi "NFR-01" bosqichi shu rejimda ishlaydi (Linux'da qo'shimcha `unshare -rn` bilan).

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", "0.0.0.0", "testserver", ""}


class NetworkBlockedError(RuntimeError):
    """Testda tashqi tarmoqqa urinish (NFR-01 buzilishi)."""


def _is_local(address: object) -> bool:
    if isinstance(address, tuple) and address:
        host = str(address[0])
        return host in _LOOPBACK_HOSTS or host.startswith("127.")
    # AF_UNIX yo'llari va boshqalar - tarmoq emas.
    return isinstance(address, (str, bytes))


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.environ.get("LAHZA_NO_NETWORK") != "1":
        return
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def guard(address: object) -> None:
        if not _is_local(address):
            raise NetworkBlockedError(f"NFR-01: testda tarmoqqa ulanishga urinish: {address!r}")

    def connect(self: socket.socket, address: object) -> None:
        guard(address)
        return real_connect(self, address)

    def connect_ex(self: socket.socket, address: object) -> int:
        guard(address)
        return real_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):  # type: ignore[no-untyped-def]
        h = host.decode() if isinstance(host, bytes) else host
        if h is not None and not _is_local((h,)):
            raise NetworkBlockedError(f"NFR-01: testda DNS so'rovi: {h!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
