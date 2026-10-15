"""Brend shabloni (TZ 9-bo'lim): JSON sifatida saqlanadi va fayl orqali almashiladi."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from lahza_engine.text.orthography import Orthography

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

TEMPLATE_VERSION = 1
"""Shablon fayli formatining versiyasi. Mos kelmaydigan o'zgarishda oshiriladi."""


class StyleTemplate(BaseModel):
    name: str = "Standart"
    font_family: str = "Inter"
    font_size: int = Field(72, ge=24, le=200)
    bold: bool = True
    primary_color: str = "#FFFFFF"
    highlight_color: str = "#FFD400"
    outline_color: str = "#000000"
    outline_width: float = Field(5.0, ge=0, le=20)
    shadow: float = Field(0.0, ge=0, le=10)
    box: bool = False
    box_color: str = "#000000"
    box_opacity: float = Field(0.6, ge=0, le=1)
    position: Literal["lower", "middle", "upper"] = "lower"
    uppercase: bool = False
    animation: Literal["karaoke", "pop", "none"] = "karaoke"
    max_words: int = Field(3, ge=1, le=8)
    max_lines: int = Field(2, ge=1, le=3)
    orthography: Orthography = Orthography.OFFICIAL
    # "pop": faol so'z boshida shu foizdan 100% gacha kichrayadi.
    pop_scale: int = Field(115, ge=100, le=160)
    # Kalit so'zlar doim highlight rangida va qalin chiqadi.
    keywords: list[str] = Field(default_factory=list)
    # Tozalash (TZ 9-bo'lim): faqat subtitrdan olib tashlanadi, videodan kesilmaydi.
    remove_fillers: bool = False
    filler_words: list[str] = Field(default_factory=lambda: ["ee", "eee", "mmm", "hmm", "aa", "ı"])
    mask_profanity: bool = False
    profanity_words: list[str] = Field(default_factory=list)
    # Logotip/suv belgisi.
    logo_path: str | None = None
    logo_position: Literal["top_left", "top_right", "bottom_left", "bottom_right"] = "top_right"
    logo_opacity: float = Field(0.8, ge=0, le=1)

    @field_validator("primary_color", "highlight_color", "outline_color", "box_color")
    @classmethod
    def _color(cls, v: str) -> str:
        if not _HEX.match(v):
            raise ValueError("rang #RRGGBB ko'rinishida bo'lishi kerak")
        return v.upper()

    @field_validator("keywords", "filler_words", "profanity_words")
    @classmethod
    def _words(cls, v: list[str]) -> list[str]:
        return [w.strip() for w in v if w and w.strip()]


def ass_color(hex_rgb: str, alpha: float = 0.0) -> str:
    """#RRGGBB -> ASS &HAABBGGRR (alpha: 0 = to'liq ko'rinadi, 1 = shaffof)."""
    r, g, b = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    a = round(max(0.0, min(1.0, alpha)) * 255)
    return f"&H{a:02X}{b}{g}{r}".upper()


class TemplateError(ValueError):
    """Shablon faylini o'qib/yozib bo'lmadi (foydalanuvchiga ko'rsatiladigan xabar)."""


def template_to_dict(t: StyleTemplate) -> dict:
    return {"version": TEMPLATE_VERSION, "template": t.model_dump(mode="json")}


def template_from_dict(data: dict) -> StyleTemplate:
    """Versiyali (`{"version", "template"}`) yoki eski, versiyasiz (yalang'och) ko'rinishni qabul qiladi.

    Noma'lum maydonlar e'tiborsiz qoldiriladi (yangi versiyadagi qo'shimcha maydonlar).
    """
    if not isinstance(data, dict):
        raise TemplateError("Shablon fayli JSON obyekt bo'lishi kerak")
    if "template" in data:
        version = data.get("version", 0)
        if not isinstance(version, int) or version > TEMPLATE_VERSION:
            raise TemplateError(
                f"Shablon versiyasi ({version}) bu dastur versiyasidan yangi - dasturni yangilang"
            )
        body = data["template"]
    else:
        body = data
    try:
        return StyleTemplate.model_validate(body)
    except ValidationError as e:
        first = e.errors()[0]
        field = ".".join(str(x) for x in first.get("loc", ()))
        raise TemplateError(f"Shablon noto'g'ri: '{field}' maydoni - {first.get('msg')}") from e


def load_template(path: str | os.PathLike[str]) -> StyleTemplate:
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise TemplateError(f"Shablon fayli topilmadi: {p.name}") from e
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise TemplateError("Shablon fayli JSON formatida emas") from e
    return template_from_dict(data)


def save_template(t: StyleTemplate, path: str | os.PathLike[str]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(template_to_dict(t), ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(p)
    return p
