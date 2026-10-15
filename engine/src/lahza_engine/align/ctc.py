"""CTC forced alignment (TZ 6-bo'lim, 1-yo'l).

Tayyor transkript CTC akustik modelning log-ehtimolliklariga Viterbi bilan tekislanadi.
Algoritm `torchaudio.functional.forced_align` bilan bir xil (blank'li standart CTC trellis);
bu yerda sof numpy - PyTorch'siz ham ishlaydi va testlanadi. Akustik model (emissiyalar)
alohida: R0'da tanlanadi (Omnilingual CTC yoki o'z modelimiz).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TokenSpan:
    token_index: int  # targets ichidagi indeks
    start_frame: int
    end_frame: int  # inklyuziv emas
    score: float


def forced_align(log_probs: np.ndarray, targets: list[int], blank: int = 0) -> list[TokenSpan]:
    """log_probs: [T, V] (log-softmax). targets: blank'siz token ID'lar.

    Qaytaradi: har target token uchun kadrlar oralig'i. Tekislab bo'lmasa ValueError.
    """
    T, _ = log_probs.shape
    L = len(targets)
    if L == 0:
        return []
    S = 2 * L + 1
    ext = np.full(S, blank, dtype=np.int64)
    ext[1::2] = targets
    # s-2 dan o'tish: faqat blank bo'lmagan va oldingi tokenga teng bo'lmagan holatlarga.
    allow2 = np.zeros(S, dtype=bool)
    allow2[2:] = (ext[2:] != blank) & (ext[2:] != ext[:-2])
    neg = -np.inf
    lp_ext = np.asarray(log_probs, dtype=np.float64)[:, ext]  # [T, S]
    dp = np.full((T, S), neg, dtype=np.float64)
    bp = np.zeros((T, S), dtype=np.int8)  # 0: o'zi, 1: s-1, 2: s-2
    dp[0, 0] = lp_ext[0, 0]
    if S > 1:
        dp[0, 1] = lp_ext[0, 1]
    c1 = np.empty(S, dtype=np.float64)
    c2 = np.empty(S, dtype=np.float64)
    for t in range(1, T):
        prev = dp[t - 1]
        # S o'qi bo'yicha vektorlashgan: tenglikda avvalgi variant (o'zi < s-1 < s-2) ustun.
        best = prev.copy()
        arg = np.zeros(S, dtype=np.int8)
        c1[0] = neg
        c1[1:] = prev[:-1]
        m = c1 > best
        best[m] = c1[m]
        arg[m] = 1
        c2[:2] = neg
        c2[2:] = prev[:-2]
        c2[~allow2] = neg
        m = c2 > best
        best[m] = c2[m]
        arg[m] = 2
        ok = best != neg
        dp[t, ok] = best[ok] + lp_ext[t, ok]
        bp[t, ok] = arg[ok]
    end_s = S - 1 if dp[T - 1, S - 1] >= dp[T - 1, S - 2] else S - 2
    if dp[T - 1, end_s] == neg:
        raise ValueError("tekislab bo'lmadi: audio transkript uchun juda qisqa")
    path = np.zeros(T, dtype=np.int64)
    s = end_s
    for t in range(T - 1, -1, -1):
        path[t] = s
        s -= int(bp[t, s])
    # Yo'l monoton: har target holati uzluksiz kadrlar bloki.
    states, first, counts = np.unique(path, return_index=True, return_counts=True)
    where = {int(st): (int(f), int(c)) for st, f, c in zip(states, first, counts, strict=True)}
    probs = np.exp(lp_ext[np.arange(T), path])
    spans: list[TokenSpan] = []
    for i in range(L):
        hit = where.get(2 * i + 1)
        if hit is None:
            raise ValueError(f"token {i} kadrga tushmadi")
        f, c = hit
        spans.append(TokenSpan(i, f, f + c, float(np.mean(probs[f : f + c]))))
    return spans


def word_times(
    spans: list[TokenSpan], word_token_counts: list[int], frame_ms: float, offset_ms: int = 0
) -> list[tuple[int, int, float]]:
    """Token oraliqlarini so'zlarga yig'adi: (start_ms, end_ms, ishonch)."""
    out = []
    i = 0
    for n in word_token_counts:
        group = spans[i : i + n]
        i += n
        if not group:
            continue
        a = offset_ms + int(group[0].start_frame * frame_ms)
        b = offset_ms + int(group[-1].end_frame * frame_ms)
        out.append((a, b, float(np.mean([g.score for g in group]))))
    return out
