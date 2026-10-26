"""PRO-3 "Hook oldinga": hook tanlash, timeline prefiksi, subtitr siljishi, render bo'laklari, API."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from _api_helpers import make_client, seed_episode
from conftest import make_sentences, make_words

from lahza_engine.core.export import _with_hook_prefix
from lahza_engine.db import store as db
from lahza_engine.highlight.hook_front import (
    EARLY_ZONE_MS,
    HOOK_MAX_MS,
    HOOK_MIN_MS,
    hook_candidates,
    pick_hook,
    snap_hook,
)
from lahza_engine.highlight.signals import SentenceSignals, SignalReport
from lahza_engine.reframe.planner import LayoutSegment, Observation
from lahza_engine.render.graph import split_pieces
from lahza_engine.subtitle.ass import build_srt, map_words
from lahza_engine.timeline import Timeline, clip_timeline
from lahza_engine.types import Clip, ClipHook, ClipSource, Layout, Sentence

TEXTS = [
    "Bugun biz sizga bir narsa aytamiz.",
    "Va keyin u yerga bordik.",
    "Nega hamma 90 foiz xato qiladi?",
    "Shunday qilib hikoya oxiriga yetdi.",
]


def _sentences(texts: list[str] = TEXTS, pause_ms: int = 600) -> list[Sentence]:
    out, t = [], 1_000
    for i, text in enumerate(texts):
        ws = make_words(text, t)
        out.append(Sentence(id=i, start_ms=ws[0].start_ms, end_ms=ws[-1].end_ms, words=ws))
        t = ws[-1].end_ms + pause_ms
    return out


def _clip(sentences: list[Sentence], **kw) -> Clip:
    base = dict(id="c1", media_id="m", start_ms=sentences[0].start_ms - 100,
                end_ms=sentences[-1].end_ms + 200, start_sentence_id=sentences[0].id,
                end_sentence_id=sentences[-1].id)
    base.update(kw)
    return Clip(**base)


def _word_edges(sentences: list[Sentence]) -> tuple[set[int], set[int]]:
    return ({w.start_ms for s in sentences for w in s.words}, {w.end_ms for s in sentences for w in s.words})


# ---- Tanlash (sof funksiya) ------------------------------------------------------

def test_lite_picks_question_with_strong_words_and_number() -> None:
    ss = _sentences()
    pick = pick_hook(_clip(ss), ss)
    assert pick is not None
    assert pick.sentence_ids == (2,)
    assert pick.text == TEXTS[2]
    assert {"savol", "kuchli so'zlar", "son"} <= set(pick.reasons)


def test_pick_is_on_word_boundaries_and_within_length() -> None:
    ss = _sentences()
    pick = pick_hook(_clip(ss), ss)
    assert pick is not None
    words = [w for s in ss for w in s.words]
    first = next(w for w in words if w.end_ms > pick.start_ms)
    last = [w for w in words if w.start_ms < pick.end_ms][-1]
    # Bo'lak hech qaysi so'zni kesmaydi: chegaralar so'zlar orasidagi bo'shliqda.
    assert pick.start_ms <= first.start_ms and pick.end_ms >= last.end_ms
    assert not any(w.start_ms < pick.start_ms < w.end_ms or w.start_ms < pick.end_ms < w.end_ms
                   for w in words)
    assert HOOK_MIN_MS <= last.end_ms - first.start_ms <= HOOK_MAX_MS


def test_llm_hook_sentence_gets_priority() -> None:
    ss = make_sentences(6)  # neytral matn: faqat LLM hook_id farq qiladi
    clip = _clip(ss, hook_sentence_id=4)
    pick = pick_hook(clip, ss)
    assert pick is not None and pick.sentence_ids == (4,)
    assert "LLM hook gapi" in pick.reasons
    assert ss[4].start_ms - 100 <= pick.start_ms and pick.end_ms <= ss[4].end_ms + 200


def test_signals_steer_pick_in_lite_mode() -> None:
    ss = make_sentences(6)
    report = SignalReport([SentenceSignals(sentence_id=s.id, loudness_z=2.5 if s.id == 3 else 0.0)
                           for s in ss])
    pick = pick_hook(_clip(ss), ss, report)
    assert pick is not None and pick.sentence_ids == (3,)


def test_clip_opening_is_not_a_hook() -> None:
    ss = make_sentences(3)
    clip = _clip(ss, hook_sentence_id=0)  # LLM boshini ko'rsatsa ham - avtomatik tanlanmaydi
    for p in hook_candidates(clip, ss, limit=10):
        assert p.start_ms - clip.start_ms >= EARLY_ZONE_MS - 100
    # Qo'lda shu gap tanlansa - ruxsat.
    manual = pick_hook(clip, ss, sentence_id=0)
    assert manual is not None and manual.sentence_ids == (0,)


def test_speed_30_min_episode_all_clips() -> None:
    """Tezlik: 30 daqiqalik sintetik transkript (~300 gap, ~3600 so'z), signallar keshdan;
    30 ta 45 s klip uchun jami vaqt. Maqsad < 100 ms; CI uchun yumshoq chegara 1 s."""
    import time

    ss = make_sentences(300)  # 300 x 6.4 s ~ 32 daqiqa
    report = SignalReport([SentenceSignals(sentence_id=s.id, loudness_z=(s.id % 7) / 3) for s in ss])
    clips = [_clip(ss[i : i + 7], id=f"c{i}") for i in range(0, 300, 10)]
    pick_hook(clips[0], ss, report)  # isitish
    t0 = time.perf_counter()
    picks = [pick_hook(c, ss, report) for c in clips]
    total = time.perf_counter() - t0
    assert all(p is not None for p in picks)
    assert total < 1.0, f"{len(clips)} klip uchun {total * 1000:.1f} ms"


def test_cut_words_are_never_in_hook() -> None:
    ss = _sentences()
    cut = (ss[2].words[1].start_ms, ss[2].words[3].end_ms)
    clip = _clip(ss, cuts=[cut])
    for p in hook_candidates(clip, ss, limit=10):
        assert p.end_ms <= cut[0] or p.start_ms >= cut[1]


def test_sentence_restriction_and_short_sentence_whole() -> None:
    ss = _sentences(["Bir gap bu yerda turadi va davom etadi.", "Qisqa gap!", "Yana bir uzun gap shu yerda."])
    clip = _clip(ss)
    pick = pick_hook(clip, ss, sentence_id=1)
    assert pick is not None and pick.sentence_ids == (1,) and pick.text == "Qisqa gap!"
    assert pick_hook(clip, ss, sentence_id=99) is None


def test_too_short_clip_has_no_hook() -> None:
    ss = _sentences(["Salom dunyo."])
    assert pick_hook(_clip(ss), ss) is None


def test_candidates_do_not_overlap_and_are_sorted() -> None:
    ss = make_sentences(5)
    cands = hook_candidates(_clip(ss), ss, limit=5)
    assert len(cands) >= 2
    assert [c.score for c in cands] == sorted((c.score for c in cands), reverse=True)
    for i, a in enumerate(cands):
        for b in cands[i + 1:]:
            assert a.end_ms <= b.start_ms or b.end_ms <= a.start_ms


def test_snap_hook_expands_to_words_and_clamps() -> None:
    ss = _sentences()
    clip = _clip(ss)
    w = ss[2].words
    h = snap_hook(clip, ss, w[0].start_ms + 50, w[2].end_ms - 50)
    assert h == ClipHook(start_ms=w[0].start_ms, end_ms=w[2].end_ms)
    assert snap_hook(clip, ss, ss[2].end_ms + 10, ss[2].end_ms + 20) is None  # so'zsiz pauza


# ---- Timeline / render segmentlari ----------------------------------------------

def test_timeline_hook_prefix_segments() -> None:
    tl = Timeline(10_000, 20_000, hook=(15_000, 18_000))
    assert tl.prefix_ms == 3_000 and tl.duration_ms == 13_000
    assert [(s.src_start_ms, s.src_end_ms, s.out_start_ms) for s in tl.segments] == [
        (15_000, 18_000, 0), (10_000, 20_000, 3_000)]
    assert tl.to_out(10_000) == 3_000 and tl.to_out(16_000) == 9_000  # asosiy qism
    assert tl.prefix_to_out(16_000) == 1_000 and tl.prefix_to_out(12_000) is None
    assert tl.to_src(500) == 15_500 and tl.to_src(3_000) == 10_000
    assert tl.boundaries_out() == [3_000]
    assert tl.clamp_to_out(5_000) == 3_000


def test_timeline_default_unchanged() -> None:
    a, b = Timeline(0, 10_000, [(2_000, 3_000)]), Timeline(0, 10_000, [(2_000, 3_000)], hook=None)
    assert a.segments == b.segments and a.prefix_ms == 0 and a.duration_ms == 9_000
    assert a.prefix_segments == [] and a.body_segments == a.segments


def test_timeline_hook_respects_cuts_and_clip_bounds() -> None:
    tl = Timeline(10_000, 20_000, cuts=[(16_000, 17_000)], hook=(15_000, 18_000))
    assert [(s.src_start_ms, s.src_end_ms) for s in tl.prefix_segments] == [(15_000, 16_000), (17_000, 18_000)]
    assert tl.prefix_ms == 2_000 and tl.duration_ms == 2_000 + 9_000
    out_of_clip = Timeline(10_000, 20_000, hook=(19_000, 25_000))
    assert out_of_clip.prefix_ms == 1_000
    gone = Timeline(10_000, 20_000, cuts=[(15_000, 18_000)], hook=(15_000, 18_000))
    assert gone.prefix_ms == 0 and gone.duration_ms == 7_000


def test_clip_timeline_uses_hook_field() -> None:
    clip = Clip(id="c", media_id="m", start_ms=0, end_ms=10_000, start_sentence_id=0, end_sentence_id=1)
    assert clip_timeline(clip).prefix_ms == 0
    clip.hook = ClipHook(start_ms=4_000, end_ms=7_000)
    assert clip_timeline(clip).duration_ms == 13_000


def test_render_pieces_start_with_hook_copy() -> None:
    tl = Timeline(10_000, 20_000, hook=(15_000, 18_000))
    pieces = split_pieces(tl, [LayoutSegment(0, tl.duration_ms, Layout.FIT_BLUR)])
    assert [(p.src_start_ms, p.src_end_ms, p.out_start_ms, p.out_end_ms) for p in pieces] == [
        (15_000, 18_000, 0, 3_000), (10_000, 20_000, 3_000, 13_000)]


def test_observations_are_copied_into_prefix() -> None:
    tl = Timeline(10_000, 20_000, hook=(15_000, 18_000))
    body = [Observation(t_ms=tl.to_out(t)) for t in range(10_000, 20_000, 1_000)]
    obs = _with_hook_prefix(body, tl)
    pre = [o for o in obs if o.t_ms < 3_000]
    assert [o.t_ms for o in pre] == [0, 1_000, 2_000]
    assert pre[0].shot_cut and obs[len(pre)].shot_cut and obs[len(pre)].t_ms == 3_000
    assert [o.t_ms for o in obs] == sorted(o.t_ms for o in obs)
    assert _with_hook_prefix(body, Timeline(10_000, 20_000)) is body


# ---- Subtitr siljishi ---------------------------------------------------------------

def test_subtitles_repeat_hook_words_then_shift_body() -> None:
    words = make_words("bir ikki uch to'rt besh olti", 0, word_ms=900, gap_ms=100)  # har so'z 1 s
    tl = Timeline(0, 6_000, hook=(3_000, 5_000))  # "to'rt besh"
    mapped = map_words(words, tl)
    assert [(w.text, w.start_ms, w.end_ms) for w in mapped[:2]] == [("to'rt", 0, 900), ("besh", 1_000, 1_900)]
    assert [(w.text, w.start_ms) for w in mapped[2:]] == [
        ("bir", 2_000), ("ikki", 3_000), ("uch", 4_000), ("to'rt", 5_000), ("besh", 6_000), ("olti", 7_000)]
    srt = build_srt(words, tl, max_words=2)
    assert srt.startswith("1\n00:00:00,000 --> ")
    assert srt.count("to'rt") == 2
    # Hook'siz xulq o'zgarmagan.
    plain = map_words(words, Timeline(0, 6_000))
    assert [w.start_ms for w in plain] == [0, 1_000, 2_000, 3_000, 4_000, 5_000]


def _ass_events(ass: str) -> list[tuple[int, int, str]]:
    def ms(t: str) -> int:
        h, m, s = t.split(":")
        return round((int(h) * 3600 + int(m) * 60 + float(s)) * 1000)
    out = []
    for line in ass.splitlines():
        if line.startswith("Dialogue:"):
            parts = line.split(",", 9)
            out.append((ms(parts[1]), ms(parts[2]), parts[9]))
    return out


def test_caption_cards_split_at_hook_prefix_end() -> None:
    """Regression: hook tinish belgisisiz va qisqa pauza bilan tugasa ham, hech bir kartochka
    hook -> klip chegarasini (prefix_ms) kesib o'tmaydi (SRT, VTT, ASS, host captions)."""
    from lahza_engine.config import Settings
    from lahza_engine.hostplan.build import caption_lines
    from lahza_engine.subtitle.ass import _cues, build_ass, build_vtt, caption_breaks, clean_words
    from lahza_engine.subtitle.style import StyleTemplate

    words = make_words("bir ikki uch to'rt besh olti", 0, word_ms=900, gap_ms=100)
    tl = Timeline(0, 6_000, hook=(3_000, 5_000))  # "to'rt besh" -> 0..1900, klip 2000 dan
    b = tl.prefix_ms
    assert b == 2_000

    cues = _cues(words, tl, 7, None)
    assert [(a, e, t) for a, e, t in cues[:2]] == [(0, 1_900, "to'rt besh"),
                                                   (2_000, 7_900, "bir ikki uch to'rt besh olti")]
    srt = build_srt(words, tl, max_words=7)
    assert srt.startswith("1\n00:00:00,000 --> 00:00:01,900\nto'rt besh\n")
    assert "2\n00:00:02,000 --> " in srt
    assert "00:00:00.000 --> 00:00:01.900\nto'rt besh\n" in build_vtt(words, tl, max_words=7)

    for anim in ("none", "karaoke"):
        style = StyleTemplate(max_words=7, max_lines=2, animation=anim)
        events = _ass_events(build_ass(words, tl, style))
        assert events and all(e <= b or a >= b for a, e, _ in events), events
        assert any(e == b for _, e, _ in events)  # hook kartochkasi aynan hook oxirigacha ushlanadi
        assert any(a == b for a, _, _ in events)

    style = StyleTemplate(max_words=7, max_lines=2)
    lines = caption_lines(map_words(clean_words(words, style), tl), style, Settings(), 1080,
                          breaks_ms=caption_breaks(tl))
    assert all(ln.t1 * 1000 <= b or ln.t0 * 1000 >= b for ln in lines)
    assert len(lines[0].words) == 2 and lines[0].t1 == b / 1000


def test_caption_cards_unchanged_without_hook() -> None:
    from lahza_engine.subtitle.ass import _cues, build_ass
    from lahza_engine.subtitle.style import StyleTemplate

    words = make_words("bir ikki uch to'rt besh olti", 0, word_ms=900, gap_ms=100)
    tl = Timeline(0, 6_000)
    assert _cues(words, tl, 7, None) == [(0, 5_900, "bir ikki uch to'rt besh olti")]
    assert build_srt(words, tl, max_words=7) == \
        "1\n00:00:00,000 --> 00:00:05,900\nbir ikki uch to'rt besh olti\n"
    events = _ass_events(build_ass(words, tl, StyleTemplate(max_words=7, max_lines=2, animation="none")))
    assert [(a, e) for a, e, _ in events] == [(0, 5_900)]


# ---- Baza ---------------------------------------------------------------------------

def test_project_migration_adds_hook_columns(tmp_path: Path) -> None:
    db.open_project(tmp_path).close()
    raw = sqlite3.connect(tmp_path / "project.db")
    raw.executescript("ALTER TABLE clips DROP COLUMN hook_start_ms; ALTER TABLE clips DROP COLUMN hook_end_ms;"
                      " UPDATE schema_version SET version = 2;")
    raw.commit()
    raw.close()
    conn = db.open_project(tmp_path)
    assert db.schema_version(conn) == db.PROJECT_SCHEMA_VERSION == 3
    cols = {r[1] for r in conn.execute("PRAGMA table_info(clips)")}
    assert {"hook_start_ms", "hook_end_ms"} <= cols
    assert (tmp_path / "project.v2.bak").exists()


# ---- API ----------------------------------------------------------------------------

def _seed(st, tmp_path: Path, hook_sentence: int | None = None):
    _, eid, pdir = seed_episode(st, tmp_path, n=6)
    conn = db.open_project(pdir)
    ss = db.load_transcript(conn, eid).sentences
    clip = Clip(id=uuid.uuid4().hex[:12], media_id=eid, start_ms=ss[0].start_ms, end_ms=ss[3].end_ms,
                start_sentence_id=0, end_sentence_id=3, hook_sentence_id=hook_sentence,
                title="Klip", source=ClipSource.MANUAL)
    db.insert_manual_clip(conn, clip)
    conn.close()
    return eid, clip, ss, pdir


def test_api_hook_default_off_auto_manual_and_disable(tmp_path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    eid, clip, ss, pdir = _seed(st, tmp_path, hook_sentence=2)
    url = f"/v1/episodes/{eid}/clips/{clip.id}"
    assert c.get(f"/v1/episodes/{eid}/clips").json()[0]["hook"] is None  # standart - o'chiq

    # Avtomatik: LLM hook gapi (2) ichidan 2-4 s.
    r = c.put(f"{url}/hook", json={"enabled": True})
    assert r.status_code == 200, r.text
    h = r.json()["hook"]
    assert ss[2].start_ms - 100 <= h["start_ms"] < h["end_ms"] <= ss[2].end_ms + 200
    assert HOOK_MIN_MS <= h["end_ms"] - h["start_ms"] <= HOOK_MAX_MS + 300
    assert c.get(f"/v1/episodes/{eid}/clips").json()[0]["hook"] == h  # saqlangan

    # Qo'lda boshqa gap.
    r = c.put(f"{url}/hook", json={"enabled": True, "sentence_id": 1})
    assert r.status_code == 200 and ss[1].start_ms - 100 <= r.json()["hook"]["start_ms"] <= ss[1].end_ms

    # Qo'lda oraliq: so'z chegarasiga kengaytiriladi.
    w = ss[3].words
    r = c.put(f"{url}/hook", json={"enabled": True, "start_ms": w[1].start_ms + 30, "end_ms": w[5].end_ms - 30})
    assert r.status_code == 200
    assert r.json()["hook"] == {"start_ms": w[1].start_ms, "end_ms": w[5].end_ms}

    # Kalit kadr chegarasi chiqish davomiyligiga (prefiks bilan) moslashgan.
    dur = clip.end_ms - clip.start_ms + (w[5].end_ms - w[1].start_ms)
    kf = {"t_ms": dur - 10, "layout": "fit_blur"}
    assert c.put(f"{url}/keyframes", json={"keyframes": [kf]}).status_code == 200

    r = c.put(f"{url}/hook", json={"enabled": False})
    assert r.status_code == 200 and r.json()["hook"] is None
    assert c.put(f"{url}/keyframes", json={"keyframes": [kf]}).status_code == 400


def test_api_hook_validation_and_candidates(tmp_path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    eid, clip, ss, pdir = _seed(st, tmp_path)
    url = f"/v1/episodes/{eid}/clips/{clip.id}"
    assert c.put(f"{url}/hook", json={"enabled": True, "start_ms": 5}).status_code == 400
    assert c.put(f"{url}/hook", json={"enabled": True, "start_ms": 0, "end_ms": clip.end_ms + 5_000}).status_code == 400
    assert c.put(f"{url}/hook", json={"enabled": True, "sentence_id": 5}).status_code == 404  # klipdan tashqari
    w = ss[1].words
    assert c.put(f"{url}/hook", json={"enabled": True, "start_ms": w[0].start_ms,
                                      "end_ms": w[0].end_ms}).status_code == 400  # < 0.5 s
    assert c.put(f"/v1/episodes/{eid}/clips/nope/hook", json={"enabled": True}).status_code == 404

    r = c.get(f"{url}/hook/candidates")
    assert r.status_code == 200
    cands = r.json()
    assert cands and {"start_ms", "end_ms", "sentence_ids", "text", "score", "reasons"} <= set(cands[0])
    assert all(clip.start_ms <= x["start_ms"] < x["end_ms"] <= clip.end_ms for x in cands)


def test_api_hook_clears_auto_keyframes(tmp_path, monkeypatch) -> None:
    c, st = make_client(tmp_path, monkeypatch)
    eid, clip, ss, pdir = _seed(st, tmp_path)
    conn = db.open_project(pdir)
    with conn:
        conn.execute("INSERT INTO reframe_keyframes(clip_id, t_ms, layout, source) VALUES (?, 0, 'fit_blur', 'avto')",
                     (clip.id,))
    conn.close()
    assert c.put(f"/v1/episodes/{eid}/clips/{clip.id}/hook", json={"enabled": True}).status_code == 200
    conn = db.open_project(pdir)
    assert conn.execute("SELECT COUNT(*) FROM reframe_keyframes WHERE clip_id = ?", (clip.id,)).fetchone()[0] == 0
    conn.close()
