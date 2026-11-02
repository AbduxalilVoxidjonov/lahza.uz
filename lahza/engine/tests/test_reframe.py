from lahza_engine.config import ReframeConfig
from lahza_engine.reframe.faces import Box, FaceTracker
from lahza_engine.reframe.filters import OneEuroFilter, clamp_speed
from lahza_engine.reframe.planner import Observation, crop_rect, plan
from lahza_engine.reframe.speaker_map import AsdSample, active_track, learn_speaker_to_track
from lahza_engine.types import Layout


def test_crop_rect_9x16_inside_frame() -> None:
    x, y, w, h = crop_rect(0.5, 1920, 1080)
    assert (w, h) == (606, 1080)  # 1080*9/16 = 607.5 -> juft
    assert 0 <= x <= 1920 - w and x % 2 == 0
    x2, *_ = crop_rect(0.99, 1920, 1080)
    assert x2 == 1920 - 606
    x3, *_ = crop_rect(0.0, 1920, 1080)
    assert x3 == 0


def test_one_euro_smooths_noise() -> None:
    import random

    random.seed(1)
    f = OneEuroFilter(min_cutoff=0.3, beta=0.0)
    vals = [f(0.5 + random.uniform(-0.05, 0.05), t / 5) for t in range(100)]
    assert max(vals[20:]) - min(vals[20:]) < 0.05


def test_clamp_speed() -> None:
    assert clamp_speed(0.0, 1.0, 0.2, 0.5) == 0.1


def _face(cx: float) -> Box:
    return Box(cx - 0.05, 0.3, 0.1, 0.15)


def test_plan_single_speaker_focus_with_dead_zone() -> None:
    obs = [Observation(t * 200, [_face(0.40 + (0.01 if t % 2 else 0))], 0) for t in range(50)]
    segs = plan(obs, 10_000, ReframeConfig())
    assert [s.layout for s in segs] == [Layout.FOCUS]
    xs = {round(k.cx, 3) for k in segs[0].keys}
    assert len(xs) <= 3  # o'lik zona mayda tebranishni yutadi


def test_plan_switch_is_hard_cut() -> None:
    obs = [Observation(t * 200, [_face(0.25), _face(0.75)], 0 if t < 25 else 1) for t in range(50)]
    segs = plan(obs, 10_000, ReframeConfig())
    keys = [k for s in segs for k in s.keys]
    assert any(k.cut and abs(k.cx - 0.75) < 0.01 for k in keys)


def test_plan_no_faces_fit_blur() -> None:
    segs = plan([Observation(t * 200, []) for t in range(10)], 2_000, ReframeConfig())
    assert segs[0].layout is Layout.FIT_BLUR


def test_tracker_keeps_identity() -> None:
    tr = FaceTracker()
    ids = set()
    for t in range(10):
        active = tr.update(t * 200, [Box(0.2 + t * 0.005, 0.3, 0.1, 0.15)])
        ids.add(active[0].id)
    assert ids == {0}


def test_speaker_map() -> None:
    samples = [AsdSample(i, "A", {0: 0.9, 1: 0.1}) for i in range(5)] + [
        AsdSample(i, "B", {0: 0.2, 1: 0.8}) for i in range(5)]
    m = learn_speaker_to_track(samples)
    assert m == {"A": 0, "B": 1}
    assert active_track(AsdSample(0, "B", {0: 0.55, 1: 0.45}), m) == 1
