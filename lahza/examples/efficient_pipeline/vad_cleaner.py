"""Conservative cleanup proposals from existing Silero/Whisper SOURCE timings.

No model inference/download. Pass Silero seconds multiplied by 1000 and rounded
ONCE at the boundary. Low/unknown confidence fillers require human review.
"""

import re
import unicodedata
from dataclasses import dataclass
from math import isfinite

from .edit_model import Span, keep_spans, merge_spans, ms


@dataclass(frozen=True)
class Word:
    id: str
    text: str
    start_ms: int
    end_ms: int
    confidence: float | None = None


@dataclass(frozen=True)
class Config:
    silence_ms: int = 600
    retain_pause_ms: int = 180
    edge_pad_ms: int = 80
    word_guard_ms: int = 40
    min_cut_ms: int = 80
    min_token_ms: int = 120
    min_confidence: float = 0.8
    terms: tuple[str, ...] = ("haligi", "anaqa", "demak", "xo'sh", "e-e-e")
    allow_terms: tuple[str, ...] = ()  # explicit permission for meaningful words


@dataclass(frozen=True)
class Review:
    word_ids: tuple[str, ...]
    text: str
    span: Span
    reason: str


@dataclass(frozen=True)
class CleanupPlan:
    cuts: tuple[Span, ...]
    review: tuple[Review, ...]
    auto_word_ids: tuple[str, ...]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.translate(str.maketrans({c: "'" for c in "‘’ʻʼ`´"}))
    return " ".join(re.sub(r"[^\w']+", " ", text).split()).strip("'")


def plan_cleanup(
    words: list[Word], speech: list[Span], duration_ms: int, config: Config | None = None
) -> CleanupPlan:
    """Silence cuts never intersect ANY word; filler cuts protect other words.

    Missing/empty VAD means unknown speech, so silence cleanup is disabled.
    Overlapping VAD intervals are unioned. Phrase matches use longest-first,
    maximum 180ms interword gaps, and occurrence IDs (not transcript mutation).
    """
    config = config or Config()
    duration = ms(duration_ms)
    if duration == 0:
        raise ValueError("positive source duration required")
    for name in (
        "silence_ms",
        "retain_pause_ms",
        "edge_pad_ms",
        "word_guard_ms",
        "min_cut_ms",
        "min_token_ms",
    ):
        ms(getattr(config, name))
    if (
        config.min_cut_ms < 1
        or not isfinite(config.min_confidence)
        or not 0 <= config.min_confidence <= 1
    ):
        raise ValueError("invalid cleanup thresholds")
    ordered = sorted(words, key=lambda w: (w.start_ms, w.end_ms))
    if len({w.id for w in ordered}) != len(ordered) or any(not w.id for w in ordered):
        raise ValueError("unique nonempty word IDs required")
    for word in ordered:
        if ms(word.start_ms) >= ms(word.end_ms) or word.end_ms > duration:
            raise ValueError("word outside source")
        if word.confidence is not None and (
            not isfinite(word.confidence) or not 0 <= word.confidence <= 1
        ):
            raise ValueError("invalid word confidence")
    vad = merge_spans(speech)
    if vad and vad[-1][1] > duration:
        raise ValueError("VAD outside source")
    allowed = {normalize(t) for t in config.allow_terms}
    terms = {normalize(t) for t in config.terms} | allowed
    ambiguous = {normalize("demak"), normalize("xo'sh")}
    review, auto, filler_cuts = [], set(), []
    index = 0
    while index < len(ordered):
        match = None
        for count in range(min(6, len(ordered) - index), 0, -1):
            group = ordered[index : index + count]
            token = normalize(" ".join(w.text for w in group))
            hesitation = re.fullmatch(r"e(?:\s*e){2,}", token)
            if (token in terms or hesitation) and all(
                0 <= b.start_ms - a.end_ms <= 180 for a, b in zip(group, group[1:], strict=False)
            ):
                match = group, token
                break
        if match is None:
            index += 1
            continue
        group, token = match
        lo, hi = group[0].start_ms, group[-1].end_ms
        reason = (
            "meaningful_term"
            if token in ambiguous and token not in allowed
            else "short_token"
            if hi - lo < config.min_token_ms
            else "low_or_missing_confidence"
            if any(w.confidence is None or w.confidence < config.min_confidence for w in group)
            else ""
        )
        if reason:
            review.append(
                Review(
                    tuple(w.id for w in group), " ".join(w.text for w in group), (lo, hi), reason
                )
            )
        else:
            auto.update(w.id for w in group)
            filler_cuts.append((lo, hi))
        index += len(group)

    def protected(exclude_auto=False):
        return merge_spans(
            [
                (
                    max(0, w.start_ms - config.word_guard_ms),
                    min(duration, w.end_ms + config.word_guard_ms),
                )
                for w in ordered
                if not exclude_auto or w.id not in auto
            ]
        )

    def subtract(candidates, guards):
        # Sorted disjoint candidates and guards: a monotone sweep, not C * W.
        result, index = [], 0
        for lo, hi in merge_spans(candidates):
            while index < len(guards) and guards[index][1] <= lo:
                index += 1
            cursor, scan = lo, index
            while scan < len(guards) and guards[scan][0] < hi:
                a, b = guards[scan]
                if min(a, hi) - cursor >= config.min_cut_ms:
                    result.append((cursor, min(a, hi)))
                cursor = max(cursor, b)
                if b > hi:
                    break
                scan += 1
            if hi - cursor >= config.min_cut_ms:
                result.append((cursor, hi))
            index = scan
        return result

    silence = []
    if vad:
        for a, b in keep_spans((0, duration), vad):
            pad = config.edge_pad_ms + config.retain_pause_ms // 2
            end_pad = config.edge_pad_ms + config.retain_pause_ms - config.retain_pause_ms // 2
            if b - a > config.silence_ms and a + pad < b - end_pad:
                silence.append((a + pad, b - end_pad))
    cuts = merge_spans(subtract(silence, protected()) + subtract(filler_cuts, protected(True)))
    return CleanupPlan(tuple(cuts), tuple(review), tuple(w.id for w in ordered if w.id in auto))
