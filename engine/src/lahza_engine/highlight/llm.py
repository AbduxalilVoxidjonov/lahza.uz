"""Lokal LLM (llama.cpp `llama-server`) orqali highlight nomzodlari - map/reduce (TZ 7-bo'lim).

Server dastur ichida yetkaziladi va 127.0.0.1 da ishlaydi (runtime/llama_server.py).
OpenAI-mos endpoint ishlatiladi: POST /v1/chat/completions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from importlib import resources

import httpx
from pydantic import ValidationError

from lahza_engine.config import HighlightConfig
from lahza_engine.highlight.schema import LlmCandidate, LlmResponse, json_schema
from lahza_engine.types import Sentence

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Window:
    first_id: int
    last_id: int


def make_windows(sentences: list[Sentence], cfg: HighlightConfig) -> list[Window]:
    """Ustma-ust oynalar (oyna va ustma-ustlik uzunligi - R0 parametrlari)."""
    if not sentences:
        return []
    windows: list[Window] = []
    i = 0
    n = len(sentences)
    while i < n:
        start_ms = sentences[i].start_ms
        j = i
        while j + 1 < n and sentences[j + 1].end_ms - start_ms <= cfg.llm_window_ms:
            j += 1
        windows.append(Window(i, j))
        if j == n - 1:
            break
        # Keyingi oyna overlap qadar orqadan boshlanadi.
        next_start_ms = sentences[j].end_ms - cfg.llm_window_overlap_ms
        k = j
        while k > i and sentences[k].start_ms > next_start_ms:
            k -= 1
        i = max(k, i + 1)
    return windows


def render_prompt(
    sentences: list[Sentence],
    window: Window,
    cfg: HighlightConfig,
    focus: str | None = None,
    max_candidates: int = 4,
) -> str:
    template = (
        resources.files("lahza_engine.highlight")
        .joinpath("prompts/highlight_uz.txt")
        .read_text(encoding="utf-8")
    )
    lines = []
    for s in sentences[window.first_id : window.last_id + 1]:
        dur = s.duration_ms / 1000
        lines.append(f"{s.id} | {s.speaker or '-'} | {dur:.1f} | {s.text}")
    focus_block = (
        f"9. Foydalanuvchi ustuvor mavzusi: {focus}. Shu mavzudagi lahzalarni afzal ko'r.\n"
        if focus
        else ""
    )
    return template.format(
        min_s=cfg.min_clip_ms // 1000,
        max_s=cfg.max_clip_ms // 1000,
        max_candidates=max_candidates,
        focus_block=focus_block,
        lines="\n".join(lines),
    )


def parse_response(raw: str, window: Window) -> list[LlmCandidate]:
    """JSON sxema + oyna chegarasini tekshiradi. Yaroqsiz nomzodlar tashlab yuboriladi."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("LLM javobi JSON emas")
        return []
    items = data.get("nomzodlar", []) if isinstance(data, dict) else []
    out: list[LlmCandidate] = []
    for item in items:
        try:
            c = LlmCandidate.model_validate(item)
        except ValidationError as e:
            log.info("nomzod rad etildi: %s", e.errors()[:1])
            continue
        if c.start_id < window.first_id or c.end_id > window.last_id:
            log.info("nomzod oynadan tashqarida: %s-%s", c.start_id, c.end_id)
            continue
        out.append(c)
    return out


class LlamaServerClient:
    def __init__(self, base_url: str, model_id: str, timeout_s: float = 600.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self._http = httpx.Client(timeout=timeout_s)

    def complete_json(self, prompt: str, schema: dict, temperature: float = 0.2) -> str:
        body = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "nomzodlar", "schema": schema, "strict": True},
            },
        }
        r = self._http.post(f"{self.base_url}/v1/chat/completions", json=body)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def close(self) -> None:
        self._http.close()


def propose_candidates(
    client: LlamaServerClient,
    sentences: list[Sentence],
    cfg: HighlightConfig,
    focus: str | None = None,
    on_progress=None,
) -> list[LlmCandidate]:
    """Map bosqichi: har oynadan nomzodlar."""
    windows = make_windows(sentences, cfg)
    schema = json_schema()
    found: list[LlmCandidate] = []
    for i, w in enumerate(windows):
        prompt = render_prompt(sentences, w, cfg, focus=focus)
        raw = client.complete_json(prompt, schema)
        found.extend(parse_response(raw, w))
        if on_progress:
            on_progress((i + 1) / len(windows))
    return found


def validate_full_response(raw: str) -> LlmResponse:
    """Testlar va diagnostika uchun: butun javobni qat'iy tekshirish."""
    return LlmResponse.model_validate_json(raw)
