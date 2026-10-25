"""Qoidaga asoslangan montaj rejalashtiruvchi: shablon + manba tahlillari -> `MontageTimeline`.

Algoritm deterministik (bir xil kirish -> bir xil timeline; vaqt belgisi `now` orqali beriladi).
Qoidalar (docs/11 6.5, 5.5):

1. Nomzodlar: `highlight` - manba highlight'lari (bo'lmasa sahnalar, provenance'da izoh);
   `scenes` - shotlar (qisqalari qo'shniga qo'shiladi, uzunlari `max_shot_ms` oynalariga bo'linadi,
   asosiy oyna - eng yuqori faollik (energiya + keskinlik)); `full` - har manba to'liq.
2. Nutqli manbada (`respect_sentences`) chegaralar gap chegarasiga yopishtiriladi - so'z o'rtasida
   kesilmaydi (`highlight/boundaries.snap`).
3. Tanlash: ball bo'yicha ochko'z, maqsad davomiylikka (o'tishlar ustma-ustligi, intro/outro kartalari
   hisobga olingan) yetguncha; `max_per_source`; bir xil oraliq takrorlanmaydi.
4. Tartib: `berilgan` / `xronologik` / `ball` (ballda xilma-xillik: bir manbadan ketma-ket 2 tadan ortiq
   emas, bir shot ketma-ket kelmaydi - agar boshqa nomzod bo'lsa).
5. Effektlar trigger'lar bo'yicha (min_gap_ms, max_count), o'tishlar, rang, matn qatlamlari, subtitr
   so'zlari chiqish vaqtiga, musiqa, brend, audio, provenance.

Intro kartasi (`kind="card"`) birinchi video element USTIGA qo'yiladi (to'liq qoplovchi fon) va birinchi
element shu muddatga oldindan uzaytiriladi - tanlangan lahza karta tugagach boshlanadi. Outro kartasi
ham xuddi shunday oxirgi element ustida (element oxiridan uzaytiriladi).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from lahza_engine import __version__
from lahza_engine.config import HighlightConfig, Settings
from lahza_engine.highlight.boundaries import snap
from lahza_engine.montage.analyze import SourceAnalysis
from lahza_engine.montage.model import (
    ASPECT_SIZE,
    AudioMix,
    Brand,
    Captions,
    Format,
    FxRef,
    MediaRef,
    MontageTimeline,
    MusicItem,
    Provenance,
    TextItem,
    TransitionRef,
    VideoItem,
)
from lahza_engine.render.profiles import Platform, get_profile
from lahza_engine.subtitle.style import StyleTemplate
from lahza_engine.templates.model import FxRule, MusicSpec, Template, TextCard
from lahza_engine.types import Sentence, Word

CUT_PLUGIN = "uz.lahza.tr.cut"
MUSIC_ID = "music"
ON_END_LEAD_MS = 1500
"""on_end effekti oxirgi element tugashidan shuncha oldin boshlanadi."""
POINT_FX_MS = 3000
"""on_emphasis / on_speaker_change effektining davomiyligi (element oxirigacha emas)."""
OVERLAP_TOL_MS = 200
"""Bir manbadan tanlangan ikki oraliq shundan ko'p ustma-ust tushsa - takror hisoblanadi."""


class PlanError(ValueError):
    """Montajni rejalashtirib bo'lmadi (foydalanuvchiga ko'rsatiladigan o'zbekcha xabar)."""


@dataclass
class MontageOverrides:
    target_duration_ms: int | None = None
    aspect: str | None = None
    music_path: str | None = None
    title: str | None = None
    cta: str | None = None
    shou: str | None = None
    captions: bool | None = None
    caption_style: StyleTemplate | None = None
    logo_path: str | None = None
    transition: str | None = None
    color: str | None = None
    target_platform: Platform = "custom"


@dataclass
class _Cand:
    src: int
    start: int
    end: int
    score: float
    reason: str
    key: tuple[Any, ...]  # shot/highlight identifikatori (ketma-ket takrorlanmaslik uchun)
    primary: bool = True
    title: str = ""

    @property
    def dur(self) -> int:
        return self.end - self.start


@dataclass
class _Ctx:
    tpl: Template
    sources: list[SourceAnalysis]
    hl: HighlightConfig
    notes: list[str] = field(default_factory=list)

    def name(self, si: int) -> str:
        m = self.sources[si].media
        return m.path.replace("\\", "/").rsplit("/", 1)[-1] or m.id


# --- yordamchilar ----------------------------------------------------------------------------


