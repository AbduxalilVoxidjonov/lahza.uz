"""Montaj rejalashtiruvchi (montage/planner.py): soxta manba tahlillari bilan, ffmpeg'siz."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime

import pytest
from conftest import make_sentences

from lahza_engine.config import Settings
from lahza_engine.montage import planner as planner_mod
from lahza_engine.montage.analyze import HighlightSeg, Shot, SourceAnalysis
from lahza_engine.montage.model import MediaRef, MontageTimeline
from lahza_engine.montage.planner import (
    MontageOverrides,
    PlanError,
    fill_placeholders,
    plan_montage,
)
from lahza_engine.templates.model import FxRule, Template, TextCard
from lahza_engine.templates.store import builtin_templates, get_builtin
from lahza_engine.types import Sentence, Word

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
SETTINGS = Settings(data_dir="/nonexistent")


def media(mid: str, dur: int, has_audio: bool = True) -> MediaRef:
    return MediaRef(id=mid, path=f"/videos/{mid}.mp4", hash=f"b2b:{mid}", duration_ms=dur, width=1920,
                    height=1080, fps=25.0, has_audio=has_audio)


def curve(dur: int, phase: float = 0.0) -> list[float]:
    return [round(0.5 + 0.4 * math.sin(i / 3.0 + phase), 4) for i in range(-(-dur // 500))]


def speech_source(mid: str, n: int = 20, speakers: bool = True) -> SourceAnalysis:
    sents = make_sentences(n)  # har gap 6 s + 0.4 s pauza
    if speakers:
        sents = [s.model_copy(update={"speaker": "A" if (i // 3) % 2 == 0 else "B"}) for i, s in enumerate(sents)]
    dur = sents[-1].end_ms + 1000
    hl = [] if n < 20 else [
        HighlightSeg(start_ms=sents[2].start_ms - 150, end_ms=sents[6].end_ms + 300, score=0.9,
                     title=f"{mid} eng zo'r", clip_id=f"{mid}-c1"),
        HighlightSeg(start_ms=sents[9].start_ms - 150, end_ms=sents[12].end_ms + 300, score=0.7,
                     title=f"{mid} ikkinchi", clip_id=f"{mid}-c2"),
        HighlightSeg(start_ms=sents[14].start_ms - 150, end_ms=sents[18].end_ms + 300, score=0.6,
                     title="", clip_id=f"{mid}-c3"),
    ]
    emphasis = [sents[i].words[3].start_ms for i in (2, 3, 4, 5, 10, 11, 15) if i < n]
    changes = [s.start_ms for i, s in enumerate(sents) if i and s.speaker != sents[i - 1].speaker]
    return SourceAnalysis(
        media=media(mid, dur), shots=[Shot(0, dur, score=0.6, has_speech=True)],
        speech=[(s.start_ms, s.end_ms) for s in sents], sentences=sents, highlights=hl,
        emphasis_ms=emphasis, speaker_changes_ms=changes, curve=curve(dur),
    )


def scene_source(mid: str, shot_ms: list[int], phase: float = 0.0, has_audio: bool = True,
                 recorded_at: str | None = None) -> SourceAnalysis:
    shots, t = [], 0
    for k, d in enumerate(shot_ms):
        shots.append(Shot(t, t + d, score=round(0.4 + 0.5 * abs(math.sin(k + phase)), 4), sharpness=0.6,
                          motion=0.05, energy=0.5))
        t += d
    return SourceAnalysis(media=media(mid, t, has_audio), shots=shots, curve=curve(t, phase),
                          recorded_at=recorded_at)


def scene_sources() -> list[SourceAnalysis]:
    return [
        scene_source("a", [2500, 6000, 900, 400, 3000, 12000, 2200], 0.0, recorded_at="2026-10-01T10:00:00Z"),
        scene_source("b", [4000, 1800, 2600, 9000, 3100], 1.0, recorded_at="2026-10-01T09:00:00Z"),
        scene_source("c", [20000, 2400, 2700, 1500], 2.0, recorded_at=None),
    ]


@pytest.fixture(autouse=True)
def _fake_music(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(planner_mod, "_probe_music", lambda path: (120_000, "b2b:music"))


def plan(t: Template, sources: list[SourceAnalysis], **ov: object) -> MontageTimeline:
    return plan_montage(t, sources, MontageOverrides(**ov), SETTINGS, now=NOW)  # type: ignore[arg-type]


def sources_for(t: Template) -> list[SourceAnalysis]:
    return [speech_source("p1"), speech_source("p2")] if t.selection == "highlight" else scene_sources()


def assert_no_repeats(tl: MontageTimeline) -> None:
    by_media: dict[str, list[tuple[int, int]]] = {}
    for it in tl.video:
        by_media.setdefault(it.media, []).append((it.src_in_ms, it.src_out_ms))
    for spans in by_media.values():
        spans.sort()
        for (_a0, a1), (b0, _b1) in zip(spans, spans[1:], strict=False):
            assert b0 >= a1 - planner_mod.OVERLAP_TOL_MS, spans


# --- har o'rnatilgan shablon -----------------------------------------------------------------


@pytest.mark.parametrize("tpl", builtin_templates(), ids=lambda t: t.id)
def test_every_builtin_plans(tpl: Template) -> None:
    tl = plan(tpl, sources_for(tpl), music_path="/music/track.mp3", title="Yangi mavsum", shou="Lahza",
              cta="Obuna bo'ling")
    assert tl.video, tpl.id
    assert abs(tl.duration_ms - tpl.target_duration_ms) <= 0.2 * tpl.target_duration_ms, (
        tpl.id, tl.duration_ms, tl.provenance.notes)
    assert tl.video[0].transition_in is None
    assert_no_repeats(tl)
    assert tl.provenance.template_id == tpl.id and tl.provenance.planner == "qoida"
    assert tl.provenance.created_at == "2026-10-20T12:00:00+00:00"
    assert all(it.reason for it in tl.video)
    # JSON orqali qayta validatsiya.
    again = MontageTimeline.model_validate(tl.to_json())
    assert again.to_json() == tl.to_json()
    assert tl.to_json()["schema"] == "lahza.timeline/1"
    # Kadr uzunligi: shablon chegaralaridan juda chiqmaydi (intro/outro uzaytirish hisobga olinadi).
    extra = (tpl.intro.dur_ms if tpl.intro else 0) + (tpl.outro.dur_ms if tpl.outro else 0)
    for it in tl.video:
        assert it.out_duration_ms <= tpl.max_shot_ms + extra + 3000, (tpl.id, it)
    if tpl.mute_sources:
        assert all(it.mute for it in tl.video)
    if tpl.transition and tpl.transition.plugin != "uz.lahza.tr.cut":
        assert all(it.transition_in and it.transition_in.plugin == tpl.transition.plugin for it in tl.video[1:])
    else:
        assert all(it.transition_in is None for it in tl.video)
    if tpl.color:
        assert tl.color is not None and tl.color.plugin == tpl.color
    assert tl.captions.enabled == tpl.captions
    assert tl.audio.loudnorm_lufs == tpl.loudnorm_lufs


@pytest.mark.parametrize("tpl", builtin_templates(), ids=lambda t: t.id)
def test_deterministic(tpl: Template) -> None:
    a = plan(tpl, sources_for(tpl), music_path="/m.mp3", title="X")
    b = plan(tpl, sources_for(tpl), music_path="/m.mp3", title="X")
    assert json.dumps(a.to_json(), sort_keys=True) == json.dumps(b.to_json(), sort_keys=True)


# --- gap chegaralari -------------------------------------------------------------------------


def _inside_word(sents: list[Sentence], t: int) -> bool:
    return any(w.start_ms < t < w.end_ms for s in sents for w in s.words)


@pytest.mark.parametrize("tid", ["uz.lahza.tpl.podcast-hook", "uz.lahza.tpl.interview-clean",
                                 "uz.lahza.tpl.course-announce"])
def test_cuts_never_inside_words(tid: str) -> None:
    srcs = [speech_source("p1"), speech_source("p2")]
    tl = plan(get_builtin(tid), srcs, target_duration_ms=25_000)
    sents = {s.media.id: s.sentences for s in srcs}
    for it in tl.video:
        assert not _inside_word(sents[it.media], it.src_in_ms), it
        assert not _inside_word(sents[it.media], it.src_out_ms), it


def test_scene_selection_snaps_to_sentences_when_speech() -> None:
    tpl = get_builtin("uz.lahza.tpl.daily-story")
    sa = speech_source("s", n=10)
    # Bitta uzun shot -> bir nechta oyna; nutq bor -> gap chegarasi.
    tl = plan(tpl, [sa], target_duration_ms=20_000)
    for it in tl.video:
        assert not _inside_word(sa.sentences, it.src_in_ms)
        assert not _inside_word(sa.sentences, it.src_out_ms)
    assert any("gap chegarasiga" in it.reason for it in tl.video)


# --- effekt trigger'lari ---------------------------------------------------------------------


def test_emphasis_punch_in_limits() -> None:
    tpl = get_builtin("uz.lahza.tpl.podcast-hook")
    tl = plan(tpl, [speech_source("p1"), speech_source("p2")], target_duration_ms=60_000)
    starts = tl.item_starts()
    pts = sorted(starts[i] + f.at_ms for i, it in enumerate(tl.video) for f in it.fx
                 if f.plugin == "uz.lahza.motion.punch-in")
    rule = tpl.fx[0]
    assert 1 <= len(pts) <= rule.max_count
    assert all(b - a >= rule.min_gap_ms for a, b in zip(pts, pts[1:], strict=False))
    # Effekt nuqtasi haqiqiy urg'u nuqtasiga tushadi.
    srcs = {"p1": speech_source("p1"), "p2": speech_source("p2")}
    for it in tl.video:
        for f in it.fx:
            assert it.src_in_ms + f.at_ms in srcs[it.media].emphasis_ms
            assert f.dur_ms is not None and f.dur_ms <= planner_mod.POINT_FX_MS
            assert f.params["zoom"] == 1.2


def _custom(fx: list[FxRule], **kw: object) -> Template:
    base = get_builtin("uz.lahza.tpl.event-rhythm").model_copy(update={"fx": fx, "builtin": False, **kw})
    return base


def test_triggers_on_cut_every_n_start_end() -> None:
    fx = [
        FxRule(plugin="uz.lahza.motion.shake", trigger="on_start", min_gap_ms=0),
        FxRule(plugin="uz.lahza.audio.fade", trigger="on_end", min_gap_ms=0),
        FxRule(plugin="uz.lahza.motion.push-in", trigger="on_cut", min_gap_ms=0, max_count=4),
        FxRule(plugin="uz.lahza.motion.zoom-out", trigger="every_n", every_n=3, min_gap_ms=0),
    ]
    tl = plan(_custom(fx), scene_sources(), music_path="/m.mp3")
    n = len(tl.video)
    assert n >= 6
    plugins = [[f.plugin for f in it.fx] for it in tl.video]
    assert "uz.lahza.motion.shake" in plugins[0] and all("uz.lahza.motion.shake" not in p for p in plugins[1:])
    assert "uz.lahza.audio.fade" in plugins[-1]
    cut_items = [i for i, p in enumerate(plugins) if "uz.lahza.motion.push-in" in p]
    assert cut_items == [1, 2, 3, 4]  # max_count=4, birinchi elementda emas
    every = [i for i, p in enumerate(plugins) if "uz.lahza.motion.zoom-out" in p]
    assert every == list(range(2, n, 3))
    end_fx = next(f for f in tl.video[-1].fx if f.plugin == "uz.lahza.audio.fade")
    assert end_fx.at_ms == max(0, tl.video[-1].out_duration_ms - planner_mod.ON_END_LEAD_MS)


def test_min_gap_between_cut_fx() -> None:
    fx = [FxRule(plugin="uz.lahza.motion.push-in", trigger="on_cut", min_gap_ms=5000)]
    tl = plan(_custom(fx), scene_sources(), music_path="/m.mp3")
    starts = tl.item_starts()
    pts = [starts[i] + f.at_ms for i, it in enumerate(tl.video) for f in it.fx]
    assert len(pts) >= 2
    assert all(b - a >= 5000 for a, b in zip(pts, pts[1:], strict=False))


def test_speaker_change_trigger() -> None:
    tpl = get_builtin("uz.lahza.tpl.interview-clean").model_copy(
        update={"fx": [FxRule(plugin="uz.lahza.motion.punch-in", trigger="on_speaker_change", min_gap_ms=0)]})
    sa = speech_source("p1")
    tl = plan(tpl, [sa])
    found = [(it, f) for it in tl.video for f in it.fx]
    assert found
    for it, f in found:
        assert it.src_in_ms + f.at_ms in sa.speaker_changes_ms


# --- tanlash va tartib -----------------------------------------------------------------------


def test_diversity_and_max_per_source() -> None:
    tpl = get_builtin("uz.lahza.tpl.event-rhythm")
    tl = plan(tpl, scene_sources(), music_path="/m.mp3")
    ms = [it.media for it in tl.video]
    for i in range(2, len(ms)):
        assert not (ms[i] == ms[i - 1] == ms[i - 2]), ms
    counts = {m: ms.count(m) for m in set(ms)}
    assert max(counts.values()) <= tpl.max_per_source  # type: ignore[operator]
    assert all(tpl.min_shot_ms <= it.out_duration_ms <= tpl.max_shot_ms for it in tl.video)


def test_single_source_relaxes_max_per_source() -> None:
    tpl = get_builtin("uz.lahza.tpl.event-rhythm")
    tl = plan(tpl, [scene_source("solo", [60_000])], music_path="/m.mp3")
    assert abs(tl.duration_ms - tpl.target_duration_ms) <= 0.2 * tpl.target_duration_ms
    assert len(tl.video) > tpl.max_per_source  # type: ignore[operator]
    assert any("cheklovi yumshatildi" in n for n in tl.provenance.notes)
    assert_no_repeats(tl)


def test_chronological_order() -> None:
    tpl = get_builtin("uz.lahza.tpl.daily-story")
    tl = plan(tpl, scene_sources())
    ms = [it.media for it in tl.video]
    # b (09:00) -> a (10:00) -> c (vaqti noma'lum)
    rank = {"b": 0, "a": 1, "c": 2}
    assert [rank[m] for m in ms] == sorted(rank[m] for m in ms)
    for m in set(ms):
        ins = [it.src_in_ms for it in tl.video if it.media == m]
        assert ins == sorted(ins)


def test_given_order_and_highlight_fallback_note() -> None:
    tpl = get_builtin("uz.lahza.tpl.course-announce")
    srcs = [speech_source("p1"), scene_source("broll", [3000, 4000, 5000])]
    tl = plan(tpl, srcs, title="Kurs")
    ms = [it.media for it in tl.video]
    assert ms == sorted(ms, key=lambda m: ["p1", "broll"].index(m))
    assert any("highlight yo'q" in n for n in tl.provenance.notes)


def test_highlight_reason_and_hook_role() -> None:
    tl = plan(get_builtin("uz.lahza.tpl.podcast-hook"), [speech_source("p1")])
    assert tl.video[0].role == "hook"
    assert tl.video[0].reason.startswith("highlight: p1 eng zo'r")


def test_full_selection() -> None:
    tpl = Template(id="user.full-test", name={"uz": "To'liq"}, selection="full", target_duration_ms=20_000,
                   max_shot_ms=60_000, respect_sentences=False)
    tl = plan(tpl, [scene_source("a", [8000]), scene_source("b", [30_000])])
    assert [it.media for it in tl.video] == ["a", "b"]
    assert (tl.video[0].src_in_ms, tl.video[0].src_out_ms) == (0, 8000)
    assert abs(tl.duration_ms - 20_000) <= 4000


# --- matn, subtitr, musiqa -------------------------------------------------------------------


def test_intro_outro_cards_product_promo() -> None:
    tpl = get_builtin("uz.lahza.tpl.product-promo")
    tl = plan(tpl, scene_sources(), title="Yangi krossovka")
    intro = next(t for t in tl.text if t.id == "intro")
    outro = next(t for t in tl.text if t.id == "outro")
    assert (intro.start_ms, intro.end_ms, intro.kind, intro.text) == (0, 1500, "card", "Yangi krossovka")
    assert intro.background == "#111111"
    assert outro.end_ms == tl.duration_ms and outro.end_ms - outro.start_ms == 2500
    assert outro.text == "Hoziroq buyurtma bering"  # {cta:...} standart qiymati
    # Birinchi element intro muddatiga uzaytirilgan (karta ostida "isrof" bo'lmasligi uchun).
    assert tl.video[0].out_duration_ms >= tpl.min_shot_ms + 1500 - 50
    assert tl.video[-1].role == "cta"
    # Karta ostida effekt yo'q.
    starts = tl.item_starts()
    for i, it in enumerate(tl.video):
        for f in it.fx:
            g = starts[i] + f.at_ms
            assert not 0 <= g < 1500 and not outro.start_ms <= g < outro.end_ms
    assert any("logo" in n for n in tl.provenance.notes)


def test_placeholders_and_missing_title() -> None:
    tpl = get_builtin("uz.lahza.tpl.product-promo")
    tl = plan(tpl, scene_sources(), cta="Do'konga kiring", logo_path="/brand/logo.png")
    assert not any(t.id == "intro" for t in tl.text)
    assert any("intro matni bo'sh" in n for n in tl.provenance.notes)
    assert next(t for t in tl.text if t.id == "outro").text == "Do'konga kiring"
    assert tl.brand.logo_path == "/brand/logo.png"
    assert fill_placeholders("{shou} | {sarlavha}", {"shou": "Lahza", "sarlavha": None}) == "Lahza |"
    assert fill_placeholders("{cta}", {}) is None
    assert fill_placeholders("{ cta : Obuna }", {"cta": "  "}) == "Obuna"


def test_hook_text_and_lower_third() -> None:
    tl = plan(get_builtin("uz.lahza.tpl.course-announce"), [speech_source("p1")], title="Python kursi")
    hook = next(t for t in tl.text if t.id == "hook")
    assert (hook.kind, hook.text, hook.start_ms) == ("hook", "Python kursi", 0)
    tl2 = plan(get_builtin("uz.lahza.tpl.interview-clean"), [speech_source("p1")], shou="Mehmon: Ali Valiyev")
    lt = next(t for t in tl2.text if t.id == "hook")
    assert lt.kind == "lower_third" and lt.background is None
    # Sarlavha berilmasa - highlight sarlavhasi ishlatiladi.
    tl3 = plan(get_builtin("uz.lahza.tpl.course-announce"), [speech_source("p1")])
    assert next(t for t in tl3.text if t.id == "hook").text == "p1 eng zo'r"


def test_captions_words_in_output_time() -> None:
    srcs = [speech_source("p1"), speech_source("p2")]
    tl = plan(get_builtin("uz.lahza.tpl.course-announce"), srcs)
    words = tl.captions.words
    assert tl.captions.enabled and words
    assert tl.captions.style.animation == "pop"
    assert all(a.end_ms <= b.start_ms for a, b in zip(words, words[1:], strict=False))
    assert all(w.end_ms > w.start_ms for w in words)
    outro = next(t for t in tl.text if t.id == "outro")
    assert all(w.start_ms < outro.start_ms for w in words)  # karta ostida subtitr yo'q
    # Birinchi so'z: manba vaqti -> chiqish vaqti.
    first = tl.video[0]
    src_words = [w for s in srcs[[s.media.id for s in srcs].index(first.media)].sentences for w in s.words
                 if w.start_ms >= first.src_in_ms]
    assert words[0].text == src_words[0].text
    assert words[0].start_ms == src_words[0].start_ms - first.src_in_ms


def test_captions_override_off_and_style() -> None:
    from lahza_engine.subtitle.style import StyleTemplate

    tl = plan(get_builtin("uz.lahza.tpl.podcast-hook"), [speech_source("p1")], captions=False)
    assert not tl.captions.enabled and tl.captions.words  # retained for a later captions-on toggle
    st = StyleTemplate(name="Mening", font_size=50)
    tl2 = plan(get_builtin("uz.lahza.tpl.daily-story"), scene_sources(), captions=True, caption_style=st)
    assert tl2.captions.enabled and tl2.captions.style.name == "Mening"
    assert any("transkript yo'q" in n for n in tl2.provenance.notes)


def test_music_item_and_required_warning() -> None:
    tpl = get_builtin("uz.lahza.tpl.event-rhythm")
    tl = plan(tpl, scene_sources(), music_path="/music/song.mp3")
    assert tl.media["music"].path == "/music/song.mp3" and tl.media["music"].duration_ms == 120_000
    assert len(tl.music) == 1 and tl.music[0].media == "music"
    assert tl.music[0].gain_db == tpl.music.gain_db and tl.music[0].duck is False  # type: ignore[union-attr]
    tl2 = plan(tpl, scene_sources())
    assert not tl2.music and "music" not in tl2.media
    assert any("musiqa tanlanmagan" in n for n in tl2.provenance.notes)
    assert any("ovozsiz" in n for n in tl2.provenance.notes)


def test_music_probe_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def bad(path: str) -> tuple[int, str | None]:
        raise PlanError("musiqa faylini o'qib bo'lmadi: test")

    monkeypatch.setattr(planner_mod, "_probe_music", bad)
    with pytest.raises(PlanError, match="musiqa"):
        plan(get_builtin("uz.lahza.tpl.event-rhythm"), scene_sources(), music_path="/x.mp3")


# --- overrides -------------------------------------------------------------------------------


def test_overrides_format_transition_color() -> None:
    tpl = get_builtin("uz.lahza.tpl.daily-story")
    tl = plan(tpl, scene_sources(), aspect="16:9", transition="uz.lahza.tr.cut", color="")
    assert (tl.format.aspect, tl.format.w, tl.format.h) == ("16:9", 1920, 1080)
    assert all(it.transition_in is None for it in tl.video)
    assert tl.color is None
    tl2 = plan(get_builtin("uz.lahza.tpl.podcast-hook"), [speech_source("p1"), speech_source("p2")],
               transition="uz.lahza.tr.fade", color="uz.lahza.color.cool", target_duration_ms=50_000)
    assert all(it.transition_in and it.transition_in.plugin == "uz.lahza.tr.fade" for it in tl2.video[1:])
    assert tl2.color is not None and tl2.color.plugin == "uz.lahza.color.cool"


def test_override_unknown_plugin_rejected() -> None:
    pytest.importorskip("lahza_engine.fx.registry")
    with pytest.raises(PlanError, match="o'rnatilmagan"):
        plan(get_builtin("uz.lahza.tpl.daily-story"), scene_sources(), transition="uz.lahza.tr.yoq")
    with pytest.raises(PlanError):
        plan(get_builtin("uz.lahza.tpl.daily-story"), scene_sources(), color="uz.lahza.tr.fade")


def test_target_override_respected() -> None:
    tl = plan(get_builtin("uz.lahza.tpl.event-rhythm"), scene_sources(), target_duration_ms=12_000,
              music_path="/m.mp3")
    assert abs(tl.duration_ms - 12_000) <= 2400


# --- xatolar ---------------------------------------------------------------------------------


def test_plan_errors() -> None:
    tpl = get_builtin("uz.lahza.tpl.event-rhythm")
    with pytest.raises(PlanError, match="tanlanmagan"):
        plan(tpl, [])
    with pytest.raises(PlanError, match="takroriy"):
        plan(tpl, [scene_source("a", [5000]), scene_source("a", [5000])])
    with pytest.raises(PlanError, match="band"):
        plan(tpl, [scene_source("music", [5000])])
    with pytest.raises(PlanError, match="format"):
        plan(tpl, scene_sources(), aspect="4:3")
    with pytest.raises(PlanError, match="davomiylik"):
        plan(tpl, scene_sources(), target_duration_ms=1000)
    with pytest.raises(PlanError, match="yaroqli"):
        plan(tpl, [SourceAnalysis(media=media("tiny", 300), shots=[Shot(0, 300)])])
    with pytest.raises(PlanError, match="kartalaridan"):
        plan(get_builtin("uz.lahza.tpl.product-promo"), scene_sources(), target_duration_ms=5000)


def test_silent_source_items_muted() -> None:
    tl = plan(get_builtin("uz.lahza.tpl.daily-story"), [scene_source("q", [3000, 3000, 3000], has_audio=False),
                                                        scene_source("r", [3000, 3000, 3000])])
    assert all(it.mute for it in tl.video if it.media == "q")
    assert not any(it.mute for it in tl.video if it.media == "r")


def test_word_mapping_with_custom_speech() -> None:
    """Qo'lda tuzilgan qisqa transkript: so'zlar aynan element ichida qoladi."""
    words = [Word(text=f"w{i}", start_ms=1000 + i * 500, end_ms=1000 + i * 500 + 400) for i in range(20)]
    sents = [Sentence(id=0, start_ms=1000, end_ms=words[9].end_ms, words=words[:10]),
             Sentence(id=1, start_ms=words[10].start_ms, end_ms=words[19].end_ms, words=words[10:])]
    sa = SourceAnalysis(media=media("m", 12_000), shots=[Shot(0, 12_000, 0.7)], sentences=sents,
                        highlights=[HighlightSeg(900, 11_000, 0.8, "Bitta")])
    tpl = get_builtin("uz.lahza.tpl.course-announce").model_copy(update={"outro": None})
    tl = plan(tpl, [sa], target_duration_ms=10_000)
    it = tl.video[0]
    assert it.src_in_ms <= 1000 and it.src_out_ms >= words[19].end_ms
    assert [w.text for w in tl.captions.words] == [w.text for w in words]
    assert tl.captions.words[0].start_ms == 1000 - it.src_in_ms


def test_hook_text_card_kind_title_on_first_item() -> None:
    tpl = get_builtin("uz.lahza.tpl.daily-story").model_copy(
        update={"hook_text": TextCard(text="{sarlavha}", dur_ms=2000, kind="title")})
    tl = plan(tpl, scene_sources(), title="Samarqand kuni")
    h = next(t for t in tl.text if t.id == "hook")
    assert h.end_ms <= tl.item_starts()[0] + tl.video[0].out_duration_ms


# --- klip manbalari: oraliq va kesimlar (regressiya) ------------------------------------------


def _clip_source(segs: list[tuple[int, int]], explicit: bool) -> SourceAnalysis:
    """Epizoddan klip manbasi: so'zlar butun epizod bo'ylab, lekin foydalanish faqat `segs` ichida."""
    words = [Word(text=f"w{i}" + ("." if i % 8 == 7 else ""), start_ms=200 + i * 450,
                  end_ms=200 + i * 450 + 380) for i in range(60)]
    sents = [Sentence(id=k, start_ms=words[k * 8].start_ms, end_ms=words[k * 8 + 7].end_ms,
                      words=words[k * 8:k * 8 + 8]) for k in range(7)]
    # API kabi: klip ichidagi gaplar (yarmidan ko'pi ichidagi so'zlar).
    inside = [s.model_copy(update={"words": ws, "start_ms": ws[0].start_ms, "end_ms": ws[-1].end_ms})
              for s in sents if (ws := [w for w in s.words
                                        if any(a <= (w.start_ms + w.end_ms) // 2 < b for a, b in segs)])]
    m = MediaRef(id="ep1", path="/ep.mp4", duration_ms=30_000, width=1920, height=1080, fps=25,
                 origin="clip:e1/c1")
    return SourceAnalysis(
        media=m, shots=[Shot(a, b, 0.6) for a, b in segs], sentences=inside,
        highlights=[HighlightSeg(a, b, 0.8, "Klip", "c1") for a, b in segs],
        allowed=list(segs) if explicit else None,
    )


@pytest.mark.parametrize("explicit", [True, False])
@pytest.mark.parametrize("tid", ["uz.lahza.tpl.podcast-hook", "uz.lahza.tpl.course-announce",
                                 "uz.lahza.tpl.daily-story", "uz.lahza.tpl.product-promo"])
def test_clip_source_stays_inside_clip_and_skips_cuts(tid: str, explicit: bool) -> None:
    segs = [(1000, 5000), (6000, 11000)]  # 5000-6000 - foydalanuvchi o'chirgan kesim
    sa = _clip_source(segs, explicit)
    tl = plan(get_builtin(tid), [sa], target_duration_ms=8000, title="Sarlavha")
    assert tl.video
    for it in tl.video:
        assert any(a <= it.src_in_ms and it.src_out_ms <= b for a, b in segs), (it.src_in_ms, it.src_out_ms)


def test_clip_post_roll_not_beyond_clip_end() -> None:
    """Integratsiyada topilgan: klip oxiri 11000, snap post-roll'i element oxirini 11180 ga chiqargan."""
    sa = _clip_source([(1000, 11000)], explicit=False)
    tl = plan(get_builtin("uz.lahza.tpl.course-announce").model_copy(update={"outro": None}), [sa],
              target_duration_ms=12_000)
    assert max(it.src_out_ms for it in tl.video) <= 11_000
    assert min(it.src_in_ms for it in tl.video) >= 1000
