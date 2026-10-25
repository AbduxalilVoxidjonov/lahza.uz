"""Run: PYTHONPATH=engine/src engine/.venv/bin/pytest examples/efficient_pipeline -q."""

from copy import deepcopy
from dataclasses import replace
from random import Random
from time import perf_counter

import pytest

from examples.efficient_pipeline.edit_model import delete_source, keep_spans, merge_spans
from examples.efficient_pipeline.vad_cleaner import Config, Word, normalize, plan_cleanup


def timeline():
    return {
        "schema": "lahza.timeline/1",
        "media": {
            "v": {
                "id": "v",
                "path": "/v.mp4",
                "duration_ms": 40000,
                "width": 1920,
                "height": 1080,
                "fps": 30,
            },
            "m": {
                "id": "m",
                "path": "/m.wav",
                "duration_ms": 40000,
                "width": 0,
                "height": 0,
                "fps": 0,
            },
        },
        "video": [
            {
                "id": "a",
                "media": "v",
                "src_in_ms": 0,
                "src_out_ms": 8000,
                "speed": 2,
                "fx": [],
                "transition_in": None,
            },
            {
                "id": "repeat",
                "media": "v",
                "src_in_ms": 0,
                "src_out_ms": 8000,
                "speed": 1,
                "fx": [],
                "transition_in": None,
            },
        ],
        "captions": {
            "enabled": True,
            "words": [
                {"text": "crossing", "start_ms": 900, "end_ms": 1100},
                {"text": "after", "start_ms": 2000, "end_ms": 2200},
                {"text": "repeat", "start_ms": 5000, "end_ms": 5300},
            ],
        },
        "text": [{"id": "t", "text": "title", "start_ms": 500, "end_ms": 2500}],
        "stickers": [
            {"id": "gone", "path": "/s.png", "start_ms": 1000, "end_ms": 2000},
            {"id": "s", "path": "/s.png", "start_ms": 2000, "end_ms": 4500},
        ],
        "music": [
            {
                "media": "m",
                "src_in_ms": 1000,
                "start_ms": 0,
                "end_ms": None,
                "fade_in_ms": 500,
                "fade_out_ms": 1500,
            }
        ],
    }


def duration(tl):
    return sum(round((v["src_out_ms"] - v["src_in_ms"]) / v.get("speed", 1)) for v in tl["video"])


def test_speed_repeated_occurrence_and_ripple_all_tracks():
    original = timeline()
    snapshot = deepcopy(original)
    edited = delete_source(original, "a", [(2000, 4000)])
    assert original == snapshot
    assert duration(edited) == 11000
    assert [(v["src_in_ms"], v["src_out_ms"], v["speed"]) for v in edited["video"]] == [
        (0, 2000, 2),
        (4000, 8000, 2),
        (0, 8000, 1),
    ]
    assert edited["video"][0]["id"] == "a"
    assert edited["video"][-1] == original["video"][-1]
    assert [(w["text"], w["start_ms"], w["end_ms"]) for w in edited["captions"]["words"]] == [
        ("after", 1000, 1200),
        ("repeat", 4000, 4300),
    ]
    assert (edited["text"][0]["start_ms"], edited["text"][0]["end_ms"]) == (500, 1500)
    assert [(s["id"], s["start_ms"], s["end_ms"]) for s in edited["stickers"]] == [
        ("s", 1000, 3500)
    ]
    assert [(m["start_ms"], m["end_ms"], m["src_in_ms"]) for m in edited["music"]] == [
        (0, 1000, 1000),
        (1000, 11000, 3000),
    ]
    assert edited["music"][0]["fade_out_ms"] == edited["music"][1]["fade_in_ms"] == 0
    assert delete_source(original, "a", [(2000, 4000)]) == edited  # stable IDs
    edited["media"]["v"]["path"] = "changed"
    assert original == snapshot  # undo snapshot owns ALL nested objects


def test_actual_montage_schema_roundtrip():
    model = pytest.importorskip("lahza_engine.montage.model")
    edited = delete_source(timeline(), "a", [(2000, 4000)])
    validated = model.MontageTimeline.model_validate(edited)
    assert validated.duration_ms == duration(edited)
    assert validated.to_json()["schema"] == "lahza.timeline/1"


