"""Lahza FX plaginlar reestri (`lahza.fx/1`, ADR-0011, docs/11 5).

Plagin - kod emas, ma'lumot: JSON manifest effektni TAVSIFLAYDI, FFmpeg grafini esa engine'ning o'z
backend kompilyatori (`render/montage_render.py`) yig'adi. Manifestda filtr nomi yoki graf matni
bo'lmaydi - faqat backend nomi, backend ichidagi tayyor ko'rinish (`preset`) va parametrlar.

Oq ro'yxat (NFR-M1/M3):
* backend faqat `BACKENDS` dagilardan biri;
* har backend faqat `BACKEND_FILTERS` dagi filtrlarni ishlatadi;
* GPL ro'yxatidagi (`GPL_FILTERS`) va fayl/tashqi manba o'qiydigan (`IO_FILTERS`) filtrlar hech
  qachon ruxsat etilmaydi - `check_graph` render grafini shu bo'yicha tekshiradi.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FX_SCHEMA = "lahza.fx/1"
BUILTIN_DIR = Path(__file__).parent / "builtin"

Kind = Literal["transition", "motion", "color", "text", "overlay", "audio", "speed"]
Backend = Literal["xfade", "motion-keys", "color", "lut", "audio-graph", "speed"]
ParamType = Literal["float", "int", "enum", "bool", "color", "file"]
BACKENDS: frozenset[str] = frozenset({"xfade", "motion-keys", "color", "lut", "audio-graph", "speed"})

# FFmpeg `configure` faylida faqat --enable-gpl bilan yoqiladigan filtrlar (LICENSE.md, configure).
# Lahza yig'masida ular yo'q; grafda paydo bo'lsa - xato (docs/11 11.3).
GPL_FILTERS: frozenset[str] = frozenset({
    "blackframe", "boxblur", "colormatrix", "cover_rect", "cropdetect", "delogo", "eq",
    "find_rect", "fspp", "histeq", "hqdn3d", "interlace", "kerndeint", "lensfun", "mcdeint",
    "mpdecimate", "nnedi", "owdenoise", "perspective", "phase", "pp", "pp7", "pullup",
    "repeatfields", "rubberband", "sab", "signature", "smartblur", "spp", "stereo3d",
    "super2xsai", "tinterlace", "uspp", "vaguedenoiser", "vidstabdetect", "vidstabtransform",
    "frei0r", "frei0r_src", "zmq", "azmq",
})
# Fayl yoki tashqi manba o'qiydigan filtrlar - foydalanuvchi yo'li grafga kirmasligi kerak.
IO_FILTERS: frozenset[str] = frozenset({"movie", "amovie", "subtitles", "ladspa", "lv2"})

# Har backend ishlatishi mumkin bo'lgan filtrlar (kompilyator shu to'plamdan chiqmaydi).
BACKEND_FILTERS: dict[str, frozenset[str]] = {
    "xfade": frozenset({"xfade", "acrossfade", "concat", "fps", "settb"}),
    "motion-keys": frozenset({"crop", "scale", "zoompan", "sendcmd", "setsar"}),
    "color": frozenset({"colorbalance", "colorchannelmixer", "curves", "hue"}),
    "lut": frozenset({"lut3d"}),
    "audio-graph": frozenset({"afade", "volume", "acrossfade", "sidechaincompress", "loudnorm",
                              "amix", "atrim", "adelay", "apad", "asplit"}),
    "speed": frozenset({"setpts", "atempo", "tpad", "trim", "concat", "split"}),
}
# Montaj kompilyatorining o'z (plagin bo'lmagan) qismlari: trim, reframe, xira fon, kartalar,
# matn qatlami (ASS), logotip, audio normallash.
CORE_FILTERS: frozenset[str] = frozenset({
    "trim", "atrim", "setpts", "asetpts", "fps", "crop", "scale", "split", "asplit", "gblur",
    "overlay", "format", "setsar", "tpad", "concat", "drawbox", "color", "anullsrc", "aresample",
    "aformat", "ass", "null", "anull", "apad", "adelay", "volume", "afade", "loudnorm", "amix",
    "colorchannelmixer", "sendcmd", "vstack", "zoompan", "xfade", "acrossfade",
    "sidechaincompress",
})
ALLOWED_GRAPH_FILTERS: frozenset[str] = CORE_FILTERS.union(*BACKEND_FILTERS.values())

# Backend ichidagi tayyor ko'rinishlar (manifestdagi `preset`).
XFADE_TRANSITIONS: frozenset[str] = frozenset({
    "fade", "dissolve", "fadeblack", "fadewhite", "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown", "smoothleft", "smoothright", "smoothup",
    "smoothdown", "circleopen", "circleclose", "circlecrop", "rectcrop", "zoomin", "radial",
    "distance", "pixelize", "hblur", "squeezeh", "squeezev", "fadegrays",
})
CUT_PRESET = "cut"
MOTION_PRESETS: frozenset[str] = frozenset({"punch-in", "push-in", "pan", "shake", "zoom-out"})
COLOR_PRESETS: frozenset[str] = frozenset({"warm", "cool", "bw", "vivid", "film"})
SPEED_PRESETS: frozenset[str] = frozenset({"freeze"})
AUDIO_PRESETS: frozenset[str] = frozenset({"fade"})
PRESETS: dict[str, frozenset[str]] = {
    "xfade": XFADE_TRANSITIONS | {CUT_PRESET},
    "motion-keys": MOTION_PRESETS,
    "color": COLOR_PRESETS,
    "lut": frozenset({"cube"}),
    "audio-graph": AUDIO_PRESETS,
    "speed": SPEED_PRESETS,
}
KIND_BACKENDS: dict[str, frozenset[str]] = {
    "transition": frozenset({"xfade"}),
    "motion": frozenset({"motion-keys"}),
    "color": frozenset({"color", "lut"}),
    "audio": frozenset({"audio-graph"}),
    "speed": frozenset({"speed"}),
    "text": frozenset(),
    "overlay": frozenset(),
}
TRIGGERS = frozenset({"on_start", "on_end", "on_cut", "on_emphasis", "on_speaker_change",
                      "every_n", "manual"})

_ID_RE = re.compile(r"^[a-z0-9]+(\.[a-z0-9][a-z0-9-]*)+$")
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_PARAM_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


class FxError(ValueError):
    """Manifest yoki parametr xatosi (o'zbekcha xabar)."""


class ParamSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: ParamType
    min: float | None = None
    max: float | None = None
    values: list[str] | None = None
    default: Any = None
    name: dict[str, str] | None = None  # UI uchun nom (ixtiyoriy)

    @field_validator("id")
    @classmethod
    def _pid(cls, v: str) -> str:
        if not _PARAM_ID_RE.match(v):
            raise ValueError(f"parametr id noto'g'ri: {v!r}")
        return v

    @model_validator(mode="after")
    def _check(self) -> ParamSpec:
        if self.type == "enum":
            if not self.values:
                raise ValueError(f"{self.id}: enum uchun values majburiy")
            if self.default is not None and self.default not in self.values:
                raise ValueError(f"{self.id}: default values ichida emas")
        elif self.values is not None:
            raise ValueError(f"{self.id}: values faqat enum uchun")
        if self.type in ("float", "int"):
            if self.min is not None and self.max is not None and self.min > self.max:
                raise ValueError(f"{self.id}: min > max")
            if self.default is not None:
                if isinstance(self.default, bool) or not isinstance(self.default, int | float):
                    raise ValueError(f"{self.id}: default son bo'lishi kerak")
                if (self.min is not None and self.default < self.min) or (
                        self.max is not None and self.default > self.max):
                    raise ValueError(f"{self.id}: default chegaradan tashqarida")
        elif self.min is not None or self.max is not None:
            raise ValueError(f"{self.id}: min/max faqat son parametrlar uchun")
        if self.type == "bool" and self.default is not None and not isinstance(self.default, bool):
            raise ValueError(f"{self.id}: default bool bo'lishi kerak")
        if self.type == "color" and self.default is not None and not _HEX_RE.match(str(self.default)):
            raise ValueError(f"{self.id}: default #RRGGBB bo'lishi kerak")
        return self


class FxManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: Literal["lahza.fx/1"] = Field(FX_SCHEMA, alias="schema")
    id: str
    version: str = "1.0.0"
    kind: Kind
    name: dict[str, str]
    description: dict[str, str] | None = None
    backend: Backend
    # Backend ichidagi tayyor ko'rinish: xfade o'tish nomi, rang preseti, harakat turi va h.k.
    preset: str
    params: list[ParamSpec] = Field(default_factory=list)
    default_trigger: str | None = None
    license: str = "Lahza"
    builtin: bool = False

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _ID_RE.match(v):
            raise ValueError(f"plagin id noto'g'ri: {v!r}")
        return v

    @field_validator("version")
    @classmethod
    def _ver(cls, v: str) -> str:
        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError("version X.Y.Z ko'rinishida bo'lishi kerak")
        return v

    @field_validator("name", "description")
    @classmethod
    def _local(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is None:
            return v
        if not v.get("uz"):
            raise ValueError("'uz' nomi majburiy")
        bad = set(v) - {"uz", "uz-Cyrl", "ru", "en"}
        if bad:
            raise ValueError(f"noma'lum til kaliti: {sorted(bad)[0]}")
        return v

    @model_validator(mode="after")
    def _whitelist(self) -> FxManifest:
        if self.backend not in KIND_BACKENDS[self.kind]:
            raise ValueError(f"{self.kind} turi uchun '{self.backend}' backendi ruxsat etilmagan")
        if self.preset not in PRESETS[self.backend]:
            raise ValueError(f"'{self.backend}' backendida '{self.preset}' preseti yo'q")
        ids = [p.id for p in self.params]
        if len(ids) != len(set(ids)):
            raise ValueError("takroriy parametr id")
        if self.default_trigger is not None and self.default_trigger not in TRIGGERS:
            raise ValueError(f"noma'lum trigger: {self.default_trigger}")
        return self

    def param(self, pid: str) -> ParamSpec | None:
        return next((p for p in self.params if p.id == pid), None)


def load_manifest(data: dict[str, Any] | str | Path) -> FxManifest:
    """JSON matn/dict/fayldan manifest (sxema + oq ro'yxat). Xato bo'lsa FxError."""
    try:
        if isinstance(data, Path):
            data = json.loads(data.read_text(encoding="utf-8"))
        elif isinstance(data, str):
            data = json.loads(data)
        return FxManifest.model_validate(data)
    except (OSError, json.JSONDecodeError) as e:
        raise FxError(f"plagin manifestini o'qib bo'lmadi: {e}") from e
    except ValueError as e:
        raise FxError(f"plagin manifesti noto'g'ri: {e}") from e


@lru_cache(maxsize=1)
def _builtin() -> dict[str, FxManifest]:
    out: dict[str, FxManifest] = {}
    for f in sorted(BUILTIN_DIR.glob("*.json")):
        m = load_manifest(f).model_copy(update={"builtin": True})
        if m.id in out:
            raise FxError(f"takroriy plagin id: {m.id}")
        out[m.id] = m
    return out


def list_plugins(kind: str | None = None) -> list[FxManifest]:
    return [m for m in _builtin().values() if kind is None or m.kind == kind]


def get_plugin(plugin_id: str) -> FxManifest:
    """Plagin manifesti. Topilmasa KeyError."""
    try:
        return _builtin()[plugin_id]
    except KeyError:
        raise KeyError(f"noma'lum plagin: {plugin_id}") from None


def validate_params(m: FxManifest, params: dict[str, Any] | None, *, strict: bool = False
                    ) -> dict[str, Any]:
    """Parametrlarni tekshiradi va default'lar bilan to'ldiradi.

    Sonlar chegaraga qisiladi (strict=True bo'lsa chegaradan tashqari - xato). Noma'lum parametr,
    noto'g'ri tur, ro'yxatda yo'q enum qiymati, noto'g'ri rang - FxError.
    """
    params = dict(params or {})
    unknown = set(params) - {p.id for p in m.params}
    if unknown:
        raise FxError(f"{m.id}: noma'lum parametr '{sorted(unknown)[0]}'")
    out: dict[str, Any] = {}
    for p in m.params:
        if p.id not in params or params[p.id] is None:
            out[p.id] = p.default
            continue
        v = params[p.id]
        if p.type in ("float", "int"):
            if isinstance(v, bool) or not isinstance(v, int | float):
                raise FxError(f"{m.id}: '{p.id}' son bo'lishi kerak")
            lo = p.min if p.min is not None else v
            hi = p.max if p.max is not None else v
            if strict and not lo <= v <= hi:
                raise FxError(f"{m.id}: '{p.id}' = {v} chegaradan tashqarida [{p.min}, {p.max}]")
            v = min(max(v, lo), hi)
            out[p.id] = int(round(v)) if p.type == "int" else float(v)
        elif p.type == "enum":
            if v not in (p.values or []):
                raise FxError(f"{m.id}: '{p.id}' qiymati ruxsat etilmagan: {v!r}")
            out[p.id] = v
        elif p.type == "bool":
            if not isinstance(v, bool):
                raise FxError(f"{m.id}: '{p.id}' true/false bo'lishi kerak")
            out[p.id] = v
        elif p.type == "color":
            if not isinstance(v, str) or not _HEX_RE.match(v):
                raise FxError(f"{m.id}: '{p.id}' #RRGGBB ko'rinishida bo'lishi kerak")
            out[p.id] = v.upper()
        else:  # file
            if not isinstance(v, str) or not v.strip():
                raise FxError(f"{m.id}: '{p.id}' fayl yo'li bo'lishi kerak")
            out[p.id] = v
    return out


# --- Graf tekshiruvi (NFR-M1/M3) ------------------------------------------------------------


def _split_top(text: str, sep: str) -> list[str]:
    """Qo'shtirnoq ('...') va '\\' ekranlashni hisobga olib bo'lish."""
    parts, cur, quote, esc = [], [], False, False
    for ch in text:
        if esc:
            cur.append(ch)
            esc = False
        elif ch == "\\":
            cur.append(ch)
            esc = True
        elif ch == "'":
            quote = not quote
            cur.append(ch)
        elif ch == sep and not quote:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


_LABELS_RE = re.compile(r"^\s*(\[[^\]]*\]\s*)*")


def graph_filters(graph: str) -> set[str]:
    """Filtergraph matnidagi filtr nomlari (`crop@c0` -> `crop`)."""
    names: set[str] = set()
    for chain in _split_top(graph, ";"):
        for f in _split_top(chain, ","):
            f = _LABELS_RE.sub("", f).strip()
            if not f:
                continue
            m = re.match(r"([A-Za-z0-9_]+)", f)
            if m:
                names.add(m.group(1))
    return names


def check_graph(graph: str) -> set[str]:
    """Grafda faqat oq ro'yxatdagi filtrlar borligini tekshiradi; filtr nomlarini qaytaradi."""
    names = graph_filters(graph)
    bad = names & (GPL_FILTERS | IO_FILTERS)
    if bad:
        raise FxError(f"taqiqlangan filtr grafda: {sorted(bad)[0]}")
    extra = names - ALLOWED_GRAPH_FILTERS
    if extra:
        raise FxError(f"oq ro'yxatda yo'q filtr grafda: {sorted(extra)[0]}")
    return names
