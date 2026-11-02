"""Host-reja (`lahza.hostplan/1`) - Adobe plaginlari (Premiere Pro, After Effects) uchun montaj ko'rsatmasi.

Engine klip yoki montajni tahlil qiladi va rejalashtiradi; plagin esa shu rejani o'z dasturining
API'si orqali timeline'ga qo'yadi (Premiere: sekvensiya, AE: kompozitsiya). Render'ni Adobe o'zi qiladi.

Koordinatalar host-neytral va ikkala dasturning "Motion/Transform" modeliga to'g'ridan-to'g'ri mos:
* vaqt - soniya (float), `rec_*` - sekvensiya/kompozitsiya vaqti, `src_*` - manba fayl vaqti;
* `scale_pct` - manba kadrining masshtabi (100 = asl o'lcham);
* `pos_x`, `pos_y` - manba kadri MARKAZI sekvensiyaning qaysi pikseliga tushadi (anchor = manba markazi).
Hech qanday piksel yaratilmaydi (ADR-0013): faqat kesish, masshtab, siljitish, xiralashtirish, matn.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

HOSTPLAN_SCHEMA = "lahza.hostplan/1"


class Sequence(BaseModel):
    name: str
    width: int
    height: int
    fps: float
    audio_hz: int = 48_000
    duration_s: float


class HostMedia(BaseModel):
    id: str
    path: str  # absolyut yo'l - plagin shu faylni loyihaga import qiladi
    width: int
    height: int
    fps: float
    duration_s: float
    has_audio: bool = True


class TransformKey(BaseModel):
    t: float  # rec vaqt, elementning o'z boshidan (soniya)
    scale_pct: float
    pos_x: float
    pos_y: float
    rotation: float = 0.0
    interp: Literal["linear", "hold", "ease"] = "linear"


class HostEffect(BaseModel):
    # Faqat ikkala dasturda ham bor standart effektlar.
    kind: Literal["gaussian_blur", "lumetri_preset", "lut"]
    amount: float | None = None  # gaussian_blur: xiralik (Premiere "Blurriness", AE "Blurriness")
    preset: str | None = None  # "warm" | "cool" | "bw" | "vivid" | "film"
    lut_path: str | None = None


class HostLayer(BaseModel):
    """Bitta element ichidagi qatlam: oddiy holatda bitta "main"; xira fon layoutida "bg" + "main";
    split layoutida "top" + "bottom" (har biri o'z crop'i bilan, mask/crop bilan yarim kadr)."""

    role: Literal["main", "bg", "top", "bottom"] = "main"
    keys: list[TransformKey]
    effects: list[HostEffect] = Field(default_factory=list)
    # Qatlamni sekvensiyada ko'rinadigan to'rtburchakka qirqish (split uchun): px, sekvensiya koordinatasi
    crop_rect: tuple[int, int, int, int] | None = None  # (x, y, w, h)


class HostTransition(BaseModel):
    kind: Literal["cut", "cross_dissolve", "dip_to_black", "dip_to_white", "push", "wipe", "zoom"]
    dur_s: float = 0.0
    lahza_plugin: str | None = None  # asl fx id (hisobot uchun)


class VideoClipItem(BaseModel):
    id: str
    media: str  # HostMedia.id
    src_in: float
    src_out: float
    rec_in: float
    rec_out: float
    speed: float = 1.0
    volume_db: float = 0.0
    mute: bool = False
    layers: list[HostLayer]
    transition_in: HostTransition | None = None
    label: str | None = None  # "hook" | "asosiy" ... - Premiere klip nomi / AE qatlam izohi


class MusicItem(BaseModel):
    media: str
    src_in: float
    rec_in: float
    rec_out: float
    volume_db: float = -14.0
    duck: bool = True  # Premiere: Essential Sound "Ducking"; AE: plagin kalit kadrlar bilan pasaytiradi
    fade_in_s: float = 0.5
    fade_out_s: float = 1.5


class CaptionWord(BaseModel):
    text: str  # tanlangan imloda (official/ascii/new)
    t0: float  # rec vaqt
    t1: float


class CaptionLine(BaseModel):
    t0: float
    t1: float
    text: str
    words: list[CaptionWord]
    speaker: str | None = None


class Captions(BaseModel):
    srt_path: str | None = None  # Premiere: Captions trekiga import
    words_path: str | None = None  # AE: karaoke uchun to'liq so'z vaqtlari (JSON)
    lines: list[CaptionLine] = Field(default_factory=list)
    style: dict = Field(default_factory=dict)  # StyleTemplate JSON (shrift, rang, highlight_color ...)


class TextOverlay(BaseModel):
    id: str
    rec_in: float
    rec_out: float
    text: str
    kind: Literal["title", "hook", "lower_third", "cta", "card"] = "title"
    background: str | None = None
    position: Literal["upper", "middle", "lower"] = "middle"


class Marker(BaseModel):
    t: float
    name: str
    comment: str = ""
    kind: Literal["hook", "highlight", "emphasis", "note"] = "note"


class HostPlan(BaseModel):
    schema_: Literal["lahza.hostplan/1"] = Field(HOSTPLAN_SCHEMA, alias="schema")
    source: Literal["clip", "montage"]
    source_id: str
    sequence: Sequence
    media: list[HostMedia]
    video: list[VideoClipItem]
    music: list[MusicItem] = Field(default_factory=list)
    captions: Captions = Field(default_factory=Captions)
    text: list[TextOverlay] = Field(default_factory=list)
    markers: list[Marker] = Field(default_factory=list)
    # Host dasturiga o'tmaydigan narsalar (masalan, Lahza'ga xos animatsiya) - plagin foydalanuvchiga ko'rsatadi.
    not_translated: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    def to_json(self) -> dict:
        return self.model_dump(mode="json", by_alias=True)