def test_randomized_span_complement_against_integer_set():
    rng = Random(16)
    for _ in range(300):
        cuts = [tuple(sorted(rng.sample(range(101), 2))) for _ in range(rng.randrange(10))]
        kept = keep_spans((0, 100), cuts)
        expected = set(range(100)) - {t for a, b in cuts for t in range(a, b)}
        assert {t for a, b in kept for t in range(a, b)} == expected
        assert sum(b - a for a, b in kept) == len(expected)
        assert merge_spans(merge_spans(cuts)) == merge_spans(cuts)


def test_randomized_speed_duration_overlay_consistency():
    rng = Random(123)
    for speed in (0.25, 0.75, 1, 1.3, 2, 4):
        for _ in range(30):
            tl = timeline()
            tl["video"][0]["speed"] = speed
            old = duration(tl)
            tl["captions"]["words"] = []
            tl["text"][0].update(start_ms=0, end_ms=old)
            tl["stickers"] = []
            lo, hi = sorted(rng.sample(range(100, 7900, 20), 2))
            out = delete_source(tl, "a", [(lo, hi)])
            assert duration(out) == round(lo / speed) + round((8000 - hi) / speed) + 8000
            assert out["text"][0]["end_ms"] == duration(out)
            assert all(0 <= m["start_ms"] < m["end_ms"] <= duration(out) for m in out["music"])
            assert out["video"][-1] == tl["video"][-1]


@pytest.mark.parametrize("cut", [[(-1, 10)], [(2, 2)], [(0, 9000)], [(1.5, 4)], [(True, 4)]])
def test_bad_source_cuts(cut):
    with pytest.raises(ValueError):
        delete_source(timeline(), "a", cut)


@pytest.mark.parametrize("speed", [float("nan"), float("inf"), 0, -1, True, 5])
def test_bad_speeds(speed):
    tl = timeline()
    tl["video"][0]["speed"] = speed
    with pytest.raises(ValueError):
        delete_source(tl, "a", [(2000, 4000)])


def test_explicit_unsupported_and_empty_semantics():
    for kind in ("transition", "fx", "card", "schema", "duplicate", "empty"):
        tl = timeline()
        if kind == "transition":
            tl["video"][1]["transition_in"] = {"plugin": "fade", "dur_ms": 100}
        elif kind == "fx":
            tl["video"][0]["fx"] = [{"plugin": "freeze"}]
        elif kind == "card":
            tl["text"][0].update(kind="card", end_ms=13000)
        elif kind == "schema":
            tl["schema"] = "other/1"
        elif kind == "duplicate":
            tl["video"][1]["id"] = "a"
        else:
            tl["video"] = tl["video"][:1]
        with pytest.raises(ValueError):
            delete_source(tl, "a", [(0, 8000)])
    with pytest.raises(ValueError):
        delete_source(timeline(), "not-an-occurrence", [])


def test_global_color_lut_is_preserved():
    tl = timeline()
    tl["color"] = {"plugin": "uz.lahza.color.lut", "params": {"path": "/warm.cube"}}
    result = delete_source(tl, "a", [(2000, 4000)])
    assert result["color"] == tl["color"]
    assert result["color"] is not tl["color"]


def test_noop_and_submillisecond_edits():
    tl = timeline()
    out = delete_source(tl, "a", [])
    assert out == tl and out is not tl
    with pytest.raises(ValueError, match="zero output"):
        delete_source(tl, "a", [(0, 1)])
    tl["video"][0]["src_out_ms"] = 1
    with pytest.raises(ValueError, match="zero output"):
        delete_source(tl, "a", [])


def test_delete_whole_occurrence_not_all_source_occurrences():
    result = delete_source(timeline(), "a", [(0, 8000)])
    assert [v["id"] for v in result["video"]] == ["repeat"]
    assert [(w["text"], w["start_ms"]) for w in result["captions"]["words"]] == [("repeat", 1000)]


def test_weak_vad_never_cuts_words_even_low_confidence():
    words = [Word("real", "salom", 1200, 1600, 0.1), Word("end", "dunyo", 3500, 3800)]
    snapshot = deepcopy(words)
    result = plan_cleanup(words, [(0, 800), (3000, 4000)], 4000)
    assert result.cuts == ((970, 1160), (1640, 2830))
    assert words == snapshot
    for a, b in result.cuts:
        assert all(b <= w.start_ms - 40 or a >= w.end_ms + 40 for w in words)


