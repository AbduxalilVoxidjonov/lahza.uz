"""Lahza Timeline (`lahza.timeline/1`) - montajning yagona modeli (ADR-0012, docs/11 10.2).

Preview, render, montaj hisoboti (`_edl.json`) va keyinchalik NLE eksporti shu modeldan o'qiydi.
Vaqtlar butun son ms. `src_*` - manba fayl vaqti; `start_ms`/`end_ms` - chiqish (montaj) vaqti.

Asosiy video trek ketma-ket: elementlar birin-ketin keladi, o'tish (`transition_in`) oldingi element
bilan ustma-ust tushadi va umumiy davomiylikni `dur_ms` ga qisqartiradi. Matn kartalari, musiqa va
subtitr alohida qatlamlar. Hamma narsa "haqiqiy kadr" tamoyiliga bo'ysunadi (ADR-0013): faqat manba
kadrlarining deterministik o'zgarishi va grafik qatlamlar.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from lahza_engine.subtitle.style import StyleTemplate
from lahza_engine.types import Word

TIMELINE_SCHEMA = "lahza.timeline/1"

Aspect = Literal["9:16", "1:1", "16:9"]
ASPECT_SIZE: dict[str, tuple[int, int]] = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}


class Format(BaseModel):
    aspect: Aspect = "9:16"
    w: int = 1080
    h: int = 1920
    fps: float = 30.0
    audio_hz: int = 48_000

    @classmethod
    def for_aspect(cls, aspect: Aspect, fps: float = 30.0) -> Format:
        w, h = ASPECT_SIZE[aspect]
        return cls(aspect=aspect, w=w, h=h, fps=fps)


class MediaRef(BaseModel):
    """Manba fayl. Asl fayl ko'chirilmaydi - faqat havola (TZ 12-bo'lim)."""

    id: str
    path: str
    hash: str | None = None
    duration_ms: int
    width: int
    height: int
    fps: float
    has_audio: bool = True
    # Qayerdan kelgani: "file" | "clip:<episode_id>/<clip_id>" | "episode:<episode_id>"
    origin: str = "file"


class FxRef(BaseModel):
    """Elementga qo'llangan plagin (fx/ reestridagi `id`). `at_ms` - element boshidan (chiqish vaqti)."""

    plugin: str
    at_ms: int = 0
    dur_ms: int | None = None  # None - element oxirigacha
    params: dict[str, Any] = Field(default_factory=dict)
    source: Literal["shablon", "qolda"] = "shablon"


class TransitionRef(BaseModel):
    plugin: str  # masalan "uz.lahza.tr.dissolve"
    dur_ms: int = Field(400, ge=0, le=3000)
    params: dict[str, Any] = Field(default_factory=dict)


class Crop(BaseModel):
    """Qo'lda kadr: normallashgan markaz va zoom (manba kadri ichida)."""

    cx: float = Field(0.5, ge=0, le=1)
    cy: float = Field(0.5, ge=0, le=1)
    zoom: float = Field(1.0, ge=1.0, le=4.0)


class VideoItem(BaseModel):
    id: str
    media: str  # MediaRef.id
    src_in_ms: int
    src_out_ms: int
    reframe: Literal["auto", "focus", "fit_blur", "center"] = "auto"
    crop: Crop | None = None
    speed: float = Field(1.0, ge=0.25, le=4.0)
    volume_db: float = Field(0.0, ge=-60, le=12)
    mute: bool = False
    transition_in: TransitionRef | None = None  # oldingi element bilan o'tish
    fx: list[FxRef] = Field(default_factory=list)
    role: str | None = None  # "hook" | "asosiy" | "broll" | "cta" ... (reja izohi)
    reason: str = ""  # nega tanlandi (montaj hisoboti uchun)
    user_edited: bool = False

    @model_validator(mode="after")
    def _range(self) -> VideoItem:
        if self.src_out_ms <= self.src_in_ms:
            raise ValueError(f"{self.id}: src_out_ms src_in_ms dan katta bo'lishi kerak")
        return self

    @property
    def out_duration_ms(self) -> int:
        return round((self.src_out_ms - self.src_in_ms) / self.speed)


