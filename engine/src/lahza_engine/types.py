"""Domen turlari. Barcha vaqtlar butun son millisekundda (ms)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Word(BaseModel):
    text: str
    start_ms: int
    end_ms: int
    conf: float | None = None
    speaker: str | None = None
    edited: bool = False
    original_text: str | None = None


class Sentence(BaseModel):
    id: int
    start_ms: int
    end_ms: int
    speaker: str | None = None
    words: list[Word] = Field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


class Transcript(BaseModel):
    language: str = "uz"
    sentences: list[Sentence] = Field(default_factory=list)

    @property
    def words(self) -> list[Word]:
        return [w for s in self.sentences for w in s.words]


class ClipKind(StrEnum):
    MASLAHAT = "maslahat"
    HIKOYA = "hikoya"
    KULGILI = "kulgili"
    BAHSLI_FIKR = "bahsli_fikr"
    FAKT = "fakt"
    SAVOL_JAVOB = "savol_javob"


class ClipStatus(StrEnum):
    CANDIDATE = "nomzod"
    ACCEPTED = "qabul"
    REJECTED = "rad"
    EXPORTED = "eksport_qilingan"


class ClipSource(StrEnum):
    AI_LLM = "ai_llm"
    AI_LITE = "ai_lite"
    MANUAL = "qolda"


class Clip(BaseModel):
    id: str
    media_id: str
    start_ms: int
    end_ms: int
    start_sentence_id: int
    end_sentence_id: int
    hook_sentence_id: int | None = None
    title: str = ""
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    kind: ClipKind | None = None
    score: float = 0.0
    scores: dict[str, float] = Field(default_factory=dict)
    reason: str = ""
    status: ClipStatus = ClipStatus.CANDIDATE
    source: ClipSource = ClipSource.AI_LITE
    llm_model_id: str | None = None
    cuts: list[tuple[int, int]] = Field(
        default_factory=list, description="Matn orqali o'chirilgan oraliqlar (manba vaqtida)"
    )

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


class Layout(StrEnum):
    FOCUS = "focus"
    SPLIT = "split"
    FIT_BLUR = "fit_blur"
    MANUAL = "manual"
