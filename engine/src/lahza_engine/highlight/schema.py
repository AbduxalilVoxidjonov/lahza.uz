"""LLM javobi uchun majburiy JSON sxema (TZ 7-bo'lim, ADR-0005).

LLM vaqt emas, gap ID'larini qaytaradi. llama-server grammatika/JSON-schema rejimida modelni
shu sxemadan chiqib ketolmaydigan qiladi; shunga qaramay javob pydantic bilan qayta tekshiriladi
(NFR-09: LLM chiqishi faqat ma'lumot).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from lahza_engine.types import ClipKind

CRITERIA = ("hook", "mustaqillik", "hissiyot", "foyda", "aniqlik")


class LlmScores(BaseModel):
    hook: int = Field(ge=0, le=10)
    mustaqillik: int = Field(ge=0, le=10)
    hissiyot: int = Field(ge=0, le=10)
    foyda: int = Field(ge=0, le=10)
    aniqlik: int = Field(ge=0, le=10)

    def mean(self) -> float:
        return sum(getattr(self, c) for c in CRITERIA) / len(CRITERIA)


class LlmCandidate(BaseModel):
    start_id: int = Field(ge=0)
    end_id: int = Field(ge=0)
    hook_id: int = Field(ge=0)
    turi: ClipKind
    mustaqil: bool
    ballar: LlmScores
    sarlavha: str = Field(max_length=120)
    sabab: str = Field(max_length=400)
    izoh_matni: str = Field(max_length=2200)
    heshteglar: list[str] = Field(default_factory=list, max_length=15)

    @model_validator(mode="after")
    def _order(self) -> LlmCandidate:
        if not (self.start_id <= self.hook_id <= self.end_id):
            raise ValueError("start_id <= hook_id <= end_id bo'lishi shart")
        return self

    @field_validator("heshteglar")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        out = []
        for t in v:
            t = t.strip().lstrip("#").replace(" ", "")
            if t:
                out.append("#" + t)
        return out


class LlmResponse(BaseModel):
    nomzodlar: list[LlmCandidate] = Field(default_factory=list, max_length=12)


# M3-PERF-2: LLM'ga beriladigan sxemadagi qattiqroq chegaralar. Grammatika ularni majburlaydi,
# shuning uchun 4B model erkin matn maydonlarida takrorlanib, minglab token "yoza olmaydi"
# (o'lchov: chegarasiz 1751 chiqish tokeni/oyna, asosan takrorlangan "sabab"/"izoh_matni").
# Pydantic modeli (yuqorida) o'zgarmaydi - qo'lda tahrirlangan ma'lumot uchun kengroq.
LLM_TEXT_LIMITS = {"sarlavha": 80, "sabab": 200, "izoh_matni": 300}
LLM_MAX_HASHTAGS = 5
LLM_HASHTAG_MAX_LEN = 30


def json_schema(max_candidates: int | None = None) -> dict:
    """llama-server'ga uzatiladigan JSON Schema (LLM uchun torroq chegaralar bilan)."""
    schema = LlmResponse.model_json_schema()
    cand = schema["$defs"]["LlmCandidate"]["properties"]
    for name, limit in LLM_TEXT_LIMITS.items():
        cand[name]["maxLength"] = limit
    tags = cand["heshteglar"]
    tags["maxItems"] = LLM_MAX_HASHTAGS
    tags["items"] = {**tags.get("items", {"type": "string"}), "maxLength": LLM_HASHTAG_MAX_LEN}
    if max_candidates is not None:
        schema["properties"]["nomzodlar"]["maxItems"] = max_candidates
    return schema