def _activity(sa: SourceAnalysis, a: int, b: int) -> float | None:
    """[a, b) oralig'idagi o'rtacha faollik (egri chiziq bo'lmasa None)."""
    if not sa.curve or b <= a:
        return None
    step = max(1, sa.curve_step_ms)
    i0, i1 = a // step, max(a // step + 1, -(-b // step))
    vals = sa.curve[i0:i1]
    return sum(vals) / len(vals) if vals else None


def _best_window(sa: SourceAnalysis, a: int, b: int, length: int) -> tuple[int, int, float | None]:
    """[a, b) ichida `length` uzunlikdagi eng faol oyna (teng bo'lsa - eng erta)."""
    if length >= b - a:
        return a, b, _activity(sa, a, b)
    if not sa.curve:
        return a, a + length, None
    step = max(1, sa.curve_step_ms)
    starts = [a]
    s = -(-a // step) * step
    while s <= b - length:
        if s != a:
            starts.append(s)
        s += step
    if starts[-1] != b - length:
        starts.append(b - length)
    best = (a, -1.0)
    for st in starts:
        v = _activity(sa, st, st + length) or 0.0
        if v > best[1] + 1e-9:
            best = (st, v)
    return best[0], best[0] + length, best[1]


def _snap_sentences(sents: list[Sentence], s: int, e: int, lo: int, hi: int, cfg: HighlightConfig,
                    dur: int) -> tuple[int, int] | None:
    """Oraliqni gap chegarasiga yopishtirish. Gap kesishmasa - None (o'zgarishsiz qoldiriladi)."""
    idx = [i for i, x in enumerate(sents) if x.end_ms > s and x.start_ms < e]
    if not idx:
        return None
    a, b = idx[0], idx[-1]
    first, last = sents[a], sents[b]
    # Gapning ko'p qismi oynadan tashqarida bo'lsa - uni olmaymiz (bitta gap qolmaguncha).
    if a < b and first.start_ms < s and (s - first.start_ms) > (first.end_ms - s):
        a += 1
    if b > a and last.end_ms > e and (last.end_ms - e) > (e - last.start_ms):
        b -= 1
    span = snap(sents, a, b, cfg, min_ms=lo, max_ms=hi)
    st, en = max(0, span.start_ms), min(dur, span.end_ms)
    if en <= st:
        return None
    return st, en


def allowed_ranges(sa: SourceAnalysis) -> list[tuple[int, int]] | None:
    """Manbadan foydalanish mumkin bo'lgan oraliqlar (None - butun fayl).

    Klip manbasida segment klip oralig'idan chiqmasligi va o'chirilgan kesimlarga tushmasligi shart:
    `sa.allowed` berilgan bo'lsa - shu; aks holda `origin="clip:..."` uchun highlight oraliqlari.
    """
    dur = sa.media.duration_ms
    rng: list[tuple[int, int]] | None = None
    if sa.allowed is not None:
        rng = list(sa.allowed)
    elif sa.media.origin.startswith("clip:") and sa.highlights:
        rng = [(h.start_ms, h.end_ms) for h in sa.highlights]
    if rng is None:
        return None
    out = sorted((max(0, a), min(dur, b)) for a, b in rng if min(dur, b) > max(0, a))
    merged: list[tuple[int, int]] = []
    for a, b in out:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def _clamp(sa: SourceAnalysis, a: int, b: int) -> tuple[int, int] | None:
    """[a, b) ni ruxsat etilgan oraliqqa qisish (eng katta kesishma; teng bo'lsa - eng erta)."""
    rng = allowed_ranges(sa)
    if rng is None:
        return (a, b) if b > a else None
    best: tuple[int, int] | None = None
    for x, y in rng:
        lo, hi = max(a, x), min(b, y)
        if hi > lo and (best is None or hi - lo > best[1] - best[0]):
            best = (lo, hi)
    return best


def _clamp_cand(ctx: _Ctx, c: _Cand) -> _Cand | None:
    r = _clamp(ctx.sources[c.src], c.start, c.end)
    if r is None:
        return None
    return c if r == (c.start, c.end) else replace(c, start=r[0], end=r[1])


def _fit(ctx: _Ctx, c: _Cand, length: int) -> _Cand | None:
    """Nomzodni `length` dan oshmaydigan qilib qisqartirish (nutqda - gap bo'yicha)."""
    sa = ctx.sources[c.src]
    tpl = ctx.tpl
    if c.dur <= length:
        return c
    if tpl.respect_sentences and sa.sentences:
        r = _snap_sentences(sa.sentences, c.start, c.start + length, min(tpl.min_shot_ms, length), length,
                            ctx.hl, sa.media.duration_ms)
        if r is not None:
            if r[1] - r[0] > length + 300:
                return None
            return _clamp_cand(ctx, replace(c, start=r[0], end=r[1]))
    st, en, _ = _best_window(sa, c.start, c.end, length)
    return replace(c, start=st, end=en)


def _merge_short_shots(sa: SourceAnalysis, min_ms: int) -> list[tuple[int, int, float]]:
    """Qisqa shotlarni keyingi (bo'lmasa oldingi) qo'shnisiga qo'shish; qo'shnisiz qisqasi tashlanadi."""
    shots = sorted(sa.shots, key=lambda x: (x.start_ms, x.end_ms))
    if not shots:
        return [(0, sa.media.duration_ms, 0.5)]
    out: list[tuple[int, int, float]] = []
    pend: tuple[int, int, float] | None = None
    for sh in shots:
        a, b, sc = sh.start_ms, min(sh.end_ms, sa.media.duration_ms), sh.score
        if b <= a:
            continue
        if pend is not None and abs(pend[1] - a) <= 50:
            w0, w1 = pend[1] - pend[0], b - a
            a, sc = pend[0], (pend[2] * w0 + sc * w1) / (w0 + w1)
        pend = None
        if b - a < min_ms:
            pend = (a, b, sc)
            continue
        out.append((a, b, sc))
    if pend is not None and out and abs(out[-1][1] - pend[0]) <= 50:
        a, b, sc = out[-1]
        w0, w1 = b - a, pend[1] - pend[0]
        out[-1] = (a, pend[1], (sc * w0 + pend[2] * w1) / (w0 + w1))
    return out


# --- 1. nomzodlar ----------------------------------------------------------------------------


def _scene_cands(ctx: _Ctx, si: int) -> list[_Cand]:
    sa, tpl = ctx.sources[si], ctx.tpl
    out: list[_Cand] = []
    for k, (a, b, sc) in enumerate(_merge_short_shots(sa, tpl.min_shot_ms)):
        if b - a <= tpl.max_shot_ms:
            out.append(_Cand(si, a, b, round(sc, 4), f"sahna: bali {sc:.2f}", ("shot", si, k)))
            continue
        L = tpl.max_shot_ms
        ws, we, act = _best_window(sa, a, b, L)
        score = sc if act is None else 0.6 * sc + 0.4 * act
        why = "eng yuqori energiya va keskinlik oynasi" if act is not None else "sahna boshi"
        out.append(_Cand(si, ws, we, round(score, 4), f"{why} (sahna bali {sc:.2f})", ("shot", si, k)))
        # Qo'shimcha (ikkilamchi) oynalar: material yetmasa ishlatiladi.
        t = a
        while t + L <= b:
            if t + L <= ws or t >= we:
                act2 = _activity(sa, t, t + L)
                s2 = sc if act2 is None else 0.6 * sc + 0.4 * act2
                out.append(_Cand(si, t, t + L, round(0.9 * s2, 4), f"sahnaning davomi (bali {sc:.2f})",
                                 ("shot", si, k), primary=False))
            t += L
    return out


def _candidates(ctx: _Ctx, budget: int) -> list[_Cand]:
    tpl = ctx.tpl
    cands: list[_Cand] = []
    for si, sa in enumerate(ctx.sources):
        dur = sa.media.duration_ms
        mode = tpl.selection
        if mode == "highlight":
            hs = sorted(sa.highlights, key=lambda h: (h.start_ms, h.end_ms))
            if hs:
                for k, h in enumerate(hs):
                    a, b = max(0, h.start_ms), min(dur, h.end_ms)
                    if b - a < 300:
                        continue
                    why = f"highlight: {h.title}" if h.title else f"highlight (bali {h.score:.2f})"
                    c = _Cand(si, a, b, round(float(h.score), 4), why, ("hl", si, k), title=h.title)
                    if c.dur > tpl.max_shot_ms:
                        # Hook highlight boshida: oxiridan qisqartiriladi.
                        c = replace(c, end=a + tpl.max_shot_ms)
                    cands.append(c)
                continue
            ctx.notes.append(f"'{ctx.name(si)}' manbasida highlight yo'q - sahnalar bo'yicha tanlandi")
            mode = "scenes"
        if mode == "full":
            c = _Cand(si, 0, dur, round(1.0 - si * 1e-3, 4), "to'liq manba", ("full", si))
            if c.dur > budget:
                ws, we, _ = _best_window(sa, 0, dur, budget)
                c = replace(c, start=ws, end=we, reason="to'liq manba (maqsad davomiylikka qisqartirildi)")
            cands.append(c)
            continue
        cands.extend(_scene_cands(ctx, si))

    # Nutqli manbada gap chegaralariga yopishtirish.
    if tpl.respect_sentences:
        snapped: list[_Cand] = []
        for c in cands:
            sa = ctx.sources[c.src]
            if not sa.sentences:
                snapped.append(c)
                continue
            hi = max(tpl.max_shot_ms, tpl.min_shot_ms)
            r = _snap_sentences(sa.sentences, c.start, c.end, min(tpl.min_shot_ms, c.dur), hi, ctx.hl,
                                sa.media.duration_ms)
            if r is not None and r != (c.start, c.end):
                c = replace(c, start=r[0], end=r[1], reason=c.reason + ", gap chegarasiga moslandi")
            snapped.append(c)
        cands = snapped
    # Klip manbalari: oraliqdan va o'chirilgan kesimlardan tashqariga chiqmaslik.
    cands = [x for x in (_clamp_cand(ctx, c) for c in cands) if x is not None]

    # Bir manbada deyarli bir xil oraliqlar - yuqori balli qoladi.
    cands.sort(key=lambda c: (-c.score, c.src, c.start, c.end))
    uniq: list[_Cand] = []
    for c in cands:
        if c.dur <= 0:
            continue
        dup = False
        for u in uniq:
            if u.src == c.src:
                ov = max(0, min(u.end, c.end) - max(u.start, c.start))
                if ov > 0.5 * min(u.dur, c.dur):
                    dup = True
                    break
        if not dup:
            uniq.append(c)
    return uniq


# --- 2. tanlash va tartib --------------------------------------------------------------------


def _select(ctx: _Ctx, cands: list[_Cand], budget: int, tr_ms: int) -> list[_Cand]:
    tpl = ctx.tpl
    tol = max(500, tpl.min_shot_ms // 2)
    selected: list[_Cand] = []
    total = 0
    counts: dict[int, int] = {}

    def overlaps(c: _Cand) -> bool:
        return any(s.src == c.src and min(s.end, c.end) - max(s.start, c.start) > OVERLAP_TOL_MS
                   for s in selected)

    def run_pass(primary: bool | None, limit: int | None) -> None:
        nonlocal total
        for c in cands:
            if total >= budget - tol:
                return
            if primary is not None and c.primary != primary:
                continue
            if any(s is c for s in selected) or overlaps(c):
                continue
            if limit is not None and counts.get(c.src, 0) >= limit:
                continue
            lead = tr_ms if selected else 0
            add = c.dur - lead
            if add > budget - total + tol:
                want = budget - total + lead
                if want < min(tpl.min_shot_ms, c.dur):
                    continue
                fitted = _fit(ctx, c, want)
                if fitted is None or fitted.dur - lead > budget - total + tol:
                    continue
                if fitted is not c:
                    fitted = replace(fitted, reason=fitted.reason + ", davomiylikka moslab qisqartirildi")
                c = fitted
                add = c.dur - lead
            if c.dur < min(tpl.min_shot_ms, 1000):
                continue
            selected.append(c)
            counts[c.src] = counts.get(c.src, 0) + 1
            total += add

    run_pass(True, tpl.max_per_source)
    run_pass(False, tpl.max_per_source)
    if total < 0.8 * budget and tpl.max_per_source is not None:
        before = len(selected)
        run_pass(None, None)
        if len(selected) > before:
            ctx.notes.append("manbalar kam - bitta manbadan olinadigan bo'laklar cheklovi yumshatildi")
    return selected


def _order(ctx: _Ctx, sel: list[_Cand]) -> list[_Cand]:
    tpl = ctx.tpl
    if tpl.order == "berilgan":
        return sorted(sel, key=lambda c: (c.src, c.start))
    if tpl.order == "xronologik":
        rec = [sa.recorded_at for sa in ctx.sources]
        if not any(rec):
            ctx.notes.append("yozilgan vaqt ma'lum emas - manbalar berilgan tartibda")

        def key(c: _Cand) -> tuple[Any, ...]:
            r = rec[c.src]
            return (0, r, c.src, c.start) if r else (1, "", c.src, c.start)

        return sorted(sel, key=key)
    # ball: eng kuchli birinchi (hook), keyin xilma-xillik.
    rest = sorted(sel, key=lambda c: (-c.score, c.src, c.start))
    out: list[_Cand] = []
    while rest:
        pick = 0
        for j, c in enumerate(rest):
            run3 = len(out) >= 2 and out[-1].src == out[-2].src == c.src
            same = bool(out) and out[-1].key == c.key
            if not run3 and not same:
                pick = j
                break
        out.append(rest.pop(pick))
    return out


def _extend(ctx: _Ctx, items: list[_Cand], idx: int, need: int, front_first: bool, what: str) -> list[_Cand]:
    """Karta ostida qoladigan qism uchun elementni uzaytirish (boshqa tanlangan oraliqlarga kirmasdan)."""
    c = items[idx]
    dur = ctx.sources[c.src].media.duration_ms
    others = [o for j, o in enumerate(items) if j != idx and o.src == c.src]
    seg_lo, seg_hi = 0, dur
    rng = allowed_ranges(ctx.sources[c.src])
    if rng is not None:
        seg = next(((x, y) for x, y in rng if x <= c.start and c.end <= y), (c.start, c.end))
        seg_lo, seg_hi = seg
    lo_free = max([seg_lo, *(o.end for o in others if o.end <= c.start + OVERLAP_TOL_MS)])
    hi_free = min([seg_hi, *(o.start for o in others if o.start >= c.end - OVERLAP_TOL_MS)])
    room_front = max(0, c.start - lo_free)
    room_back = max(0, hi_free - c.end)
    if front_first:
        d1 = min(need, room_front)
        d2 = min(need - d1, room_back)
    else:
        d2 = min(need, room_back)
        d1 = min(need - d2, room_front)
    if d1 + d2 < need:
        ctx.notes.append(f"{what} kartasi uchun manbada joy yetmadi - tanlangan lahzaning bir qismi karta ostida qoladi")
    # Ovoz karta ostida ham eshitiladi: yangi chegara so'z o'rtasiga tushmasin.
    sents = ctx.sources[c.src].sentences
    start, end = c.start - d1, c.end + d2
    if d1:
        w = _word_at(sents, start)
        if w is not None:
            start = w.start_ms if w.start_ms >= lo_free else w.end_ms
    if d2:
        w = _word_at(sents, end)
        if w is not None:
            end = w.end_ms if w.end_ms <= hi_free else w.start_ms
    items = list(items)
    items[idx] = replace(c, start=min(start, c.start), end=max(end, c.end))
    return items


def _word_at(sents: list[Sentence], t: int) -> Word | None:
    """`t` nuqtasi ichiga tushgan so'z (chegarada emas)."""
    for s in sents:
        if s.start_ms < t < s.end_ms:
            for w in s.words:
                if w.start_ms < t < w.end_ms:
                    return w
    return None


# --- 3. matn ---------------------------------------------------------------------------------


_PH_RE = re.compile(r"\{\s*(sarlavha|shou|cta)\s*(?::([^{}]*))?\}")


def fill_placeholders(text: str, values: dict[str, str | None]) -> str | None:
    """`{sarlavha}`, `{shou}`, `{cta}` (ixtiyoriy standart qiymat: `{cta:Obuna bo'ling}`) o'rniga qo'yish.

    Natija bo'sh bo'lsa None (matn qatlami qo'yilmaydi).
    """
    def sub(m: re.Match[str]) -> str:
        v = values.get(m.group(1))
        if v and v.strip():
            return v.strip()
        return (m.group(2) or "").strip()

    out = re.sub(r"\s+", " ", _PH_RE.sub(sub, text)).strip()
    return out or None


def _text_item(tid: str, card: TextCard, text: str, start: int, end: int) -> TextItem:
    return TextItem(
        id=tid, start_ms=start, end_ms=end, text=text, kind=card.kind,
        background=card.background if card.kind == "card" else None,
        position=card.position, animation=card.animation,
    )


# --- 4. effektlar ----------------------------------------------------------------------------


def _place_fx(rule: FxRule, video: list[VideoItem], starts: list[int], sources_by_media: dict[str, SourceAnalysis],
              blocked: list[tuple[int, int]]) -> None:
    n = len(video)
    points: list[tuple[int, int, int | None]] = []  # (element, at_ms, dur_ms)
    if rule.trigger == "on_start":
        points.append((0, 0, None))
    elif rule.trigger == "on_end":
        points.append((n - 1, max(0, video[-1].out_duration_ms - ON_END_LEAD_MS), None))
    elif rule.trigger == "on_cut":
        points.extend((i, 0, None) for i in range(1, n))
    elif rule.trigger == "every_n":
        step = rule.every_n or 1
        points.extend((i, 0, None) for i in range(step - 1, n, step))
    else:
        for i, it in enumerate(video):
            sa = sources_by_media[it.media]
            marks = sa.emphasis_ms if rule.trigger == "on_emphasis" else sa.speaker_changes_ms
            for t in sorted(marks):
                if it.src_in_ms <= t < it.src_out_ms:
                    at = round((t - it.src_in_ms) / it.speed)
                    rest = it.out_duration_ms - at
                    if rest >= 500:
                        points.append((i, at, min(POINT_FX_MS, rest)))
    points.sort(key=lambda p: (starts[p[0]] + p[1], p[0]))
    count = 0
    last_g: int | None = None
    for i, at, d in points:
        if rule.max_count is not None and count >= rule.max_count:
            break
        g = starts[i] + at
        if any(a <= g < b for a, b in blocked):
            continue
        if last_g is not None and g - last_g < rule.min_gap_ms:
            continue
        it = video[i]
        if any(f.plugin == rule.plugin and abs(f.at_ms - at) < 300 for f in it.fx):
            continue
        it.fx.append(FxRef(plugin=rule.plugin, at_ms=at, dur_ms=d, params=dict(rule.params), source="shablon"))
        count += 1
        last_g = g


# --- 5. musiqa -------------------------------------------------------------------------------


def _probe_music(path: str) -> tuple[int, str | None]:
    """Musiqa faylining davomiyligi (ms) va xeshi. Testlarda almashtiriladi."""
    from lahza_engine.media.probe import MediaError, fast_hash
    from lahza_engine.montage.analyze import probe_media

    try:
        info = probe_media(path)
    except (MediaError, OSError, ValueError) as e:
        raise PlanError(f"musiqa faylini o'qib bo'lmadi: {e}") from None
    if not info.has_audio:
        raise PlanError("musiqa faylida ovoz yo'q")
    return info.duration_ms, fast_hash(path)


def _check_override_plugin(plugin: str, kind: str, what: str) -> None:
    try:
        from lahza_engine.fx import registry
    except ImportError:
        return  # reestr hali yo'q - tekshiruv o'tkaziladi
    try:
        m = registry.get_plugin(plugin)
    except KeyError:
        raise PlanError(f"{what}: '{plugin}' plagini o'rnatilmagan") from None
    k = getattr(m, "kind", kind)
    if k != kind:
        raise PlanError(f"{what}: '{plugin}' plagini {kind} emas")


# --- asosiy funksiya -------------------------------------------------------------------------


def _card_ms(card: TextCard | None) -> int:
    return card.dur_ms if card is not None and card.kind == "card" else 0


def plan_montage(
    template: Template,
    sources: Sequence[SourceAnalysis],
    overrides: MontageOverrides | None = None,
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
) -> MontageTimeline:
    """Shablon va manba tahlillaridan montaj rejasi. Xato bo'lsa o'zbekcha `PlanError`."""
    ov = overrides or MontageOverrides()
    tpl = template
    hl = settings.highlight if settings is not None else HighlightConfig()
    fade_ms = settings.render.fade_ms if settings is not None else 150
    srcs = list(sources)
    if not srcs:
        raise PlanError("montaj uchun video tanlanmagan")
    ids = [s.media.id for s in srcs]
    if len(set(ids)) != len(ids):
        raise PlanError("manbalar orasida takroriy media id bor")
    if MUSIC_ID in ids:
        raise PlanError(f"'{MUSIC_ID}' media id musiqa uchun band")
    for s in srcs:
        if s.media.duration_ms <= 0:
            raise PlanError(f"'{s.media.id}' manbasining davomiyligi noma'lum")

    target = ov.target_duration_ms if ov.target_duration_ms is not None else tpl.target_duration_ms
    if not 5_000 <= target <= 600_000:
        raise PlanError("davomiylik 5 soniyadan 10 daqiqagacha bo'lishi kerak")
    profile_format = get_profile(ov.target_platform).recommended_format
    aspect = ov.aspect or (profile_format.aspect if profile_format else tpl.aspect)
    if aspect not in ASPECT_SIZE:
        raise PlanError(f"noma'lum format '{aspect}' (9:16, 1:1 yoki 16:9)")

    # O'tish.
    tr_tpl: TransitionRef | None = tpl.transition
    if ov.transition:
        if ov.transition != CUT_PLUGIN:
            _check_override_plugin(ov.transition, "transition", "o'tish")
        tr_tpl = TransitionRef(plugin=ov.transition, dur_ms=tpl.transition.dur_ms if tpl.transition and
                               tpl.transition.plugin != CUT_PLUGIN else 400)
    if tr_tpl is not None and (tr_tpl.plugin == CUT_PLUGIN or tr_tpl.dur_ms <= 0):
        tr_tpl = None
    tr_ms = tr_tpl.dur_ms if tr_tpl else 0

    ctx = _Ctx(tpl=tpl, sources=srcs, hl=hl)
    intro_ms, outro_ms = _card_ms(tpl.intro), _card_ms(tpl.outro)
    budget = target - intro_ms - outro_ms
    if budget < tpl.min_shot_ms:
        raise PlanError("intro/outro kartalaridan keyin video uchun vaqt qolmadi - davomiylikni oshiring")

    # 1-2. Nomzodlar, tanlash, tartib.
    cands = _candidates(ctx, budget)
    if not cands:
        raise PlanError("tanlangan videolarda yaroqli bo'lak topilmadi (juda qisqa yoki bo'sh)")
    sel = _select(ctx, cands, budget, tr_ms)
    if not sel:
        raise PlanError("maqsad davomiylikka mos bo'lak topilmadi - davomiylikni oshiring yoki boshqa video tanlang")
    items = _order(ctx, sel)
    if intro_ms:
        items = _extend(ctx, items, 0, intro_ms, True, "intro")
    if outro_ms:
        items = _extend(ctx, items, len(items) - 1, outro_ms, False, "outro")

    # 3. Video elementlar.
    mute_all = tpl.mute_sources
    video: list[VideoItem] = []
    for i, c in enumerate(items):
        sa = srcs[c.src]
        tr = None
        if i > 0 and tr_tpl is not None:
            d = min(tr_tpl.dur_ms, items[i - 1].dur // 2, c.dur // 2)
            if d > 0:
                tr = TransitionRef(plugin=tr_tpl.plugin, dur_ms=d, params=dict(tr_tpl.params))
        if i == 0:
            role = "hook" if (tpl.selection == "highlight" or tpl.order == "ball") else "asosiy"
        elif i == len(items) - 1 and tpl.outro is not None:
            role = "cta"
        else:
            role = "asosiy"
        video.append(VideoItem(
            id=f"v{i + 1:02d}", media=sa.media.id, src_in_ms=c.start, src_out_ms=c.end,
            reframe=tpl.reframe, mute=mute_all or not sa.media.has_audio, transition_in=tr,
            role=role, reason=c.reason,
        ))

    starts: list[int] = []
    t = 0
    for i, it in enumerate(video):
        if i > 0 and it.transition_in is not None:
            t -= min(it.transition_in.dur_ms, it.out_duration_ms, video[i - 1].out_duration_ms)
        starts.append(t)
        t += it.out_duration_ms
    end_ms = t

    # Karta bilan yopilgan oraliqlar (effekt va subtitr qo'yilmaydi).
    blocked: list[tuple[int, int]] = []
    if intro_ms:
        blocked.append((0, intro_ms))
    if outro_ms:
        blocked.append((max(0, end_ms - outro_ms), end_ms))

    # 4. Effektlar.
    by_media = {s.media.id: s for s in srcs}
    for rule in tpl.fx:
        _place_fx(rule, video, starts, by_media, blocked)
    for it in video:
        it.fx.sort(key=lambda f: (f.at_ms, f.plugin))

    color_id = tpl.color if ov.color is None else (ov.color.strip() or None)
    if color_id in ("none", "yo'q"):
        color_id = None
    if ov.color and color_id:
        _check_override_plugin(color_id, "color", "rang")
    color = FxRef(plugin=color_id, at_ms=0, source="shablon") if color_id else None

    # 5. Matn qatlamlari.
    first_title = next((c.title for c in sorted(items, key=lambda c: -c.score) if c.title), None)
    values = {"sarlavha": ov.title or first_title, "shou": ov.shou, "cta": ov.cta}
    texts: list[TextItem] = []
    first_end = starts[0] + video[0].out_duration_ms
    for tid, card in (("intro", tpl.intro), ("hook", tpl.hook_text), ("outro", tpl.outro)):
        if card is None:
            continue
        txt = fill_placeholders(card.text, values)
        if txt is None:
            ctx.notes.append(f"{tid} matni bo'sh (o'rinbosar qiymati berilmagan) - qo'yilmadi")
            continue
        if tid == "intro":
            a, b = 0, min(card.dur_ms, end_ms)
        elif tid == "hook":
            a = intro_ms
            b = min(a + card.dur_ms, first_end)
            if b - a < 500:
                ctx.notes.append("hook matni uchun birinchi elementda joy yetmadi - qo'yilmadi")
                continue
        else:
            a, b = max(0, end_ms - card.dur_ms), end_ms
        texts.append(_text_item(tid, card, txt, a, b))

    # 6. Subtitr.
    cap_on = tpl.captions if ov.captions is None else ov.captions
    style = ov.caption_style or tpl.caption_style or StyleTemplate()
    words: list[Word] = []
    for i, it in enumerate(video):
        sa = by_media[it.media]
        lo, hi = starts[i], starts[i] + it.out_duration_ms
        for s in sa.sentences:
            if s.end_ms <= it.src_in_ms or s.start_ms >= it.src_out_ms:
                continue
            for w in s.words:
                if w.start_ms < it.src_in_ms or w.end_ms > it.src_out_ms:
                    continue
                ws = max(lo, starts[i] + round((w.start_ms - it.src_in_ms) / it.speed))
                we = min(hi, starts[i] + round((w.end_ms - it.src_in_ms) / it.speed))
                if we <= ws or any(a <= ws < b for a, b in blocked):
                    continue
                if words and ws < words[-1].end_ms:
                    if ws <= words[-1].start_ms:
                        continue
                    words[-1] = words[-1].model_copy(update={"end_ms": ws})
                words.append(Word(text=w.text, start_ms=ws, end_ms=we, conf=w.conf, speaker=w.speaker))
    if cap_on and not words:
        ctx.notes.append("subtitr yoqilgan, lekin manbalarda transkript yo'q")
    captions = Captions(enabled=bool(cap_on), style=style, words=words)

    # 7. Media, musiqa.
    media: dict[str, MediaRef] = {s.media.id: s.media for s in srcs}
    music: list[MusicItem] = []
    spec = tpl.music or MusicSpec()
    if ov.music_path:
        mdur, mhash = _probe_music(ov.music_path)
        if mdur <= 0:
            raise PlanError("musiqa faylining davomiyligi noma'lum")
        media[MUSIC_ID] = MediaRef(id=MUSIC_ID, path=str(ov.music_path), hash=mhash, duration_ms=mdur,
                                   width=0, height=0, fps=0.0, has_audio=True, origin="file")
        music.append(MusicItem(media=MUSIC_ID, src_in_ms=0, start_ms=0, end_ms=None, gain_db=spec.gain_db,
                               duck=spec.duck, fade_in_ms=spec.fade_in_ms, fade_out_ms=spec.fade_out_ms))
        if mdur < end_ms:
            ctx.notes.append("musiqa montajdan qisqa - oxirida musiqasiz qism bo'ladi")
    elif tpl.music is not None and tpl.music.required:
        ctx.notes.append("ogohlantirish: bu shablon musiqa bilan ishlashga mo'ljallangan, lekin musiqa tanlanmagan")
    if mute_all and not music:
        ctx.notes.append("ogohlantirish: manba ovozi o'chirilgan va musiqa yo'q - montaj ovozsiz bo'ladi")

    # 8. Brend va audio.
    brand = Brand()
    if ov.logo_path:
        brand = Brand(logo_path=ov.logo_path)
    elif tpl.logo:
        ctx.notes.append("shablon logo kutadi, lekin logo fayli berilmagan")
    audio = AudioMix(source_gain_db=tpl.source_gain_db, loudnorm_lufs=tpl.loudnorm_lufs, fade_ms=fade_ms)

    if end_ms < 0.5 * target:
        ctx.notes.append(f"material yetarli emas: montaj {end_ms / 1000:.1f} s (maqsad {target / 1000:.0f} s)")

    created = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0).isoformat()
    prov = Provenance(template_id=tpl.id, template_version=tpl.version, engine=__version__,
                      created_at=created, planner="qoida", notes=ctx.notes)
    try:
        return MontageTimeline(
            target_platform=ov.target_platform,
            format=Format.for_aspect(aspect, fps=profile_format.fps if profile_format else tpl.fps),  # type: ignore[arg-type]
            media=media, video=video, text=texts, music=music, captions=captions, brand=brand,
            audio=audio, color=color, provenance=prov,
        )
    except ValueError as e:
        raise PlanError(f"montaj rejasi yaroqsiz: {e}") from None
