"""Diarizatsiya spikerlarini yuz treklariga bog'lash (TZ 8-bo'lim: ASD bali + diarizatsiya + lab harakati).

ASD modeli (LR-ASD, ONNX) har kuzatuvda har trek uchun 0..1 ball beradi. Bu modul ballar va
diarizatsiya bo'yicha "spiker -> trek" xaritasini birgalikda uchrash (co-occurrence) orqali quradi.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from lahza_engine.reframe.faces import Box


@dataclass
class AsdSample:
    t_ms: int
    speaker: str | None  # diarizatsiya bo'yicha shu daqiqadagi spiker
    track_scores: dict[int, float]  # trek_id -> ASD bali


def learn_speaker_to_track(samples: list[AsdSample], min_score: float = 0.5) -> dict[str, int]:
    acc: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for s in samples:
        if s.speaker is None:
            continue
        for tid, sc in s.track_scores.items():
            if sc >= min_score:
                acc[s.speaker][tid] += sc
    # Ochko'z tayinlash: eng kuchli juftlikdan boshlab, bitta trek bitta spikerga.
    pairs = sorted(
        ((score, spk, tid) for spk, d in acc.items() for tid, score in d.items()), reverse=True
    )
    mapping: dict[str, int] = {}
    used: set[int] = set()
    for _, spk, tid in pairs:
        if spk in mapping or tid in used:
            continue
        mapping[spk] = tid
        used.add(tid)
    return mapping


def fused_scores(
    track_ids: Sequence[int], asd: dict[int, float], expected: int | None,
    asd_weight: float = 0.6,
) -> dict[int, float]:
    """Har ko'rinayotgan trek uchun: w*ASD + (1-w)*[diarizatsiya kutgan trek]. ASD yo'q - 0."""
    return {
        tid: asd_weight * asd.get(tid, 0.0) + (1 - asd_weight) * (1.0 if tid == expected else 0.0)
        for tid in track_ids
    }


def active_track(
    sample: AsdSample, speaker_to_track: dict[str, int], asd_weight: float = 0.6
) -> int | None:
    """Yakuniy qaror = ASD bali va diarizatsiya bo'yicha kutilgan trekning vaznli yig'indisi."""
    if not sample.track_scores:
        return None
    expected = speaker_to_track.get(sample.speaker or "")
    fused = fused_scores(list(sample.track_scores), sample.track_scores, expected, asd_weight)
    return max(fused, key=lambda tid: fused[tid])


def largest_face_index(boxes: Sequence[Box]) -> int | None:
    """ASD modeli yo'q (va lab harakati baholanmaydi) bo'lsa faol yuz - eng kattasi (M1-RND-2)."""
    if not boxes:
        return None
    return max(range(len(boxes)), key=lambda i: boxes[i].w * boxes[i].h)


def active_index(
    boxes: Sequence[Box],
    track_ids: Sequence[int] | None = None,
    sample: AsdSample | None = None,
    speaker_to_track: dict[str, int] | None = None,
) -> int | None:
    """Faol yuz indeksi: ASD ballari bo'lsa - `active_track`, aks holda eng katta yuz."""
    if sample is not None and sample.track_scores and track_ids is not None:
        tid = active_track(sample, speaker_to_track or {})
        if tid is not None and tid in track_ids:
            return list(track_ids).index(tid)
    return largest_face_index(boxes)
