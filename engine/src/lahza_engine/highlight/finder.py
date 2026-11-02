"""Highlight topish: nomzodlar -> chegaralarni tekislash -> ball -> NMS -> klipler.

Ikki rejim (TZ 7-bo'lim):
* LLM rejimi - LLM nomzodlari + signal ballari (gibrid "Lahza bali").
* Lite rejimi (zaxira) - LLM yo'q bo'lsa: faqat signallar, gap chegaralari va jarimalar.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from lahza_engine.config import HighlightConfig
from lahza_engine.highlight.boundaries import ClipSpan, snap
from lahza_engine.highlight.rules import start_penalty
from lahza_engine.highlight.schema import LlmCandidate
from lahza_engine.highlight.signals import SignalReport
from lahza_engine.types import Clip, ClipSource, Sentence


@dataclass
class Scored:
    span: ClipSpan
    score: float
    parts: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    llm: LlmCandidate | None = None


def iou(a: ClipSpan, b: ClipSpan) -> float:
    inter = max(0, min(a.end_ms, b.end_ms) - max(a.start_ms, b.start_ms))
    union = max(a.end_ms, b.end_ms) - min(a.start_ms, b.start_ms)
    return inter / union if union else 0.0


def nms(items: list[Scored], threshold: float, limit: int) -> list[Scored]:
    kept: list[Scored] = []
    for it in sorted(items, key=lambda x: x.score, reverse=True):
        if all(iou(it.span, k.span) <= threshold for k in kept):
            kept.append(it)
        if len(kept) >= limit:
            break
    return kept


def _signal_score(span: ClipSpan, signals: SignalReport) -> float:
    by_id = signals.by_id()
    vals = [by_id[i].score() for i in range(span.start_id, span.end_id + 1) if i in by_id]
    if not vals:
        return 50.0
    # Boshlanish (hook zonasi) muhimroq: birinchi 3 gap ikki barobar vazn oladi.
    weights = [2.0 if k < 3 else 1.0 for k in range(len(vals))]
    return sum(v * w for v, w in zip(vals, weights, strict=True)) / sum(weights)


def _penalty(span: ClipSpan, sentences: list[Sentence], cfg: HighlightConfig) -> tuple[float, list[str]]:
    p, reasons = start_penalty(sentences[span.start_id].text)
    if not (cfg.min_clip_ms <= span.duration_ms <= cfg.max_clip_ms):
        p += 0.3
        reasons.append("davomiylik maqsaddan tashqarida")
    return p, reasons


def lite_candidates(sentences: list[Sentence], cfg: HighlightConfig) -> list[ClipSpan]:
    """Har gapdan boshlanadigan, davomiylikka sig'adigan eng uzun gap ketma-ketligi."""
    spans: list[ClipSpan] = []
    n = len(sentences)
    for a in range(n):
        b = a
        while b + 1 < n and sentences[b + 1].end_ms - sentences[a].start_ms <= cfg.max_clip_ms:
            b += 1
        if sentences[b].end_ms - sentences[a].start_ms >= cfg.min_clip_ms * 0.8:
            spans.append(snap(sentences, a, b, cfg))
    return spans


def _first_strong_sentence(span: ClipSpan, sentences: list[Sentence], signals: SignalReport) -> str:
    by_id = signals.by_id()
    ids = list(range(span.start_id, min(span.end_id, span.start_id + 2) + 1))
    best = max(ids, key=lambda i: by_id[i].score() if i in by_id else 0.0)
    text = sentences[best].text.strip()
    return text if len(text) <= 80 else text[:77].rstrip() + "..."


def find_highlights(
    media_id: str,
    sentences: list[Sentence],
    signals: SignalReport,
    cfg: HighlightConfig,
    llm_candidates: Sequence[LlmCandidate] | None = None,
    llm_model_id: str | None = None,
) -> list[Clip]:
    if not sentences:
        return []
    scored: list[Scored] = []
    use_llm = llm_candidates is not None
    if use_llm:
        for c in llm_candidates or []:
            span = snap(sentences, c.start_id, c.end_id, cfg)
            sig = _signal_score(span, signals)
            llm_part = c.ballar.mean() * 10.0
            pen, reasons = _penalty(span, sentences, cfg)
            if not c.mustaqil:
                pen += 0.2
                reasons.append("LLM: mustaqil emas")
            total = cfg.weight_llm * llm_part + cfg.weight_signals * sig - 30.0 * pen
            scored.append(
                Scored(span, max(0.0, min(100.0, total)), {"llm": llm_part, "signal": sig}, reasons, c)
            )
    else:
        for span in lite_candidates(sentences, cfg):
            sig = _signal_score(span, signals)
            pen, reasons = _penalty(span, sentences, cfg)
            total = sig - 30.0 * pen
            scored.append(Scored(span, max(0.0, min(100.0, total)), {"signal": sig}, reasons))

    best = nms(scored, cfg.nms_iou, cfg.clip_count)
    clips: list[Clip] = []
    for s in sorted(best, key=lambda x: x.span.start_ms):
        c = s.llm
        clips.append(
            Clip(
                id=uuid.uuid4().hex[:12],
                media_id=media_id,
                start_ms=s.span.start_ms,
                end_ms=s.span.end_ms,
                start_sentence_id=s.span.start_id,
                end_sentence_id=s.span.end_id,
                hook_sentence_id=c.hook_id if c else None,
                title=c.sarlavha if c else _first_strong_sentence(s.span, sentences, signals),
                caption=c.izoh_matni if c else "",
                hashtags=list(c.heshteglar) if c else [],
                kind=c.turi if c else None,
                score=round(s.score, 1),
                scores={k: round(v, 1) for k, v in s.parts.items()},
                reason=(c.sabab if c else "Signal ballari bo'yicha tanlandi (Lite rejim)")
                + ("; " + "; ".join(s.reasons) if s.reasons else ""),
                source=ClipSource.AI_LLM if c else ClipSource.AI_LITE,
                llm_model_id=llm_model_id if c else None,
            )
        )
    return clips
