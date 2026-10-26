"""Real natijalardan o'rganish (PRO-6): klip ko'rishlari/like'lari -> "Lahza bali" vaznlari.

Ball komponentlari (`finder.find_highlights`): `llm` (LLM mezonlari o'rtachasi x10) va `signal`
(audio/matn signallari), yakuniy ball `weight_llm * llm + weight_signals * signal - jarima`.
Bu yerda shu ikki vazn ehtiyotkor moslashtiriladi:

1. Maqsad: `y = log1p(views) + 0.5 * log1p(likes)` (dumli taqsimot siqiladi).
2. Maqsad ranglarga aylantiriladi (bitta "viral" klip natijani ag'darmaydi), so'ng standartlangan
   xususiyatlarda ridge regressiya (`RIDGE`) -> xom shkaladagi musbat koeffitsiyentlar
   -> ulushlar (yig'indi standart vaznlar yig'indisiga teng, ball shkalasi 0..100 saqlanadi).
3. Bayes uslubidagi qisqartirish: `w = a * w_fit + (1 - a) * w_prior`, `a = n / (n + PRIOR_STRENGTH)`.
4. Har vazn `BOUNDS` ichida; `MIN_SAMPLES` dan kam namuna yoki xususiyat o'zgarmas bo'lsa -
   o'rganilmaydi (standart vaznlar qoladi).

Natija namunalar to'plamining deterministik funksiyasi: tartib va qayta hisoblash natijani
o'zgartirmaydi (yig'ilib boruvchi siljish yo'q).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

from lahza_engine.config import HighlightConfig

FEATURES: tuple[str, ...] = ("llm", "signal")
WEIGHT_KEYS: dict[str, str] = {"llm": "weight_llm", "signal": "weight_signals"}
MIN_SAMPLES = 8
PRIOR_STRENGTH = 20.0
RIDGE = 1.0
BOUNDS = (0.1, 0.9)


@dataclass(frozen=True)
class Sample:
    features: Mapping[str, float]
    views: int
    likes: int | None = None

    def target(self) -> float:
        return math.log1p(max(0, self.views)) + 0.5 * math.log1p(max(0, self.likes or 0))


@dataclass
class LearnResult:
    weights: dict[str, float]
    learned: bool
    n_used: int
    reason: str = ""
    fit: dict[str, float] = field(default_factory=dict)


def default_weights(cfg: HighlightConfig | None = None) -> dict[str, float]:
    cfg = cfg or HighlightConfig()
    return {"weight_llm": float(cfg.weight_llm), "weight_signals": float(cfg.weight_signals)}


def _bounded(w: np.ndarray, total: float) -> np.ndarray:
    """Chegaralarga qisib, yig'indini `total` ga qaytaradi (2 vaznda yopiq yechim)."""
    lo, hi = BOUNDS[0] * total, BOUNDS[1] * total
    w = np.clip(w, lo, hi)
    for _ in range(10):
        w = w * (total / w.sum())
        if np.all(w >= lo - 1e-9) and np.all(w <= hi + 1e-9):
            break
        w = np.clip(w, lo, hi)
    return w


def _ranks(y: np.ndarray) -> np.ndarray:
    """O'rtacha ranglar (tenglarda bir xil rang)."""
    order = np.argsort(y, kind="mergesort")
    ranks = np.empty(len(y), dtype=float)
    ys = y[order]
    i = 0
    while i < len(ys):
        j = i
        while j + 1 < len(ys) and ys[j + 1] == ys[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return ranks


def fit_weights(samples: Sequence[Sample], prior: Mapping[str, float] | None = None) -> LearnResult:
    prior = dict(prior or default_weights())
    w0 = np.array([prior[WEIGHT_KEYS[f]] for f in FEATURES], dtype=float)
    total = float(w0.sum())
    usable = [s for s in samples
              if all(f in s.features and math.isfinite(float(s.features[f])) for f in FEATURES)
              and s.views >= 0]
    n = len(usable)
    if n < MIN_SAMPLES:
        return LearnResult(dict(prior), False, n, f"kamida {MIN_SAMPLES} ta namuna kerak")
    x = np.array([[float(s.features[f]) for f in FEATURES] for s in usable])
    y = np.array([s.target() for s in usable])
    sd_x = x.std(axis=0)
    if np.any(sd_x < 1e-6):
        return LearnResult(dict(prior), False, n, "xususiyatlar o'zgarmas")
    if y.std() < 1e-9:
        return LearnResult(dict(prior), False, n, "natijalar bir xil")
    # Rang (tartib) bo'yicha regressiya: bitta "viral" natija yoki g'ayrioddiy ball vaznlarni
    # ag'darmasligi uchun (Spearman uslubi). Koeffitsiyent xom shkalaga `sd_x` orqali qaytariladi.
    rx = np.column_stack([_ranks(x[:, k]) for k in range(x.shape[1])])
    xs = (rx - rx.mean(axis=0)) / rx.std(axis=0)
    r = _ranks(y)
    ys = (r - r.mean()) / r.std()
    beta = np.linalg.solve(xs.T @ xs + RIDGE * np.eye(len(FEATURES)), xs.T @ ys)
    raw = np.maximum(beta / sd_x, 0.0)  # xom (0..100) shkala; manfiy ta'sir - 0
    if raw.sum() <= 0:
        return LearnResult(dict(prior), False, n, "musbat bog'liqlik topilmadi")
    w_fit = raw / raw.sum() * total
    alpha = n / (n + PRIOR_STRENGTH)
    w = _bounded(alpha * w_fit + (1 - alpha) * w0, total)
    weights = {WEIGHT_KEYS[f]: round(float(v), 4) for f, v in zip(FEATURES, w, strict=True)}
    fit = {f: round(float(b), 4) for f, b in zip(FEATURES, beta, strict=True)}
    return LearnResult(weights, True, n, "", fit)


def apply_weights(cfg: HighlightConfig, weights: Mapping[str, float] | None) -> HighlightConfig:
    """Saqlangan vaznlarni sozlamaga qo'yadi (noma'lum kalitlar e'tiborsiz)."""
    if not weights:
        return cfg
    upd = {k: float(v) for k, v in weights.items() if k in WEIGHT_KEYS.values()}
    return cfg.model_copy(update=upd)


def features_of(scores: Mapping[str, float]) -> dict[str, float]:
    """Klipning `scores_json` dan o'rganish xususiyatlari (bo'lmaganlari tushib qoladi)."""
    return {f: float(scores[f]) for f in FEATURES if f in scores and scores[f] is not None}
