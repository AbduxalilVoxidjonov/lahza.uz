from pathlib import Path

import pytest
from conftest import make_sentences

from lahza_engine.core.runner import Cancelled, StageContext, StageDef, run_stages
from lahza_engine.db import store as db
from lahza_engine.types import Clip, ClipSource, Transcript


def _media(conn, mid="m1"):
    with conn:
        conn.execute("INSERT INTO media(id, path, hash, duration_ms, fps, width, height, audio_channels)"
                     " VALUES (?,?,?,?,?,?,?,?)", (mid, "/x.mp4", "h", 1000, 25, 1920, 1080, 2))


def test_transcript_roundtrip_keeps_user_edits(tmp_path: Path) -> None:
    conn = db.open_project(tmp_path)
    _media(conn)
    tr = Transcript(sentences=make_sentences(3))
    db.save_transcript(conn, "m1", tr)
    db.edit_word(conn, "m1", 1, 0, "Tuzatilgan")
    db.save_transcript(conn, "m1", tr)  # qayta tahlil
    back = db.load_transcript(conn, "m1")
    w = back.sentences[1].words[0]
    assert w.text == "Tuzatilgan" and w.edited and w.original_text == "so'z1_0"
    assert len(back.sentences) == 3


def test_clips_roundtrip_and_user_edits_survive(tmp_path: Path) -> None:
    conn = db.open_project(tmp_path)
    _media(conn)
    c1 = Clip(id="a", media_id="m1", start_ms=0, end_ms=30_000, start_sentence_id=0,
              end_sentence_id=4, title="Bir", hashtags=["#x"], cuts=[(1000, 2000)])
    c2 = c1.model_copy(update={"id": "b", "title": "Ikki", "cuts": []})
    db.save_clips(conn, [c1, c2])
    db.update_clip(conn, "a", status="qabul", title="Bir (tahrir)")
    db.save_clips(conn, [c2.model_copy(update={"id": "c", "source": ClipSource.AI_LLM})])
    ids = {c.id: c for c in db.load_clips(conn, "m1")}
    assert set(ids) == {"a", "c"}  # 'b' almashtirildi, qabul qilingan 'a' qoldi
    assert ids["a"].title == "Bir (tahrir)" and ids["a"].cuts == [(1000, 2000)]
    fb = conn.execute("SELECT action FROM feedback").fetchall()
    assert [r[0] for r in fb] == ["qabul"]


def test_runner_caches_and_invalidates(tmp_path: Path) -> None:
    conn = db.open_project(tmp_path)
    _media(conn)
    calls: list[str] = []
    param = {"v": 1}

    def a(ctx):
        calls.append("a")
        return {"x": 1}

    def b(ctx):
        calls.append("b")
        return {"y": ctx.results["a"]["x"] + 1}

    stages = [StageDef("a", 1, a, params=lambda c: dict(param)), StageDef("b", 1, b)]

    def ctx():
        return StageContext("m1", "h", tmp_path, conn)

    assert run_stages(stages, ctx())["b"] == {"y": 2}
    run_stages(stages, ctx())
    assert calls == ["a", "b"]  # ikkinchi marta keshdan
    param["v"] = 2
    run_stages(stages, ctx())
    assert calls == ["a", "b", "a", "b"]  # yuqori oqim o'zgardi -> pastki ham qayta


def test_runner_failure_and_cancel_recorded(tmp_path: Path) -> None:
    conn = db.open_project(tmp_path)
    _media(conn)

    def boom(ctx):
        raise RuntimeError("xato")

    with pytest.raises(RuntimeError):
        run_stages([StageDef("x", 1, boom)], StageContext("m1", "h", tmp_path, conn))
    row = conn.execute("SELECT status, error FROM stage_runs WHERE stage='x'").fetchone()
    assert row["status"] == "failed" and "xato" in row["error"]

    c = StageContext("m1", "h", tmp_path, conn)
    c.cancel.set()
    with pytest.raises(Cancelled):
        run_stages([StageDef("y", 1, lambda ctx: {})], c)