def test_pause_threshold_padding_and_missing_vad():
    assert not plan_cleanup([], [(0, 100), (700, 1000)], 1000).cuts  # exactly 600
    assert plan_cleanup([], [(0, 100), (900, 1000)], 1000).cuts == ((270, 730),)
    assert not plan_cleanup([], [], 10000).cuts  # unknown VAD is not silence
    assert plan_cleanup([], [(3000, 5000)], 8000).cuts == ((170, 2830), (5170, 7830))


def test_filler_normalization_review_confidence_and_allow_list():
    words = [
        Word("a", "HALIGI,", 100, 400, 0.99),
        Word("b", "demak", 500, 800, 0.99),
        Word("c", "xo‘sh", 900, 1200, 0.99),
        Word("d", "anaqa", 1300, 1600, 0.4),
        Word("e", "e-e-e", 1700, 1750, 0.99),
        Word("f", "haligi", 1800, 2100),
        Word("g", "haligina", 2200, 2500, 0.99),
    ]
    plan = plan_cleanup(words, [], 3000)
    assert plan.cuts == ((100, 400),)
    assert plan.auto_word_ids == ("a",)
    assert [r.reason for r in plan.review] == [
        "meaningful_term",
        "meaningful_term",
        "low_or_missing_confidence",
        "short_token",
        "low_or_missing_confidence",
    ]
    approved = plan_cleanup(words, [], 3000, Config(allow_terms=("demak", "xo'sh")))
    assert approved.auto_word_ids == ("a", "b", "c")
    assert normalize("XOʻSH!") == normalize("xo’sh") == "xo'sh"


def test_phrase_and_overlapping_word_protection():
    words = [Word("a", "ana", 100, 240, 0.99), Word("b", "endi", 260, 450, 0.99)]
    config = Config(allow_terms=("ana endi",))
    assert plan_cleanup(words, [], 1000, config).cuts == ((100, 450),)
    overlap = words + [Word("c", "real", 400, 600, 0.99)]
    assert plan_cleanup(overlap, [], 1000, config).cuts == ((100, 360),)
    assert plan_cleanup([Word("h", "eee", 100, 500, 0.99)], [], 1000).cuts == ((100, 500),)


@pytest.mark.parametrize("case", ["word_bounds", "vad_bounds", "word_id", "nan_conf", "bad_config"])
def test_cleaner_invalid_inputs(case):
    words, speech, config = [Word("w", "test", 100, 300)], [(0, 500)], Config()
    if case == "word_bounds":
        words[0] = replace(words[0], end_ms=1100)
    elif case == "vad_bounds":
        speech = [(0, 1001)]
    elif case == "word_id":
        words.append(words[0])
    elif case == "nan_conf":
        words[0] = replace(words[0], confidence=float("nan"))
    else:
        config = Config(min_cut_ms=0)
    with pytest.raises(ValueError):
        plan_cleanup(words, speech, 1000, config)


def test_10000_word_cleanup_benchmark(record_property):
    words = [Word(str(i), "salom", i * 1000 + 100, i * 1000 + 300) for i in range(10000)]
    speech = [(w.start_ms, w.end_ms) for w in words]
    start = perf_counter()
    plan = plan_cleanup(words, speech, 10000000)
    record_property("cleanup_10000_words_seconds", perf_counter() - start)
    assert len(plan.cuts) == 10000
    assert plan.cuts[0] == (470, 930)
    assert plan.cuts[-1] == (9999470, 9999830)  # includes the 700ms trailing silence
    assert not plan.auto_word_ids


def test_randomized_cleaner_sweep_against_discrete_protection():
    rng = Random(67)
    config = Config(
        silence_ms=100, retain_pause_ms=20, edge_pad_ms=10, word_guard_ms=5, min_cut_ms=1
    )
    for _ in range(100):
        words = [
            Word(str(i), "real", a, b)
            for i, (a, b) in enumerate(tuple(sorted(rng.sample(range(1000), 2))) for _ in range(20))
        ]
        vad = [(0, 50), (950, 1000)]
        plan = plan_cleanup(words, vad, 1000, config)
        expected = set(range(70, 930)) - {
            t for w in words for t in range(max(0, w.start_ms - 5), min(1000, w.end_ms + 5))
        }
        assert {t for a, b in plan.cuts for t in range(a, b)} == expected
