"""Sifat o'lchovlari (TZ 15-bo'lim): WER/CER, so'z chegarasi xatosi, highlight precision@k."""

from __future__ import annotations

import re
from collections.abc import Sequence

import numpy as np

from lahza_engine.text.orthography import fold_for_match

_PUNCT = re.compile(r"[^\w\s']", flags=re.UNICODE)


def normalize_for_wer(text: str) -> list[str]:
    """Kichik harf, apostroflar bir xil, tinish belgilarisiz. Raqam->so'z o'girish - R0 vazifasi."""
    t = _PUNCT.sub(" ", fold_for_match(text))
    return t.split()


def edit_distance(ref: Sequence[str], hyp: Sequence[str]) -> int:
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1]


def wer(ref: str, hyp: str) -> float:
    r, h = normalize_for_wer(ref), normalize_for_wer(hyp)
    return edit_distance(r, h) / max(1, len(r))


def cer(ref: str, hyp: str) -> float:
    r = list(" ".join(normalize_for_wer(ref)))
    h = list(" ".join(normalize_for_wer(hyp)))
    return edit_distance(r, h) / max(1, len(r))


def boundary_errors(ref: list[tuple[int, int]], hyp: list[tuple[int, int]]) -> dict[str, float]:
    """Bir xil tartibdagi so'zlar uchun |start| va |end| xatolari (ms): median va p95."""
    n = min(len(ref), len(hyp))
    if n == 0:
        return {"median_ms": float("nan"), "p95_ms": float("nan")}
    errs = [abs(ref[i][0] - hyp[i][0]) for i in range(n)] + [abs(ref[i][1] - hyp[i][1]) for i in range(n)]
    return {"median_ms": float(np.median(errs)), "p95_ms": float(np.percentile(errs, 95))}


def span_iou(a: tuple[int, int], b: tuple[int, int]) -> float:
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union else 0.0


def precision_at_k(pred: list[tuple[int, int]], gold: list[tuple[int, int]], k: int = 5,
                   iou: float = 0.5) -> float:
    top = pred[:k]
    if not top:
        return 0.0
    hits = sum(1 for p in top if any(span_iou(p, g) >= iou for g in gold))
    return hits / len(top)


def recall(pred: list[tuple[int, int]], gold: list[tuple[int, int]], iou: float = 0.5) -> float:
    if not gold:
        return float("nan")
    return sum(1 for g in gold if any(span_iou(p, g) >= iou for p in pred)) / len(gold)
