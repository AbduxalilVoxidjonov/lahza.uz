"""Aktiv spiker: ASD ballari + diarizatsiya birlashmasi (TZ 8-bo'lim, M3-RF-1).

Kirish - analiz chastotasidagi `Observation` lar (yuzlar, treker ID, ASD ballari) va diarizatsiya
segmentlari (`diarize.Turn`, exclusive) + ustma-ust oraliqlar. Chiqish - har kuzatuvda tanlangan
faol yuz (`active_index`) va past ishonchda keng kadr (`wide` -> FIT_BLUR layout).

Qadamlar:
1. Har kuzatuvga shu paytdagi spiker (diarizatsiya) va ustma-ust gapirish belgisi.
2. Spiker <-> trek xaritasi: ASD ballarining birgalikda uchrashi (`learn_speaker_to_track`).
3. Har kuzatuvda trek bali = w*ASD + (1-w)*[diarizatsiya kutgan trek] (`fused_scores`).
4. Gisterezis: yangi yuz joriydan `speaker_switch_margin` ga ustun bo'lib `..._confirm_ms` davom
   etsa va joriy yuz kamida `speaker_min_hold_ms` ushlangan bo'lsa almashadi. Joriy yuz kadrda
   yo'qolsa yoki sahna kesilsa - darhol.
5. Nutq bor, lekin eng yaxshi bal `active_min_confidence` dan past holat
   `low_confidence_wide_ms` davom etsa - keng kadr.

ASD modeli yo'q (ballar bo'sh) bo'lsa - hozirgi heuristika: eng katta yuz (gisterezis bilan,
o'lchamlari yaqin ikki yuz orasida sakramasin); keng kadrga o'tilmaydi.
Kamera yo'li (o'lik zona, One-Euro, keskin kesim) o'zgarmaydi - `planner.plan` ga beriladi.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from lahza_engine.config import ReframeConfig
from lahza_engine.diarize.assign import Turn
from lahza_engine.reframe.planner import Observation
from lahza_engine.reframe.speaker_map import AsdSample, fused_scores, learn_speaker_to_track


@dataclass
class ActiveDecision:
    t_ms: int
    track_id: int | None
    index: int | None  # o.faces ichidagi indeks
    confidence: float
    wide: bool = False
    source: str = "none"  # "asd" | "largest" | "none"


def speaker_at(turns: Sequence[Turn], t_ms: int) -> str | None:
    """Exclusive diarizatsiya bo'yicha t_ms dagi spiker (segment [start, end))."""
    for t in turns:
        if t.start_ms <= t_ms < t.end_ms:
            return t.speaker
    return None


def annotate_speech(
    obs: list[Observation], turns: Sequence[Turn] | None = None,
    overlaps: Sequence[tuple[int, int]] | None = None,
) -> list[Observation]:
    """Kuzatuvlarga diarizatsiya spikeri va ustma-ust belgisi (allaqachon bor bo'lsa saqlanadi)."""
    if not turns and not overlaps:
        return obs
    out = []
    for o in obs:
        spk = o.speaker if o.speaker is not None else speaker_at(turns or [], o.t_ms)
        ov = o.overlap_speech or any(a <= o.t_ms < b for a, b in overlaps or [])
        out.append(replace(o, speaker=spk, overlap_speech=ov))
    return out


def _ids(o: Observation) -> list[int]:
    """Treker ID lari; berilmagan bo'lsa - indekslar (bir kadrdagi yuzlar tartibi)."""
    return list(o.track_ids) if len(o.track_ids) == len(o.faces) else list(range(len(o.faces)))


def _area_scores(o: Observation, ids: list[int]) -> dict[int, float]:
    areas = [b.w * b.h for b in o.faces]
    top = max(areas) or 1.0
    return {tid: a / top for tid, a in zip(ids, areas, strict=True)}


def select_active(obs: list[Observation], cfg: ReframeConfig) -> list[ActiveDecision]:
    """Har kuzatuv uchun faol yuz qarori (kuzatuvlar vaqt bo'yicha saralangan bo'lishi kerak)."""
    has_asd = any(o.asd_scores for o in obs)
    mapping: dict[str, int] = {}
    if has_asd:
        mapping = learn_speaker_to_track(
            [AsdSample(o.t_ms, o.speaker, o.asd_scores) for o in obs], cfg.asd_min_score
        )
    out: list[ActiveDecision] = []
    cur: int | None = None
    cur_since = 0
    cand: int | None = None
    cand_since = 0
    low_since: int | None = None
    for o in obs:
        if o.shot_cut:
            cur, cand, low_since = None, None, None
        if not o.faces:
            low_since = None
            out.append(ActiveDecision(o.t_ms, None, None, 0.0))
            continue
        ids = _ids(o)
        if has_asd:
            scores = fused_scores(ids, o.asd_scores, mapping.get(o.speaker or ""), cfg.asd_weight)
            speech = o.speaker is not None or any(
                o.asd_scores.get(t, 0.0) >= cfg.asd_min_score for t in ids
            )
        else:
            scores, speech = _area_scores(o, ids), False
        best = max(ids, key=lambda t: scores[t])
        if cur not in scores:
            cur, cur_since, cand = best, o.t_ms, None
        elif best != cur and scores[best] - scores[cur] >= cfg.speaker_switch_margin:
            if cand != best:
                cand, cand_since = best, o.t_ms
            if (o.t_ms - cand_since >= cfg.speaker_switch_confirm_ms
                    and o.t_ms - cur_since >= cfg.speaker_min_hold_ms):
                cur, cur_since, cand = best, o.t_ms, None
        else:
            cand = None
        conf = scores[cur] if has_asd else 1.0
        wide = False
        if has_asd and speech and scores[best] < cfg.active_min_confidence:
            low_since = o.t_ms if low_since is None else low_since
            wide = o.t_ms - low_since >= cfg.low_confidence_wide_ms
        else:
            low_since = None
        out.append(ActiveDecision(o.t_ms, cur, ids.index(cur), conf, wide,
                                  "asd" if has_asd else "largest"))
    return out


def resolve_active_speakers(
    obs: list[Observation], cfg: ReframeConfig, turns: Sequence[Turn] | None = None,
    overlaps: Sequence[tuple[int, int]] | None = None,
) -> list[Observation]:
    """Diarizatsiya + ASD -> `active_index`/`wide` to'ldirilgan kuzatuvlar (`planner.plan` uchun)."""
    ordered = annotate_speech(sorted(obs, key=lambda o: o.t_ms), turns, overlaps)
    decisions = select_active(ordered, cfg)
    return [replace(o, active_index=d.index, wide=d.wide) for o, d in zip(ordered, decisions,
                                                                          strict=True)]
