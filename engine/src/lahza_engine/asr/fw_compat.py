"""faster-whisper'ni PyAV'siz yuklash (ADR-0015).

`faster_whisper/audio.py` modul darajasida `import av` qiladi, lekin `av` faqat
`decode_audio()` ichida ishlatiladi; u esa `transcribe()` ga numpy massiv berilganda
chaqirilmaydi. Desktop to'plamda PyAV yo'q (GPL libx264/libx265 bilan yig'ilgan FFmpeg'ni
olib keladi), shuning uchun faster-whisper import qilinishidan oldin `sys.modules["av"]` ga
qo'riqchi modul qo'yiladi:

* `import av` muvaffaqiyatli o'tadi (faster-whisper import bo'ladi);
* `av` ning istalgan atributiga murojaat `PyAvBlocked` bilan yiqiladi - ya'ni kod qaysidir
  yo'l bilan PyAV dekodiga tushsa, jimgina GPL kodga emas, aniq xatoga keladi.

Qo'riqchi dasturchi muhitida ham (PyAV o'rnatilgan bo'lsa ham) qo'yiladi: reliz va dev
xatti-harakati bir xil bo'ladi. Faqat haqiqiy PyAV jarayonga allaqachon yuklangan bo'lsa
(boshqa kod import qilgan) unga tegilmaydi - bu holat `av_guard_active()` bilan aniqlanadi.

faster-whisper'ni HAR DOIM `import_faster_whisper()` orqali yuklang.
"""

from __future__ import annotations

import sys
import types
from typing import Any

_MESSAGE = (
    "PyAV (`av`) Lahza'da ishlatilmaydi (ADR-0015: PyAV g'ildiraklari GPL FFmpeg olib keladi). "
    "Audio'ni lahza_engine.media.pcm.decode_pcm_f32 bilan dekod qilib, massiv sifatida bering."
)


class PyAvBlocked(RuntimeError):
    pass


class _AvGuard(types.ModuleType):
    """`import av` ni qondiradi, lekin har qanday foydalanishni rad etadi."""

    __lahza_av_guard__ = True

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        raise PyAvBlocked(_MESSAGE + f" (so'ralgan: av.{name})")


def install_av_guard() -> bool:
    """`sys.modules["av"]` ga qo'riqchini qo'yadi. Qo'riqchi faol bo'lsa True."""
    existing = sys.modules.get("av")
    if getattr(existing, "__lahza_av_guard__", False):
        return True
    if existing is not None:
        # Haqiqiy PyAV boshqa kod tomonidan allaqachon yuklangan (faqat dev muhitda mumkin).
        return False
    guard = _AvGuard("av", _MESSAGE)
    sys.modules["av"] = guard
    return True


def av_guard_active() -> bool:
    return bool(getattr(sys.modules.get("av"), "__lahza_av_guard__", False))


def import_faster_whisper() -> Any:
    """faster_whisper modulini PyAV'siz qaytaradi."""
    install_av_guard()
    import faster_whisper

    return faster_whisper
