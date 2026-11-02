"""M3-RF-1: ASD + diarizatsiya birlashmasi - sintetik diarizatsiya va soxta ASD ballari bilan."""

import random

from lahza_engine.config import ReframeConfig
from lahza_engine.diarize.assign import Turn
from lahza_engine.reframe.active_speaker import (
    annotate_speech,
    resolve_active_speakers,
    select_active,
    speaker_at,
)
from lahza_engine.reframe.faces import Box
from lahza_engine.reframe.planner import Observation, plan
from lahza_engine.reframe.speaker_map import AsdSample, active_track
from lahza_engine.types import Layout

CFG = ReframeConfig()
STEP = 200  # 5 fps
LEFT, RIGHT = 7, 9  # treker ID lari (chap va o'ng yuz)


def _face(cx: float, size: float = 0.1) -> Box:
    return Box(cx - size / 2, 0.3, size, size * 1.5)


def _turns() -> list[Turn]:
    # S1 (chapdagi) 0-6 s, S2 (o'ngdagi) 6-12 s, S1 12-18 s
    return [Turn(0, 6_000, "S1"), Turn(6_000, 12_000, "S2"), Turn(12_000, 18_000, "S1")]


def _obs(asd_fn, dur_ms: int = 18_000, swap_order: bool = False) -> list[Observation]:
    out = []
    for t in range(0, dur_ms, STEP):
        faces, ids = [_face(0.3), _face(0.7)], [LEFT, RIGHT]
        if swap_order and (t // STEP) % 2:
            faces, ids = faces[::-1], ids[::-1]  # detektor tartibi o'zgaradi - ID barqaror
        out.append(Observation(t, faces, track_ids=ids, asd_scores=asd_fn(t)))
    return out


def _truth(t: int) -> int:
    return RIGHT if 6_000 <= t < 12_000 else LEFT


def _clean_asd(t: int) -> dict[int, float]:
    spk = _truth(t)
    return {spk: 0.9, (LEFT if spk == RIGHT else RIGHT): 0.1}


def _chosen_ids(obs: list[Observation]) -> list[int | None]:
    return [o.track_ids[o.active_index] if o.active_index is not None else None for o in obs]


def _switches(ids: list[int | None]) -> int:
    return sum(1 for a, b in zip(ids, ids[1:], strict=False) if a != b)


def test_speaker_at_and_annotate() -> None:
    turns = _turns()
    assert speaker_at(turns, 0) == "S1"
    assert speaker_at(turns, 6_000) == "S2"
    assert speaker_at(turns, 18_000) is None
    obs = annotate_speech([Observation(100), Observation(7_000), Observation(8_000)], turns,
                          overlaps=[(7_500, 8_500)])
    assert [o.speaker for o in obs] == ["S1", "S2", "S2"]
    assert [o.overlap_speech for o in obs] == [False, False, True]


def test_selects_correct_speaker_with_diarization_and_asd() -> None:
    res = resolve_active_speakers(_obs(_clean_asd, swap_order=True), CFG, turns=_turns())
    ids = _chosen_ids(res)
    correct = sum(1 for o, tid in zip(res, ids, strict=True) if tid == _truth(o.t_ms))
    assert correct / len(res) >= 0.9  # almashuvdagi tasdiq kechikishi (400 ms) - xato hisob
    assert _switches(ids) == 2
    assert not any(o.wide for o in res)
    # almashuv tasdiq oynasidan keyin sodir bo'ladi, tezroq emas
    first_right = next(o.t_ms for o, tid in zip(res, ids, strict=True) if tid == RIGHT)
    assert 6_000 + CFG.speaker_switch_confirm_ms <= first_right <= 6_000 + 1_000


def test_diarization_breaks_ambiguous_asd() -> None:
    """ASD ikkala yuzga deyarli teng ball bersa - diarizatsiya (o'rganilgan xarita) hal qiladi."""

    def asd(t: int) -> dict[int, float]:
        if 3_000 <= t < 4_000 or 9_000 <= t < 10_000:
            return {LEFT: 0.55, RIGHT: 0.55}
        return _clean_asd(t)

    res = resolve_active_speakers(_obs(asd), CFG, turns=_turns())
    for o, tid in zip(res, _chosen_ids(res), strict=True):
        if 3_000 <= o.t_ms < 4_000:
            assert tid == LEFT
        if 9_000 <= o.t_ms < 10_000:
            assert tid == RIGHT


def test_no_jitter_on_noisy_asd() -> None:
    rnd = random.Random(7)

    def noisy(t: int) -> dict[int, float]:
        spk = _truth(t)
        other = LEFT if spk == RIGHT else RIGHT
        # har 5-kuzatuvda bitta kadrlik soxta "o'girilish" + shovqin
        flip = (t // STEP) % 5 == 3
        hi, lo = 0.75 + rnd.uniform(-0.1, 0.1), 0.2 + rnd.uniform(-0.1, 0.1)
        return {spk: lo, other: hi} if flip else {spk: hi, other: lo}

    obs = _obs(noisy)
    # diarizatsiyasiz ham (faqat ASD) - bitta kadrlik sakrashlar tasdiqdan o'tmaydi
    ids = _chosen_ids(resolve_active_speakers(obs, CFG))
    assert _switches(ids) == 2
    ids_d = _chosen_ids(resolve_active_speakers(obs, CFG, turns=_turns()))
    assert _switches(ids_d) == 2


def test_min_hold_blocks_rapid_switching() -> None:
    """Spikerlar har 600 ms almashsa ham kamera min hold (1.5 s) dan tez sakramaydi."""
    turns = [Turn(s, s + 600, "S1" if (s // 600) % 2 == 0 else "S2") for s in range(0, 12_000, 600)]

    def asd(t: int) -> dict[int, float]:
        left = (t // 600) % 2 == 0
        return {LEFT: 0.9 if left else 0.1, RIGHT: 0.1 if left else 0.9}

    res = resolve_active_speakers(_obs(asd, 12_000), CFG, turns=turns)
    ids = _chosen_ids(res)
    switch_t = [res[i + 1].t_ms for i in range(len(ids) - 1) if ids[i] != ids[i + 1]]
    gaps = [b - a for a, b in zip(switch_t, switch_t[1:], strict=False)]
    assert all(g >= CFG.speaker_min_hold_ms for g in gaps)


def test_switch_immediately_when_current_face_leaves() -> None:
    obs = _obs(_clean_asd, 4_000)
    for o in obs:
        if o.t_ms >= 2_000:  # chap yuz kadrdan chiqdi
            o.faces, o.track_ids = [_face(0.7)], [RIGHT]
            o.asd_scores = {RIGHT: 0.2}
    res = resolve_active_speakers(obs, CFG, turns=_turns())
    after = [tid for o, tid in zip(res, _chosen_ids(res), strict=True) if o.t_ms >= 2_000]
    assert set(after) == {RIGHT}


def test_low_confidence_goes_wide_after_delay() -> None:
    def asd(t: int) -> dict[int, float]:
        if 4_000 <= t < 8_000:  # nutq bor (diarizatsiya), lekin hech kim gapirmayotganga o'xshaydi
            return {LEFT: 0.05, RIGHT: 0.05}
        return _clean_asd(t)

    obs = _obs(asd, 12_000)
    # S3 - kadrda yo'q odam (masalan, ekran tashqarisidagi mehmon)
    turns = [Turn(0, 4_000, "S1"), Turn(4_000, 8_000, "S3"), Turn(8_000, 12_000, "S2")]
    res = resolve_active_speakers(obs, CFG, turns=turns)
    wide = [o.t_ms for o in res if o.wide]
    assert wide
    assert min(wide) >= 4_000 + CFG.low_confidence_wide_ms
    assert max(wide) < 8_000
    segs = plan(res, 12_000, CFG)
    lay_at_6s = next(s.layout for s in segs if s.start_ms <= 6_000 < s.end_ms)
    assert lay_at_6s is Layout.FIT_BLUR
    assert segs[0].layout is Layout.FOCUS


def test_silence_does_not_go_wide() -> None:
    """Nutq yo'q (diarizatsiya bo'sh, ASD past) - joriy yuz ushlanadi, keng kadrga o'tilmaydi."""
    obs = _obs(lambda t: _clean_asd(t) if t < 3_000 else {LEFT: 0.05, RIGHT: 0.05}, 8_000)
    res = resolve_active_speakers(obs, CFG, turns=[Turn(0, 3_000, "S1")])
    assert not any(o.wide for o in res)
    assert set(_chosen_ids(res)) == {LEFT}


def test_fallback_without_asd_is_largest_face_without_jitter() -> None:
    """ASD modeli yo'q: hozirgi heuristika (eng katta yuz), o'lchami yaqin yuzlar orasida sakramaydi."""
    obs = []
    for i, t in enumerate(range(0, 6_000, STEP)):
        a = 0.1 + (0.004 if i % 2 else 0.0)  # deyarli teng, navbatma-navbat kattaroq
        obs.append(Observation(t, [_face(0.3, a), _face(0.7, 0.102)]))
    res = resolve_active_speakers(obs, CFG, turns=_turns())
    assert all(o.active_index is not None for o in res)
    assert _switches([o.active_index for o in res]) == 0
    assert not any(o.wide for o in res)
    # aniq kattaroq yuz tanlanadi
    big = [Observation(0, [_face(0.3, 0.05), _face(0.7, 0.2)])]
    assert resolve_active_speakers(big, CFG)[0].active_index == 1
    d = select_active([Observation(0)], CFG)[0]
    assert d.index is None and d.source == "none"


def test_shot_cut_resets_choice() -> None:
    obs = _obs(_clean_asd, 4_000)
    for o in obs:
        if o.t_ms >= 2_000:
            o.asd_scores = {LEFT: 0.1, RIGHT: 0.9}
    obs[10].shot_cut = True  # t=2000
    res = resolve_active_speakers(obs, CFG)
    assert _chosen_ids(res)[10] == RIGHT  # kesimda tasdiq kutilmaydi


def test_plan_integration_cuts_on_speaker_change() -> None:
    res = resolve_active_speakers(_obs(_clean_asd), CFG, turns=_turns())
    segs = plan(res, 18_000, CFG)
    assert all(s.layout is Layout.FOCUS for s in segs)
    keys = [k for s in segs for k in s.keys]
    cuts = [k for k in keys if k.cut]
    assert len(cuts) == 3  # boshlanish + ikki spiker almashuvi (pan emas, keskin kesim)
    # kesimlar orasida kamera tinch (o'lik zona + One-Euro)
    for a, b in zip(keys, keys[1:], strict=False):
        if not b.cut:
            assert abs(b.cx - a.cx) < 1e-6


def test_active_track_unchanged_behaviour() -> None:
    s = AsdSample(0, "S1", {1: 0.6, 2: 0.7})
    assert active_track(s, {}) == 2
    assert active_track(s, {"S1": 1}) == 1
    assert active_track(AsdSample(0, None, {}), {}) is None
