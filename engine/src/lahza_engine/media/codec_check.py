"""Video kodekini dekodlash mumkinligini tekshirish (import va render himoyasi).

FFmpeg'ning ichki `av1` dekoderi faqat apparat tezlatish bilan ishlaydi, VideoToolbox esa uni
ulamaydi -> "Your platform doesn't support hardware accelerated AV1 decoding" va ffmpeg 69 kodi.
AV1 ni dasturiy dekodlash uchun libdav1d (BSD-2) kerak: `scripts/setup_local_render.py` uni
statik yig'ib FFmpeg'ga ulaydi (0.2.2 gacha bundled ffmpeg'da yo'q edi). Ishlatilayotgan ffmpeg'da
dav1d bormi - `ffmpeg -decoders` orqali dinamik aniqlanadi (`software_decoders`). Audio orqali
tahlil o'tib ketadi-yu, eksport tushunarsiz xato bilan yiqilmasligi uchun:

* import paytida (`check_decodable`) - AV1 uchun avval dasturiy dekoder (libdav1d/libaom-av1)
  ro'yxatda bormi tekshiriladi: yo'q bo'lsa darhol rad etiladi (ichki `av1` ro'yxatda bor, lekin
  ishlamaydi - u hisobga olinmaydi). So'ng epizod yaratilishidan oldin birinchi kadr haqiqatan
  dekodlab ko'riladi;
* render paytida (`raise_if_decoder_failure`) - ffmpeg logidagi dekoder xatosi tanilib, xom log
  o'rniga `unsupported_codec` kodli tushunarli xato qaytariladi.

Transkod (H.264 proksi) yo'li tanlanmadi: transkod uchun ham manbani dekodlash kerak, bundled
ffmpeg buni aynan shu kodeklar uchun qila olmaydi.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path

from lahza_engine.media.tools import ToolNotFound, find_tool, run

UNSUPPORTED_CODEC = "unsupported_codec"

_LABELS = {
    "av1": "AV1", "hevc": "HEVC (H.265)", "h264": "H.264", "vp8": "VP8", "vp9": "VP9",
    "prores": "ProRes", "vvc": "VVC (H.266)", "mpeg4": "MPEG-4", "mpeg2video": "MPEG-2",
}

# Faqat "dekoder umuman ishlay olmaydi" belgilari. Buzuq kadrlar (Invalid data ...) bu yerga
# kirmaydi - ular boshqa xato, kodek muammosi emas.
_DECODER_FAILURE = re.compile(
    r"doesn't support hardware accelerated (?P<hw>\w+) decoding"
    r"|Decoder \(codec (?P<nf>\w+)\) not found"
    r"|\[(?:dec:)?(?P<sub>\w+) @ [^\]]+\] Error submitting packet to decoder: Function not implemented"
    r"|\[(?P<pix>\w+) @ [^\]]+\] Failed to get pixel format",
    re.IGNORECASE,
)


# Apparat tezlatishsiz ishlamaydigan ichki dekoderli kodeklar -> ishlaydigan dasturiy dekoderlar.
# Ro'yxatdan birortasi ffmpeg'da bo'lmasa, kodek "qo'llab-quvvatlanmaydi" deb hisoblanadi.
SOFTWARE_DECODERS: dict[str, tuple[str, ...]] = {"av1": ("libdav1d", "libaom-av1")}


def parse_decoders(output: str) -> frozenset[str]:
    """`ffmpeg -decoders` chiqishidan dekoder nomlari (" V....D libdav1d  dav1d AV1 decoder ...")."""
    names = set()
    for line in (output or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and len(parts[0]) == 6 and parts[0][0] in "VAS" and parts[1] != "=":
            names.add(parts[1])
    return frozenset(names)


@lru_cache(maxsize=8)
def _decoders_cached(ffmpeg: str, _mtime_ns: int) -> frozenset[str] | None:
    return _query_decoders(ffmpeg)


def _query_decoders(ffmpeg: str) -> frozenset[str] | None:
    try:
        r = run([ffmpeg, "-hide_banner", "-decoders"], timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    names = parse_decoders(r.stdout) if r.returncode == 0 else frozenset()
    return names or None  # bo'sh ro'yxat = aniqlab bo'lmadi


def software_decoders(ffmpeg: str | os.PathLike[str]) -> frozenset[str] | None:
    """ffmpeg'dagi dekoderlar to'plami (fayl o'zgarmaguncha keshlanadi). Aniqlab bo'lmasa - None."""
    try:
        mtime = Path(ffmpeg).stat().st_mtime_ns
    except OSError:
        return _query_decoders(str(ffmpeg))
    return _decoders_cached(str(ffmpeg), mtime)


def codec_supported(codec: str | None, ffmpeg: str | os.PathLike[str]) -> bool | None:
    """Kodek uchun ishlaydigan dasturiy dekoder bormi: True/False, ro'yxat olinmasa None."""
    needed = SOFTWARE_DECODERS.get((codec or "").lower())
    if not needed:
        return True
    decoders = software_decoders(ffmpeg)
    if decoders is None:
        return None
    return any(d in decoders for d in needed)


def codec_label(codec: str | None) -> str:
    if not codec:
        return "?"
    return _LABELS.get(codec.lower(), codec.upper())


def unsupported_message(codec: str | None) -> str:
    return (f"Bu video {codec_label(codec)} formatida, Lahza uni hali o'qiy olmaydi - "
            "videoni H.264 formatiga o'girib, qayta import qiling")


class UnsupportedCodec(RuntimeError):
    """Video kodekini bundled ffmpeg dekodlay olmaydi. `code`/`params` vazifa meta'siga
    (`error_code`, `error_params`) yoziladi - UI tarjima qilingan matn ko'rsatadi."""

    code = UNSUPPORTED_CODEC

    def __init__(self, codec: str | None) -> None:
        self.codec = (codec or "").lower() or None
        self.params = {"codec": self.codec or "", "label": codec_label(self.codec)}
        super().__init__(unsupported_message(self.codec))

    def detail(self) -> dict[str, str]:
        """HTTP javobi uchun (`detail`)."""
        return {"code": self.code, "message": str(self), **self.params}


def decoder_failure_codec(stderr: str) -> str | None:
    """ffmpeg logida dekoder ishlay olmagani tanilsa - kodek nomi (noma'lum bo'lsa ""), aks holda None."""
    m = _DECODER_FAILURE.search(stderr or "")
    if m is None:
        return None
    return next((v for v in m.groupdict().values() if v), "").lower()


def raise_if_decoder_failure(stderr: str) -> None:
    codec = decoder_failure_codec(stderr)
    if codec is not None:
        raise UnsupportedCodec(codec)


def video_codec(path: str | os.PathLike[str]) -> str | None:
    """Birinchi video yo'lagining kodeki (ffprobe). Aniqlab bo'lmasa - None."""
    try:
        ffprobe = find_tool("ffprobe")
        r = run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                 "stream=codec_name", "-of", "json", path], timeout=60)
    except (ToolNotFound, OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    try:
        streams = json.loads(r.stdout or "{}").get("streams") or []
    except ValueError:
        return None
    return (streams[0].get("codec_name") or None) if streams else None


def check_decodable(path: str | os.PathLike[str]) -> str | None:
    """Videoni bundled ffmpeg dekodlay olishini tekshiradi (birinchi kadr, ~10-50 ms).

    AV1 uchun ffmpeg'da libdav1d (yoki libaom-av1) bo'lmasa - darhol `UnsupportedCodec`; bo'lsa yoki
    ro'yxat olinmasa - birinchi kadr dekodlanadi. Dekoder ishlamasa - `UnsupportedCodec`. Boshqa har qanday holat (ffmpeg yo'q, fayl media emas,
    vaqt tugadi) bu yerda to'xtatilmaydi: u xatolar avvalgidek keyingi bosqichlarda chiqadi.
    Qaytaradi: video kodek nomi (bo'lsa).
    """
    codec = video_codec(path)
    if codec is None:
        return None
    try:
        ffmpeg = find_tool("ffmpeg")
        if codec_supported(codec, ffmpeg) is False:
            raise UnsupportedCodec(codec)
        r = run([ffmpeg, "-nostdin", "-hide_banner", "-v", "error", "-i", path,
                 "-map", "0:v:0", "-frames:v", "1", "-f", "null", "-"], timeout=60)
    except (ToolNotFound, OSError, subprocess.SubprocessError):
        return codec
    if r.returncode != 0 and decoder_failure_codec(r.stderr) is not None:
        raise UnsupportedCodec(codec)
    return codec
