"""Strict data-only editing recipe contract. No arbitrary FX parameters or templates."""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Slug = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False, populate_by_name=True)


class Timed(Strict):
    at_ms: int = Field(0, ge=0, le=600_000)
    duration_ms: int = Field(1000, ge=100, le=600_000)


class Caption(Timed):
    type: Literal["caption"]
    text: str = Field("{title}", min_length=1, max_length=500)
    position: Literal["upper", "middle", "lower"] = "middle"
    animation: Literal["none", "fade", "pop", "slide_up"] = "fade"

    @field_validator("text")
    @classmethod
    def placeholder(cls, value: str) -> str:
        rest = value.replace("{title}", "")
        if "{" in rest or "}" in rest or "\\" in value or any(ord(c) < 32 and c != '\n' for c in value):
            raise ValueError("Only {title} substitution and plain text are supported")
        return value


class Freeze(Timed):
    type: Literal["freeze"]
    duration_ms: int = Field(800, ge=100, le=5000)


class Motion(Timed):
    type: Literal["motion"]
    preset: Literal["push-in", "punch-in", "pan", "shake", "zoom-out"] = "push-in"


class Color(Strict):
    type: Literal["color"]
    preset: Literal["warm", "cool", "bw", "vivid", "film"]


class Sticker(Timed):
    type: Literal["sticker"]
    asset: str = Field(min_length=1, max_length=240)
    x: float = Field(0.5, ge=0, le=1)
    y: float = Field(0.5, ge=0, le=1)
    width: float = Field(0.25, ge=0.02, le=2)
    height: float = Field(0.25, ge=0.02, le=2)
    rotation: float = Field(0, ge=-180, le=180)
    opacity: float = Field(1, ge=0, le=1)
    layer: int = Field(0, ge=0, le=1000)
    animation: Literal["none", "fade", "pop"] = "none"


Action = Annotated[Caption | Freeze | Motion | Color | Sticker, Field(discriminator="type")]


class Skill(Strict):
    schema_: Literal["lahza.skill/1"] = Field(alias="schema")
    id: Slug
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(pattern=r"^[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}$")
    description: str = Field("", max_length=1000)
    permissions: list[Literal["timeline.modify", "assets.read"]] = Field(default_factory=lambda: ["timeline.modify"], max_length=2)
    actions: list[Action] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def permissions_match(self) -> Skill:
        if "timeline.modify" not in self.permissions or len(set(self.permissions)) != len(self.permissions):
            raise ValueError("timeline.modify required; duplicate permissions forbidden")
        if any(isinstance(a, Sticker) for a in self.actions) and "assets.read" not in self.permissions:
            raise ValueError("Sticker requires assets.read")
        return self


def safe_asset(value: str) -> str:
    if not re.fullmatch(r"assets/[A-Za-z0-9_./-]+\.(png|webp|gif)", value) or any(p in {"", ".", ".."} for p in value.split("/")):
        raise ValueError("Asset must be a relative PNG/WebP/GIF inside assets/")
    return value
