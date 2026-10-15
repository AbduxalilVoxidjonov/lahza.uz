"""Yetkaziladigan shriftlar va o'zbek glif testi (TZ 9-bo'lim, "Shriftlar").

Faqat dastur bilan yetkaziladigan papka skanerlanadi (tizim shriftlari emas): render natijasi
har kompyuterda bir xil bo'lishi uchun ASS faqat shu shriftlar bilan chiziladi.
Papka: LAHZA_FONTS_DIR yoki engine paketidagi `subtitle/fonts/`.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel

from lahza_engine.text.orthography import REQUIRED_GLYPHS

FONT_SUFFIXES = (".ttf", ".otf", ".ttc", ".otc")

__all__ = ["REQUIRED_GLYPHS", "FontInfo", "default_fonts_dir", "list_fonts", "check_font"]


class FontInfo(BaseModel):
    family: str
    path: str
    ok: bool
    missing: list[str]


def default_fonts_dir() -> Path:
    env = os.environ.get("LAHZA_FONTS_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / "fonts"


def _family(font) -> str:
    name = font["name"]
    for nid in (16, 1):  # 16 = tipografik oila, 1 = oila
        rec = name.getDebugName(nid)
        if rec:
            return str(rec)
    return ""


def check_font(path: Path, required: str = REQUIRED_GLYPHS) -> list[FontInfo]:
    """Bitta fayl (kolleksiyada bir nechta shrift bo'lishi mumkin). Buzuq fayl -> []."""
    from fontTools.ttLib import TTCollection, TTFont, TTLibError

    try:
        if path.suffix.lower() in (".ttc", ".otc"):
            fonts = list(TTCollection(str(path), lazy=True).fonts)
        else:
            fonts = [TTFont(str(path), lazy=True)]
    except (TTLibError, OSError, AssertionError, ValueError):
        return []
    out: list[FontInfo] = []
    for f in fonts:
        try:
            cmap = f.getBestCmap() or {}
            family = _family(f) or path.stem
        except Exception:  # noqa: BLE001 - buzuq jadval: shriftni ro'yxatga qo'shmaymiz
            continue
        finally:
            f.close()
        missing = [ch for ch in dict.fromkeys(required) if ord(ch) not in cmap]
        out.append(FontInfo(family=family, path=str(path), ok=not missing, missing=missing))
    return out


def list_fonts(fonts_dir: Path | None = None) -> list[FontInfo]:
    """Papkadagi barcha shriftlar glif testi bilan (UI faqat ok=True larini tanlashga beradi)."""
    root = fonts_dir or default_fonts_dir()
    if not root.is_dir():
        return []
    out: list[FontInfo] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in FONT_SUFFIXES:
            out.extend(check_font(p))
    return out


def has_fonts(fonts_dir: Path | None = None) -> bool:
    root = fonts_dir or default_fonts_dir()
    return root.is_dir() and any(
        p.suffix.lower() in FONT_SUFFIXES for p in root.rglob("*") if p.is_file()
    )
