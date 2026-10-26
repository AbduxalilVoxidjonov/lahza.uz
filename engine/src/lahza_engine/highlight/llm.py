"""Lokal LLM (llama.cpp `llama-server`) orqali highlight nomzodlari - map/reduce (TZ 7-bo'lim).

Server dastur ichida yetkaziladi va 127.0.0.1 da ishlaydi (runtime/llama_server.py).
OpenAI-mos endpoint ishlatiladi: POST /v1/chat/completions.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    """OpenAI-mos `llama-server` mijozi. httpx.Client oqimlar orasida xavfsiz - parallel oynalar
    bitta mijoz orqali yuboriladi."""

    def __init__(self, base_url: str, model_id: str, timeout_s: float = 600.0,
                 max_tokens: int | None = None, thinking: bool = False,
                 dry_multiplier: float = 0.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.thinking = thinking
        self.dry_multiplier = dry_multiplier
        self._http = httpx.Client(timeout=timeout_s)

    def request_body(self, prompt: str, schema: dict, temperature: float = 0.2) -> dict:
        body: dict = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "nomzodlar", "schema": schema, "strict": True},
            },
            # M3-PERF-2: Qwen3 standart holatda avval <think> matnini yozadi (o'lchov: ~5000
            # token/oyna). JSON grammatika bilan bu foydasiz va eng katta vaqt sababi edi.
            "chat_template_kwargs": {"enable_thinking": self.thinking},
            "cache_prompt": True,
        }
        if self.max_tokens:
            body["max_tokens"] = self.max_tokens
        if self.dry_multiplier > 0:
            # DRY: takrorlanuvchi n-gramlarni jazolaydi ("Bu narsa nima? Bu narsa nima? ..." ->
            # maydon chegarasigacha). JSON qo'shtirnoq/":"/qator - standart ajratkichlar, shuning
            # uchun kalitlar va sxema tuzilmasiga ta'sir qilmaydi.
            body["dry_multiplier"] = self.dry_multiplier
        return body

    def complete_json(self, prompt: str, schema: dict, temperature: float = 0.2) -> str:
        r = self._http.post(f"{self.base_url}/v1/chat/completions",
                            json=self.request_body(prompt, schema, temperature))
        r.raise_for_status()
        data = r.json()
        choice = data["choices"][0]
        t = data.get("timings") or {}
        log.info("LLM oyna: prompt=%s tok (%.0f tok/s), chiqish=%s tok (%.1f tok/s), finish=%s",
                 t.get("prompt_n"), t.get("prompt_per_second") or 0.0, t.get("predicted_n"),
                 t.get("predicted_per_second") or 0.0, choice.get("finish_reason"))
        if choice.get("finish_reason") == "length":
            log.warning("LLM javobi max_tokens=%s da kesildi", self.max_tokens)
        return choice["message"]["content"]

    def close(self) -> None:
        self._http.close()


def propose_candidates(
    client: LlamaServerClient,
    sentences: list[Sentence],
    cfg: HighlightConfig,
    focus: str | None = None,
    on_progress=None,
) -> list[LlmCandidate]:
    """Map bosqichi: har oynadan nomzodlar.

    Oynalar `cfg.llm_parallel` ta oqimda yuboriladi (llama-server shuncha slot bilan ishga
    tushiriladi, Metal'da bir nechta ketma-ketlikni birga dekodlash deyarli bepul). Natija
    tartibi oynalar tartibida qoladi; progress asosiy oqimda chaqiriladi.
    """
    windows = make_windows(sentences, cfg)
    if not windows:
        return []
    schema = json_schema(cfg.llm_max_candidates)
    prompts = [render_prompt(sentences, w, cfg, focus=focus, max_candidates=cfg.llm_max_candidates)
               for w in windows]
    results: list[list[LlmCandidate]] = [[] for _ in windows]
    workers = max(1, min(cfg.llm_parallel, len(windows)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="lahza-llm") as pool:
        futs = {pool.submit(client.complete_json, p, schema): i for i, p in enumerate(prompts)}
        try:
            for done, fut in enumerate(as_completed(futs), start=1):
                i = futs[fut]
                results[i] = parse_response(fut.result(), windows[i])
                if on_progress:
                    on_progress(done / len(windows))
        except BaseException:
            for f in futs:
                f.cancel()
            raise
    return [c for r in results for c in r]


def validate_full_response(raw: str) -> LlmResponse:
    """Testlar va diagnostika uchun: butun javobni qat'iy tekshirish."""
    return LlmResponse.model_validate_json(raw)
