"""M3-RF-2/4: split avtomatik tanlovi, layout ushlab turish, kalit kadrlar jadvali bilan almashinuv."""

from lahza_engine.config import ReframeConfig
from lahza_engine.reframe.faces import Box
from lahza_engine.reframe.planner import (
    CropKey,
    Keyframe,
    Observation,
    _hold_layouts,
    crop_rect,
    key_at,
    keyframes_from_layouts,
    layouts_from_keyframes,
    plan,
)
from lahza_engine.types import Layout

F, S, B = Layout.FOCUS, Layout.SPLIT, Layout.FIT_BLUR


def _face(cx: float) -> Box:
    return Box(cx - 0.05, 0.3, 0.1, 0.15)


def test_hold_absorbs_short_blips() -> None:
    raw = [(t * 200, B if 20 <= t < 23 else F) for t in range(50)]
    assert _hold_layouts(raw, 2_000, 10_000) == [(0, F)]
    raw = [(t * 200, F if t < 25 else B) for t in range(50)]
    assert _hold_layouts(raw, 2_000, 10_000) == [(0, F), (5_000, B)]
    # birinchi qisqa bo'lak keyingisiga qo'shiladi
    raw = [(t * 200, B if t < 3 else F) for t in range(50)]
    assert _hold_layouts(raw, 2_000, 10_000) == [(0, F)]


def test_two_faces_fast_speaker_switching_gives_split() -> None:
    # Diarizatsiya: har 1.2 s spiker almashadi -> tez almashinuv.
    obs = [Observation(t * 200, [_face(0.25), _face(0.75)], 0, speaker="AB"[(t // 6) % 2])
           for t in range(100)]
    segs = plan(obs, 20_000, ReframeConfig())
    assert any(s.layout is S for s in segs)
    split = next(s for s in segs if s.layout is S)
    assert abs(split.keys[0].cx - 0.25) < 0.01 and abs(split.keys_b[0].cx - 0.75) < 0.01
    assert all(s.end_ms - s.start_ms >= ReframeConfig().min_layout_hold_ms for s in segs[:-1])


def test_single_speaker_two_faces_stays_focus() -> None:
    obs = [Observation(t * 200, [_face(0.25), _face(0.75)], 0, speaker="A") for t in range(100)]
    assert [s.layout for s in plan(obs, 20_000, ReframeConfig())] == [F]


def test_overlap_speech_gives_split_one_face_does_not() -> None:
    obs = [Observation(t * 200, [_face(0.3), _face(0.7)], 0, overlap_speech=20 <= t < 60)
           for t in range(100)]
    lays = [s.layout for s in plan(obs, 20_000, ReframeConfig())]
    assert lays == [F, S, F]
    obs1 = [Observation(t * 200, [_face(0.3)], 0, overlap_speech=True) for t in range(50)]
    assert [s.layout for s in plan(obs1, 10_000, ReframeConfig())] == [F]


def test_fit_blur_when_faces_gone_long() -> None:
    obs = [Observation(t * 200, [_face(0.4)] if t < 25 else [], 0 if t < 25 else None)
           for t in range(50)]
    assert [s.layout for s in plan(obs, 10_000, ReframeConfig())] == [F, B]


def test_shot_cut_restarts_path_and_is_not_a_switch() -> None:
    obs = []
    for t in range(100):
        cx = 0.3 if (t // 5) % 2 == 0 else 0.7
        obs.append(Observation(t * 200, [_face(cx), _face(0.95)], 0, shot_cut=t % 5 == 0 and t > 0))
    segs = plan(obs, 20_000, ReframeConfig())
    assert [s.layout for s in segs] == [F]  # kamera kesimlari spiker almashuvi emas
    cuts = [k for k in segs[0].keys if k.cut]
    assert len(cuts) >= 19


def test_crop_rect_cy_and_zoom() -> None:
    x, y, w, h = crop_rect(0.5, 1920, 1080, zoom=2.0, cy=0.2)
    assert (w, h) == (302, 540)
    assert y == 0  # 0.2*1080-270 < 0 -> kadr ichida
    _, y2, _, _ = crop_rect(0.5, 1920, 1080, zoom=2.0, cy=0.5)
    assert y2 == 270
    _, y3, _, _ = crop_rect(0.5, 1920, 1080, zoom=0.5)  # zoom < 1 -> 1
    assert y3 == 0


def test_layouts_from_manual_keyframes() -> None:
    kfs = [
        Keyframe(500, Layout.MANUAL, 0.3, 0.5, 1.0),
        Keyframe(2_000, Layout.MANUAL, 0.6, 0.5, 1.0),
        Keyframe(4_000, Layout.MANUAL, 0.6, 0.4, 1.5),
        Keyframe(6_000, S, 0.25),
        Keyframe(6_000, S, 0.8, lane="b"),
        Keyframe(9_000, B),
    ]
    segs = layouts_from_keyframes(kfs, 10_000)
    assert [(s.start_ms, s.end_ms, s.layout) for s in segs] == [
        (0, 4_000, Layout.MANUAL), (4_000, 6_000, Layout.MANUAL), (6_000, 9_000, S),
        (9_000, 10_000, B)]
    k0 = segs[0].keys
    assert k0[0].t_ms == 500 and k0[0].cut and not k0[1].cut  # qo'lda: silliq pan
    assert segs[1].keys[0].zoom == 1.5 and segs[1].keys[0].cy == 0.4
    assert segs[2].keys[0].cx == 0.25 and segs[2].keys_b[0].cx == 0.8
    assert segs[3].keys == []
    assert layouts_from_keyframes([], 1_000)[0].layout is B


def test_auto_plan_keyframe_roundtrip() -> None:
    obs = [Observation(t * 200, [_face(0.25), _face(0.75)], 0 if t < 25 else 1) for t in range(50)]
    segs = plan(obs, 10_000, ReframeConfig())
    rows = keyframes_from_layouts(segs)
    assert len({(r.lane, r.t_ms) for r in rows}) == len(rows)
    back = layouts_from_keyframes(rows, 10_000)
    assert [s.layout for s in back] == [s.layout for s in segs]
    # avto rejadagi keskin kesim (0.25 -> 0.75, 200 ms ichida) qayta tiklanadi
    assert any(k.cut and abs(k.cx - 0.75) < 0.01 for s in back for k in s.keys[1:])


def test_key_at_interpolates_but_not_across_cut() -> None:
    keys = [CropKey(0, 0.2, cut=True), CropKey(1_000, 0.4), CropKey(2_000, 0.9, cut=True)]
    assert abs(key_at(keys, 500).cx - 0.3) < 1e-9
    assert key_at(keys, 1_500).cx == 0.4
    assert key_at(keys, 2_500).cx == 0.9
    assert key_at([], 10).cx == 0.5
