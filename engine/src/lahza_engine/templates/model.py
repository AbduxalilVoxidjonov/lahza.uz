"""Video shablon (`lahza.template/1`) - montaj retsepti (docs/11 5.6, 6).

Shablon - faqat ma'lumot (ADR-0011): foydalanuvchi tanlagan videolardan qanday montaj yig'ilishini
tavsiflaydi - tuzilma (intro / kliplar / outro), davomiylik, tanlash usuli, o'tishlar, harakat
effektlari va ularning trigger'lari, rang, subtitr, musiqa, brend. Rejalashtiruvchi
(`montage/planner.py`) shablonni + manbalarni `MontageTimeline` ga aylantiradi; natija har doim
deterministik (bir xil kirish -> bir xil timeline).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from lahza_engine.montage.model import Aspect, TransitionRef
from lahza_engine.subtitle.style import StyleTemplate

TEMPLATE_SCHEMA = "lahza.template/1"

Category = Literal["podkast", "elon", "tadbir", "mahsulot", "intervyu", "talim", "boshqa"]
Trigger = Literal["on_start", "on_end", "on_cut", "on_emphasis", "on_speaker_change", "every_n"]


class LocalText(BaseModel):
    """Lokalizatsiyalangan matn. `uz` majburiy."""

    uz: str
    uz_Cyrl: str | None = Field(None, alias="uz-Cyrl")
    ru: str | None = None
    en: str | None = None

    model_config = {"populate_by_name": True}


class TextCard(BaseModel):
    """Intro/outro kartasi yoki overlay matni. `{sarlavha}`, `{shou}`, `{cta}` o'rniga qo'yiladi."""

    text: str
    dur_ms: int = Field(2000, ge=500, le=10_000)
    kind: Literal["card", "title", "hook", "cta", "lower_third"] = "card"
    background: str | None = "#111111"  # faqat kind="card"
    position: Literal["upper", "middle", "lower"] = "middle"
    animation: Literal["none", "fade", "pop", "slide_up"] = "fade"


class FxRule(BaseModel):
    """Plaginni qayerga qo'yish qoidasi (docs/11 5.5)."""

    plugin: str  # fx reestridagi id, masalan "uz.lahza.motion.punch-in"
    trigger: Trigger
    params: dict[str, Any] = Field(default_factory=dict)
    every_n: int | None = Field(None, ge=1)  # trigger="every_n" uchun: har N-element
    max_count: int | None = Field(None, ge=1)  # bitta montajda ko'pi bilan
    min_gap_ms: int = Field(1500, ge=0)  # ikki qo'llash orasidagi minimal masofa

    @model_validator(mode="after")
    def _every(self) -> FxRule:
        if self.trigger == "every_n" and not self.every_n:
            raise ValueError("every_n trigger uchun every_n majburiy")
        return self


class MusicSpec(BaseModel):
    required: bool = False  # True - montaj boshlashda musiqa fayli so'raladi
    gain_db: float = Field(-14.0, ge=-60, le=6)
    duck: bool = True
    fade_in_ms: int = 500
    fade_out_ms: int = 1500


class Template(BaseModel):
    schema_: Literal["lahza.template/1"] = Field(TEMPLATE_SCHEMA, alias="schema")
    id: str  # "uz.lahza.tpl.podcast-hook" yoki foydalanuvchiniki "user.<uuid>"
    version: str = "1.0.0"
    name: LocalText
    description: LocalText | None = None
    category: Category = "boshqa"
    builtin: bool = False

    # Format va davomiylik
    aspect: Aspect = "9:16"
    fps: float = 30.0
    target_duration_ms: int = Field(30_000, ge=5_000, le=600_000)
    min_shot_ms: int = Field(1_500, ge=300)
    max_shot_ms: int = Field(8_000, ge=500)

    # Manbalardan tanlash
    selection: Literal["highlight", "scenes", "full"] = "scenes"
    # highlight - transkript/klip bo'lsa eng yaxshi lahzalar; scenes - kadr (sahna) bo'laklari
    # sifat/energiya bali bilan; full - har manba to'liq (faqat qisqa videolar uchun)
    order: Literal["berilgan", "xronologik", "ball"] = "berilgan"
    max_per_source: int | None = Field(None, ge=1)
    respect_sentences: bool = True  # nutqli manbada gap o'rtasida kesilmaydi

    # Ko'rinish
    reframe: Literal["auto", "fit_blur", "center"] = "auto"
    transition: TransitionRef | None = None  # kliplar orasidagi standart o'tish
    fx: list[FxRule] = Field(default_factory=list)
    color: str | None = None  # rang plagini id (masalan "uz.lahza.color.warm")
    captions: bool = False
    caption_style: StyleTemplate | None = None

    # Tuzilma
    intro: TextCard | None = None
    hook_text: TextCard | None = None  # birinchi klip ustida (kind="hook")
    outro: TextCard | None = None

    # Audio va brend
    music: MusicSpec | None = None
    source_gain_db: float = 0.0
    mute_sources: bool = False  # musiqa-yetakchi shablonlar uchun
    loudnorm_lufs: float | None = None
    logo: bool = False

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _shots(self) -> Template:
        if self.max_shot_ms < self.min_shot_ms:
            raise ValueError("max_shot_ms min_shot_ms dan kichik bo'lmasligi kerak")
        return self

    def to_json(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)
