"""Platforma limitlari bo'yicha eksportdan oldingi tekshiruv (V1-6, TZ 10-bo'lim).

Qiymatlar kodga yozilmaydi - `platform_limits.json` dan o'qiladi. null = aniqlanmagan
(tekshirilmaydi). Natija - foydalanuvchiga ko'rsatiladigan o'zbekcha ogohlantirishlar.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

LIMITS_FILE = Path(__file__).resolve().parent / "platform_limits.json"
DEFAULT_PLATFORM = "instagram_reels"
_NAMES = {"instagram_reels": "Instagram Reels"}


@lru_cache(maxsize=4)
def _load(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def load_limits(path: Path | None = None) -> dict[str, dict]:
    return _load(str(path or LIMITS_FILE))


def _fmt_s(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}:{s:02d}"


def check_limits(
    duration_ms: int,
    width: int,
    height: int,
    file_bytes: int | None = None,
    platform: str = DEFAULT_PLATFORM,
    limits: dict[str, dict] | None = None,
) -> list[str]:
    lim = (limits or load_limits()).get(platform)
    if lim is None:
        return []
    name = _NAMES.get(platform, platform)
    out: list[str] = []
    max_d = lim.get("max_duration_s")
    if max_d is not None and duration_ms / 1000 > max_d:
        out.append(f"{name}: klip davomiyligi {_fmt_s(duration_ms / 1000)} - "
                   f"ruxsat etilgan {_fmt_s(max_d)} dan uzun")
    min_d = lim.get("min_duration_s")
    if min_d is not None and duration_ms / 1000 < min_d:
        out.append(f"{name}: klip {_fmt_s(min_d)} dan qisqa")
    min_w, min_h = lim.get("min_width"), lim.get("min_height")
    if (min_w is not None and width < min_w) or (min_h is not None and height < min_h):
        out.append(f"{name}: o'lcham {width}x{height} - kamida {min_w}x{min_h} bo'lishi kerak")
    w, h = lim.get("width"), lim.get("height")
    if w and h and width * h != height * w:
        out.append(f"{name}: tomonlar nisbati {lim.get('aspect', f'{w}:{h}')} emas ({width}x{height})")
    max_b = lim.get("max_file_bytes")
    if file_bytes is not None and max_b is not None and file_bytes > max_b:
        out.append(f"{name}: fayl hajmi {file_bytes / 2**30:.1f} GB - "
                   f"chegara {max_b / 2**30:.1f} GB")
    return out


def source_quality_warning(src_w: int, src_h: int, out_w: int = 1080, uses_crop: bool = True) -> str | None:
    """TZ 8-bo'lim "Sifat ogohlantirishi": 9:16 crop eni chiqish enidan kichik bo'lsa."""
    if not uses_crop or src_h <= 0:
        return None
    crop_w = min(src_w, int(src_h * 9 / 16))
    if crop_w >= out_w:
        return None
    return (f"Manba {src_w}x{src_h}: 9:16 kesim eni {crop_w} px, {out_w / crop_w:.2f} marta "
            "kattalashtiriladi va yumshoqroq chiqadi. 4K yozish tavsiya etiladi.")