class TextItem(BaseModel):
    """Grafik qatlam: sarlavha, hook matni, CTA, intro/outro kartasi (ASS orqali chiziladi)."""

    id: str
    start_ms: int
    end_ms: int
    text: str
    kind: Literal["title", "hook", "lower_third", "cta", "card"] = "title"
    # "card" - to'liq ekranli fon (rang) ustida matn; boshqalari video ustida.
    background: str | None = None  # "#RRGGBB", faqat kind="card"
    position: Literal["upper", "middle", "lower"] = "middle"
    animation: Literal["none", "fade", "pop", "slide_up"] = "fade"
    font_size: int | None = None  # None - shablon/uslubdan


class MusicItem(BaseModel):
    media: str  # MediaRef.id (foydalanuvchining o'z, litsenziyali fayli)
    src_in_ms: int = 0
    start_ms: int = 0
    end_ms: int | None = None  # None - timeline oxirigacha (kerak bo'lsa takrorlanmaydi, tugaydi)
    gain_db: float = Field(-14.0, ge=-60, le=6)
    duck: bool = True  # nutq ustida pasaytirish
    fade_in_ms: int = 500
    fade_out_ms: int = 1500


class Captions(BaseModel):
    enabled: bool = False
    style: StyleTemplate = Field(default_factory=StyleTemplate)
    # Chiqish vaqtiga o'tkazilgan so'zlar (manbada transkript bo'lsa - rejalashtiruvchi to'ldiradi).
    words: list[Word] = Field(default_factory=list)


class Brand(BaseModel):
    logo_path: str | None = None
    logo_position: Literal["top_left", "top_right", "bottom_left", "bottom_right"] = "top_right"
    logo_opacity: float = Field(0.8, ge=0, le=1)


class AudioMix(BaseModel):
    source_gain_db: float = 0.0
    loudnorm_lufs: float | None = None
    fade_ms: int = 150


class Provenance(BaseModel):
    template_id: str | None = None
    template_version: str | None = None
    engine: str | None = None
    created_at: str | None = None
    planner: str | None = None  # "qoida" | "llm"
    notes: list[str] = Field(default_factory=list)


class MontageTimeline(BaseModel):
    schema_: Literal["lahza.timeline/1"] = Field(TIMELINE_SCHEMA, alias="schema")
    format: Format = Field(default_factory=Format)
    media: dict[str, MediaRef] = Field(default_factory=dict)
    video: list[VideoItem] = Field(default_factory=list)
    text: list[TextItem] = Field(default_factory=list)
    music: list[MusicItem] = Field(default_factory=list)
    captions: Captions = Field(default_factory=Captions)
    brand: Brand = Field(default_factory=Brand)
    audio: AudioMix = Field(default_factory=AudioMix)
    color: FxRef | None = None  # butun montajga rang (LUT/preset)
    provenance: Provenance = Field(default_factory=Provenance)

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _refs(self) -> MontageTimeline:
        ids = set()
        for it in self.video:
            if it.media not in self.media:
                raise ValueError(f"{it.id}: noma'lum media '{it.media}'")
            m = self.media[it.media]
            if it.src_out_ms > m.duration_ms + 50:
                raise ValueError(f"{it.id}: manba davomiyligidan tashqarida")
            if it.id in ids:
                raise ValueError(f"takroriy element id: {it.id}")
            ids.add(it.id)
        for mu in self.music:
            if mu.media not in self.media:
                raise ValueError(f"musiqa: noma'lum media '{mu.media}'")
        if self.video and self.video[0].transition_in is not None:
            raise ValueError("birinchi elementda o'tish bo'lmaydi")
        return self

    def item_starts(self) -> list[int]:
        """Har video elementning chiqish vaqtidagi boshi (o'tishlar ustma-ustligi hisobga olingan)."""
        starts: list[int] = []
        t = 0
        for i, it in enumerate(self.video):
            if i > 0 and it.transition_in is not None:
                t -= min(it.transition_in.dur_ms, it.out_duration_ms, self.video[i - 1].out_duration_ms)
            starts.append(t)
            t += it.out_duration_ms
        return starts

    @property
    def duration_ms(self) -> int:
        """Video trek oxiri yoki undan keyin davom etadigan karta (`kind="card"`) oxiri.
        Video ustidagi oddiy matn (sarlavha, CTA ...) davomiylikni uzaytirmaydi - video oxirida
        kesiladi, aks holda tahrirdan keyin oxirida qora kadr qolardi."""
        cards = [x.end_ms for x in self.text if x.kind == "card"]
        if not self.video:
            return max((x.end_ms for x in self.text), default=0)
        starts = self.item_starts()
        return max([starts[-1] + self.video[-1].out_duration_ms, *cards])

    def to_json(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True)
